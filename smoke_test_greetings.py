import os
import sys
import wave
import tempfile
import subprocess
import numpy as np
import scipy.signal
from transcriber import Transcriber, clean_hallucinations
from config import load_config
from injector import ForwardStreamCommitter

# Lista zwrotów powitalnych i pożegnalnych do przetestowania
TEST_PHRASES = [
    # Powitania
    "Cześć",
    "Hejka",
    "Słuchajcie",
    "Siema",
    "Jak się macie",
    "Hej",
    "Witaj",
    "Słuchaj",
    "Dzień dobry",
    "Cześć, jak się masz?",
    "Dzień dobry, witam wszystkich",
    "Słuchaj, mam takie pytanie",
    
    # Pożegnania i podziękowania
    "Na razie",
    "Dzięki",
    "Do zobaczenia",
    "Było fajnie",
    "Do widzenia",
    "Spotkamy się",
    "Będzie okej",
    "Dzięki za informację",
    "Dziękuję bardzo",
    "Pozdrawiam",
    "Miłego dnia",
    "Na razie, trzymaj się"
]

def synthesize_phrase(phrase: str, wav_path: str):
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft Paulina Desktop')
$synth.SetOutputToWaveFile('{wav_path}')
$synth.Speak('{phrase}')
$synth.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True, stdout=subprocess.DEVNULL)

def load_audio_16k(wav_path: str) -> np.ndarray:
    with wave.open(wav_path, "rb") as wf:
        n_ch = wf.getnchannels()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if n_ch > 1:
            audio = audio.reshape(-1, n_ch).mean(axis=1)
    if sr != 16000:
        audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr)).astype(np.float32)
    return audio

def main():
    print("=" * 70)
    print("SMOKE TEST: Polski silnik rozpoznawania powitań i pożegnań")
    print("=" * 70)
    
    cfg = load_config()
    print(f"Model Whisper: {cfg.get('model_size', 'turbo')} na {cfg.get('device', 'cuda')}")
    print("Inicjalizacja transkrybera...")
    t = Transcriber(cfg)
    
    tmp_dir = tempfile.gettempdir()
    results = []
    
    print("\nRozpoczynanie syntezy i transkrypcji zwrotów...\n")
    
    for i, phrase in enumerate(TEST_PHRASES, 1):
        wav_path = os.path.join(tmp_dir, f"smoke_test_{i}.wav")
        try:
            synthesize_phrase(phrase, wav_path)
            audio = load_audio_16k(wav_path)
            
            # 1. Test trybu wsadowego (Standard Dictation batch)
            batch_result = t.transcribe(audio)
            
            # 2. Test trybu strumieniowego (Streaming chunk + finalize)
            chunks_typed = []
            committer = ForwardStreamCommitter(type_callback=lambda c: chunks_typed.append(c))
            
            completed, tail = t.transcribe_stream_chunk(audio)
            for seg, _ in completed:
                committer.commit_segment(seg)
            if tail:
                committer.process_hypothesis(tail)
            committer.finalize(tail)
            stream_result = "".join(chunks_typed).strip()
            
            results.append({
                "phrase": phrase,
                "batch": batch_result,
                "stream": stream_result,
                "audio_len_s": len(audio) / 16000.0
            })
            
            print(f"[{i:02d}/{len(TEST_PHRASES):02d}] '{phrase}' ({len(audio)/16000.0:.2f}s)")
            print(f"     Batch:    '{batch_result}'")
            print(f"     Stream:   '{stream_result}'")
            
        except Exception as e:
            print(f"[{i:02d}] BŁĄD dla '{phrase}': {e}")
            results.append({"phrase": phrase, "batch": f"ERROR: {e}", "stream": f"ERROR: {e}", "audio_len_s": 0})
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    print("\n" + "=" * 70)
    print("PODSUMOWANIE WYNIKÓW SMOKE TESTU:")
    print("=" * 70)
    
    batch_ok = 0
    stream_ok = 0
    
    for r in results:
        p = r['phrase'].lower().replace('?', '').replace('.', '').replace(',', '').strip()
        b = r['batch'].lower().replace('?', '').replace('.', '').replace(',', '').strip()
        s = r['stream'].lower().replace('?', '').replace('.', '').replace(',', '').strip()
        
        b_match = (p in b or b in p) and len(b) > 0
        s_match = (p in s or s in p) and len(s) > 0
        
        if b_match: batch_ok += 1
        if s_match: stream_ok += 1
        
        status_b = "OK" if b_match else "FAIL"
        status_s = "OK" if s_match else "FAIL"
        
        print(f"'{r['phrase']:<30}' | Batch: [{status_b}] '{r['batch']}' | Stream: [{status_s}] '{r['stream']}'")
        
    print("-" * 70)
    print(f"Batch Dictation Success Rate:  {batch_ok}/{len(results)} ({batch_ok/len(results)*100:.1f}%)")
    print(f"Stream Dictation Success Rate: {stream_ok}/{len(results)} ({stream_ok/len(results)*100:.1f}%)")
    print("=" * 70)

if __name__ == "__main__":
    main()
