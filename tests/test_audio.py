import wave
from pathlib import Path

import pytest

from voiceops.audio import AudioContractError, WavPCM16Source


def _write_wav(path: Path, *, channels: int = 1, sample_width: int = 2, sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * (sample_rate // 10))


def test_wav_source_validates_pcm16_mono_16khz(tmp_path: Path) -> None:
    path = tmp_path / "fixture.wav"
    _write_wav(path)
    source = WavPCM16Source(path, chunk_ms=100, real_time=False)

    report = source.validate()
    assert report["channels"] == 1
    assert report["sample_width_bytes"] == 2
    assert report["sample_rate"] == 16000
    assert list(source)


def test_wav_source_rejects_wrong_sample_rate(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    _write_wav(path, sample_rate=8000)
    source = WavPCM16Source(path, sample_rate=16000, real_time=False)

    with pytest.raises(AudioContractError, match="sample_rate=8000"):
        source.validate()


def test_chunk_window_matches_streaming_contract(tmp_path: Path) -> None:
    path = tmp_path / "fixture.wav"
    _write_wav(path)

    with pytest.raises(ValueError, match="between 50 and 1000"):
        WavPCM16Source(path, chunk_ms=20)
