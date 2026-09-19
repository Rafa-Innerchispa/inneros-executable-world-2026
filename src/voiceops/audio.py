from __future__ import annotations

import time
import wave
from pathlib import Path
from typing import Iterator


class AudioContractError(ValueError):
    """Raised when an audio source cannot satisfy the AssemblyAI live contract."""


class WavPCM16Source:
    """Validated WAV source that yields real-time-safe PCM16 mono chunks.

    AssemblyAI Universal-3.5 Pro Realtime expects PCM16 mono audio whose sample
    rate matches the streaming session. This source validates a WAV file before
    streaming so a bad fixture fails loudly instead of producing nonsense text.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        sample_rate: int = 16000,
        chunk_ms: int = 100,
        real_time: bool = True,
    ) -> None:
        if not 50 <= chunk_ms <= 1000:
            raise ValueError("chunk_ms must be between 50 and 1000")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        self.path = Path(path)
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.real_time = real_time
        self.frames_per_chunk = max(1, int(sample_rate * chunk_ms / 1000))

    def validate(self) -> dict[str, int]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        with wave.open(str(self.path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            frame_rate = wav.getframerate()
            frame_count = wav.getnframes()

        errors: list[str] = []
        if channels != 1:
            errors.append(f"channels={channels}, expected 1")
        if sample_width != 2:
            errors.append(f"sample_width={sample_width}, expected 2 bytes PCM16")
        if frame_rate != self.sample_rate:
            errors.append(f"sample_rate={frame_rate}, expected {self.sample_rate}")
        if errors:
            raise AudioContractError("; ".join(errors))

        return {
            "channels": channels,
            "sample_width_bytes": sample_width,
            "sample_rate": frame_rate,
            "frame_count": frame_count,
            "chunk_ms": self.chunk_ms,
        }

    def __iter__(self) -> Iterator[bytes]:
        self.validate()
        sleep_seconds = self.chunk_ms / 1000
        with wave.open(str(self.path), "rb") as wav:
            while True:
                chunk = wav.readframes(self.frames_per_chunk)
                if not chunk:
                    break
                yield chunk
                if self.real_time:
                    time.sleep(sleep_seconds)
