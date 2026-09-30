import os
import wave
import tempfile
import subprocess
import numpy as np
import scipy.signal
from transcriber import Transcriber
from config import load_config
from injector import ForwardStreamCommitter

phrase = "Cześć! Słuchajcie, mam pytanie. Dzień dobry wszystkim. Na razie, do widzenia!"
wav_path = os.path.join(tempfile.gettempdir(), "multi_test.wav")
ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft Paulina Desktop')
$synth.SetOutputToWaveFile('{wav_path}')
$synth.Speak('{phrase}')
$synth.Dispose()
"""
subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True, stdout=subprocess.DEVNULL)

with wave.open(wav_path, "rb") as wf:
    audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    sr = wf.getframerate()
    if sr != 16000:
        audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr)).astype(np.float32)

t = Transcriber(load_config())

# 1. Batch Test
res_batch = t.transcribe(audio)
print("=" * 60)
print("MULTI-PHRASE BATCH RESULT:")
print(f"'{res_batch}'")

# 2. Streaming Simulation (0.4s steps)
typed_chunks = []
committer = ForwardStreamCommitter(type_callback=lambda c: typed_chunks.append(c))
sample_rate = 16000
step_samples = int(0.4 * sample_rate)
committed_offset = 0

for end_idx in range(step_samples, len(audio) + step_samples, step_samples):
    curr_audio = audio[committed_offset:min(end_idx, len(audio))]
    if len(curr_audio) < int(0.4 * sample_rate):
        continue
    completed, tail = t.transcribe_stream_chunk(curr_audio)
    if completed:
        for seg_text, _ in completed:
            committer.commit_segment(seg_text)
        committed_offset += int(completed[-1][1] * sample_rate)
    if tail:
        committer.process_hypothesis(tail)

from recorder import AudioRecorder
rem = audio[committed_offset:]
trimmed_rem = AudioRecorder.trim_silence(rem, sample_rate=sample_rate, keep_lead_s=0.20, keep_tail_s=0.35)
final_tail = t.transcribe(trimmed_rem) if len(trimmed_rem) >= int(0.25 * sample_rate) else ""
committer.finalize(final_tail)

res_stream = "".join(typed_chunks).strip()
print("=" * 60)
print("MULTI-PHRASE STREAM RESULT:")
print(f"'{res_stream}'")
print("=" * 60)
