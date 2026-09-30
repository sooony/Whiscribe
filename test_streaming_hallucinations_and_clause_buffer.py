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

if __name__ == '__main__':
    unittest.main()
