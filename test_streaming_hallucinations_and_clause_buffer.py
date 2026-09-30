import unittest
import time
from transcriber import clean_hallucinations
from injector import ForwardStreamCommitter

class TestHallucinationsAndStreaming(unittest.TestCase):
    """Testy weryfikujące eliminację halucynacji i płynność bufora klauzul."""

    def test_01_all_whisper_hallucinations_eliminated(self):
        cases = [
            ("Dziękuje za uwagę.", ""),
            ("Wielkie dzięki za uwagę!", ""),
            ("Dziękujemy za wysłuchanie.", ""),
            ("Subskrybuj mój kanał i zostaw lajka!", ""),
            ("Napisy stworzone przez społeczność YouTube.", ""),
            ("I to by było na tyle.", ""),
            ("To wszystko na dzisiaj.", ""),
            ("coś sobie robimy. Dziękuję za uwagę i zobaczmy", "Coś sobie robimy. I zobaczmy"),
            ("ZA OBSERWACIE ", ""),
            ("zaobserwujcie", ""),
            ("Zaobserwujcie mój profil", ""),
            ("Zaobserwuj po więcej!", ""),
            ("Dzięki za obserwację.", ""),
            ("Dziękuję za obserwację", ""),
            ("Zostaw lajka i zaobserwujcie.", ""),
            ("To jest ważne zdanie. ZA OBSERWACIE  I mówimy dalej.", "To jest ważne zdanie. I mówimy dalej."),
            ("Kolejna wypowiedź zaobserwujcie po więcej i teraz podsumowanie.", "Kolejna wypowiedź i teraz podsumowanie.")
        ]
        for inp, expected in cases:
            cleaned = clean_hallucinations(inp)
            self.assertEqual(cleaned, expected, f"Halucynacja nie została poprawnie usunięta dla: {inp!r} (otrzymano: {cleaned!r})")

    def test_01b_conversational_phrases_preserved(self):
        cases = [
            ("Cześć", "Cześć"),
            ("Cześć, jak się masz?", "Cześć, jak się masz?"),
            ("Hej, jak się masz", "Hej, jak się masz"),
            ("Słuchaj", "Słuchaj"),
            ("Na razie", "Na razie"),
            ("Dzień dobry.", "Dzień dobry."),
            ("Do widzenia państwu.", "Do widzenia państwu."),
            ("Dziękuję bardzo za pomoc.", "Dziękuję bardzo za pomoc."),
            ("Pozdrawiam serdecznie.", "Pozdrawiam serdecznie."),
            ("Miłego dnia!", "Miłego dnia!")
        ]
        for inp, expected in cases:
            cleaned = clean_hallucinations(inp)
            self.assertEqual(cleaned, expected, f"Fraza konwersacyjna została błędnie usunięta dla: {inp!r} (otrzymano: {cleaned!r})")

    def test_02_forward_committer_with_hallucinations(self):
        chunks = []
        committer = ForwardStreamCommitter(type_callback=lambda c: chunks.append(c))

        # Krok 1: Hipoteza początkowa
        committer.process_hypothesis("No dobrze zobaczmy jak")
        # Krok 2: Whisper wtrąca w ciszy halucynację "Dziękuję za uwagę"
        committer.process_hypothesis("No dobrze zobaczmy jak to działa. Dziękuję za uwagę.")
        # Krok 3: Użytkownik kontynuuje mowę
        committer.process_hypothesis("No dobrze zobaczmy jak to działa i jak to będzie wyglądało dalej.")
        committer.finalize("No dobrze zobaczmy jak to działa i jak to będzie wyglądało dalej.")

        full_text = "".join(chunks)
        self.assertNotIn("Dziękuj", full_text)
        self.assertNotIn("uwagę", full_text)
        self.assertEqual(full_text.strip(), "No dobrze zobaczmy jak to działa i jak to będzie wyglądało dalej.")

    def test_02b_streaming_anchor_alignment_no_word_duplication(self):
        """
        Weryfikacja eliminacji powielania słów przy korektach fonetycznych Whispera (np. 'OK' -> 'Okej' -> 'Ok').
        Przypadek zgłoszony przez użytkownika w trybie streamingu na żywo.
        """
        typed_stream = []
        committer = ForwardStreamCommitter(type_callback=lambda x: typed_stream.append(x))

        # Krok 1
        committer.process_hypothesis("OK, dodaję Ci jeszcze dane")
        # Krok 2: Whisper rewiduje początek na "Okej"
        committer.process_hypothesis("Okej, dodaję Ci jeszcze dane, które miałem w")
        # Krok 3: Whisper rewiduje początek na "Ok"
        committer.process_hypothesis("Ok, dodaję Ci jeszcze dane, które miałem z synu to odnośnie")
        # Krok 4: Finalizacja
        committer.finalize("OK, dodaję Ci jeszcze dane, które miałem z synu odnośnie tej strony.")

        result = "".join(typed_stream).strip()
        self.assertIn("OK, dodaję Ci jeszcze", result)
        self.assertEqual(result.count("dodaję"), 1, f"Słowo 'dodaję' zostało powielone! Otrzymano: {result}")
        self.assertEqual(result.count("miałem"), 1, f"Słowo 'miałem' zostało powielone! Otrzymano: {result}")
        self.assertNotIn("Okej", result, "Poprawka fonetyczna 'Okej' nie powinna być powtórnie wklejana")

    def test_03_clause_buffer_flushing(self):
        """Weryfikacja czy buforowanie klauzul zachowuje wszystkie spacje i interpunkcję."""
        typed_chunks = []
        def fake_type(text):
            typed_chunks.append(text)

        buffer = ""
        stream = ["To ", "jest ", "pierwsza ", "część ", "zdania, ", "a ", "to ", "jest ", "druga."]

        for part in stream:
            buffer += part
            buf_words = buffer.strip().split()
            has_punct = any(buffer.rstrip().endswith(p) for p in ('.', ',', '!', '?', ';', ':'))
            if has_punct or len(buf_words) >= 4:
                fake_type(buffer)
                buffer = ""

        if buffer:
            fake_type(buffer)

        reconstructed = "".join(typed_chunks)
        self.assertEqual(reconstructed, "To jest pierwsza część zdania, a to jest druga.")

    def test_04_polish_conjunction_casing(self):
        """Weryfikacja czy sztuczne wielkie litery w spójnikach wewnątrz zdania są redukowane."""
        inp = "No dobrze, to zróbmy teraz mały test I zobaczmy jak to działa."
        res = clean_hallucinations(inp)
        self.assertEqual(res, "No dobrze, to zróbmy teraz mały test i zobaczmy jak to działa.")

        inp2 = "Widzę to A tamto zostawiam."
        res2 = clean_hallucinations(inp2)
        self.assertEqual(res2, "Widzę to a tamto zostawiam.")

    def test_05_silence_trimming(self):
        """Weryfikacja czy trim_silence ucina zarówno wstępną jak i końcową ciszę."""
        import numpy as np
        from recorder import AudioRecorder

        sr = 16000
        # 1s ciszy na starcie, 1s sygnału mowy, 1s ciszy na końcu
        sil_pre = np.zeros(sr, dtype=np.float32)
        speech = np.ones(sr, dtype=np.float32) * 0.1
        sil_post = np.zeros(sr, dtype=np.float32)

        full = np.concatenate([sil_pre, speech, sil_post])
        trimmed = AudioRecorder.trim_silence(full, sample_rate=sr, keep_lead_s=0.20, keep_tail_s=0.35)

        # Powinno uciąć ok. 0.8s z przodu i ok. 0.65s z tyłu
        expected_min_len = int(1.0 * sr)
        expected_max_len = int(1.7 * sr)
        self.assertTrue(expected_min_len <= len(trimmed) <= expected_max_len, f"Długość przyciętego audio nieprawidłowa: {len(trimmed)/sr:.2f}s")

if __name__ == '__main__':
    unittest.main()
