"""
test_volume_meter.py - Fala w widżecie odzwierciedla głośność mowy.

Wcześniej skala liniowa nasycała się już przy zwykłej mowie (fala zawsze pełna).
Teraz: cicho/z daleka -> mała fala, normalnie -> średnia, głośno przy mikrofonie -> pełna.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recorder import AudioRecorder


def _level(rms, noise_floor=0.002):
    r = AudioRecorder()
    r.is_recording = True
    r.noise_floor = noise_floor
    r.current_volume = rms
    return r.get_volume_level()


def test_level_grows_with_loudness():
    levels = [_level(x) for x in (0.004, 0.01, 0.03, 0.08, 0.2)]
    assert levels == sorted(levels)
    assert len(set(levels)) == len(levels), "kolejne poziomy głośności nie mogą się zlewać"


def test_normal_speech_does_not_saturate():
    assert 0.4 < _level(0.03) < 0.75
    assert _level(0.01) < 0.45, "mowa z daleka powinna dawać wyraźnie mniejszą falę"


def test_loud_speech_reaches_full_scale():
    assert _level(0.25) == 1.0


def test_silence_and_noise_floor_give_zero():
    assert _level(0.0) == 0.0
    assert _level(0.002) == 0.0
    r = AudioRecorder()
    r.current_volume = 0.2
    assert r.get_volume_level() == 0.0, "bez nagrywania fala ma być płaska"
