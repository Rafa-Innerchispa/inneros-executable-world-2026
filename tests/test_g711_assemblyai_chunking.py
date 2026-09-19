from __future__ import annotations

import struct

import pytest

from voiceops.adapters.g711_rtp import (
    G711AssemblyAudioBridge,
    PCMU_PAYLOAD_TYPE,
    RtpPacket,
    pcm16_to_ulaw,
)


def _rtp(sequence: int, timestamp: int, sample: int = 1200) -> bytes:
    pcm8 = struct.pack("<" + "h" * 160, *([sample] * 160))
    payload = pcm16_to_ulaw(pcm8)
    return RtpPacket(PCMU_PAYLOAD_TYPE, sequence, timestamp, 77, payload).to_bytes()


def test_coalesces_20ms_rtp_into_100ms_provider_chunks() -> None:
    bridge = G711AssemblyAudioBridge()
    datagrams = [_rtp(i, i * 160) for i in range(10)]
    chunks = list(bridge.iter_assemblyai_pcm16(datagrams, chunk_ms=100))
    assert [len(chunk) for chunk in chunks] == [3200, 3200]
    assert bridge.received_packets == 10


def test_final_short_tail_is_padded_to_50ms_minimum() -> None:
    bridge = G711AssemblyAudioBridge()
    chunks = list(bridge.iter_assemblyai_pcm16([_rtp(1, 0)], chunk_ms=100))
    assert len(chunks) == 1
    assert len(chunks[0]) == 1600
    assert chunks[0][:640] != b"\x00" * 640
    assert chunks[0][640:] == b"\x00" * 960


@pytest.mark.parametrize("chunk_ms", [49, 1001])
def test_rejects_provider_invalid_chunk_duration(chunk_ms: int) -> None:
    bridge = G711AssemblyAudioBridge()
    with pytest.raises(ValueError):
        list(bridge.iter_assemblyai_pcm16([], chunk_ms=chunk_ms))
