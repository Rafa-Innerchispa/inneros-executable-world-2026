from __future__ import annotations

import secrets
import struct
from dataclasses import dataclass
from typing import Iterable, Iterator

PCMU_PAYLOAD_TYPE = 0
PCMA_PAYLOAD_TYPE = 8
TELEPHONE_EVENT_PAYLOAD_TYPE = 101
ASSEMBLYAI_SAMPLE_RATE = 16000
RTP_CLOCK_RATE = 8000
RTP_PTIME_MS = 20
RTP_SAMPLES_PER_PACKET = RTP_CLOCK_RATE * RTP_PTIME_MS // 1000


class RtpProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RtpPacket:
    payload_type: int
    sequence: int
    timestamp: int
    ssrc: int
    payload: bytes
    marker: bool = False

    def to_bytes(self) -> bytes:
        if not 0 <= self.payload_type <= 127:
            raise ValueError("payload_type must be 0..127")
        if not 0 <= self.sequence <= 0xFFFF:
            raise ValueError("sequence must be 0..65535")
        if not 0 <= self.timestamp <= 0xFFFFFFFF:
            raise ValueError("timestamp must be 0..2^32-1")
        if not 0 <= self.ssrc <= 0xFFFFFFFF:
            raise ValueError("ssrc must be 0..2^32-1")
        second = self.payload_type | (0x80 if self.marker else 0)
        return struct.pack("!BBHII", 0x80, second, self.sequence, self.timestamp, self.ssrc) + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "RtpPacket":
        if len(data) < 12:
            raise RtpProtocolError("RTP packet is shorter than the fixed header")
        first, second, sequence, timestamp, ssrc = struct.unpack("!BBHII", data[:12])
        if first >> 6 != 2:
            raise RtpProtocolError(f"unsupported RTP version {first >> 6}")
        padding = bool(first & 0x20)
        extension = bool(first & 0x10)
        csrc_count = first & 0x0F
        offset = 12 + 4 * csrc_count
        if len(data) < offset:
            raise RtpProtocolError("truncated RTP CSRC list")
        if extension:
            if len(data) < offset + 4:
                raise RtpProtocolError("truncated RTP extension header")
            words = struct.unpack("!H", data[offset + 2 : offset + 4])[0]
            offset += 4 + 4 * words
            if len(data) < offset:
                raise RtpProtocolError("truncated RTP extension payload")
        end = len(data)
        if padding:
            pad_bytes = data[-1]
            if pad_bytes == 0 or pad_bytes > end - offset:
                raise RtpProtocolError("invalid RTP padding")
            end -= pad_bytes
        return cls(second & 0x7F, sequence, timestamp, ssrc, data[offset:end], bool(second & 0x80))


def ulaw_to_pcm16(payload: bytes) -> bytes:
    return b"".join(struct.pack("<h", _ulaw_decode(value)) for value in payload)


def pcm16_to_ulaw(pcm16: bytes) -> bytes:
    return bytes(_ulaw_encode(sample) for sample in _unpack_pcm16(pcm16))


def alaw_to_pcm16(payload: bytes) -> bytes:
    return b"".join(struct.pack("<h", _alaw_decode(value)) for value in payload)


def pcm16_to_alaw(pcm16: bytes) -> bytes:
    return bytes(_alaw_encode(sample) for sample in _unpack_pcm16(pcm16))


def upsample_pcm16_8k_to_16k(pcm16: bytes) -> bytes:
    samples = _unpack_pcm16(pcm16)
    if not samples:
        return b""
    output: list[int] = []
    for index, sample in enumerate(samples):
        following = samples[index + 1] if index + 1 < len(samples) else sample
        output.extend((sample, (sample + following) // 2))
    return struct.pack("<" + "h" * len(output), *output)


def downsample_pcm16_16k_to_8k(pcm16: bytes) -> bytes:
    samples = _unpack_pcm16(pcm16)
    if not samples:
        return b""
    if len(samples) % 2:
        samples.append(samples[-1])
    output = [(samples[index] + samples[index + 1]) // 2 for index in range(0, len(samples), 2)]
    return struct.pack("<" + "h" * len(output), *output)


class G711AssemblyAudioBridge:
    """Translate UCM RTP G.711 audio to/from AssemblyAI PCM16 mono 16 kHz."""

    def __init__(self, *, outbound_payload_type: int = PCMU_PAYLOAD_TYPE, ssrc: int | None = None) -> None:
        if outbound_payload_type not in {PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE}:
            raise ValueError("outbound_payload_type must be PCMU (0) or PCMA (8)")
        self.outbound_payload_type = outbound_payload_type
        self.ssrc = ssrc if ssrc is not None else secrets.randbits(32)
        self.sequence = secrets.randbits(16)
        self.timestamp = secrets.randbits(32)
        self.received_packets = 0
        self.ignored_packets = 0
        self.last_sequence: int | None = None

    @property
    def assemblyai_audio_contract(self) -> dict[str, object]:
        return {"encoding": "pcm_s16le", "channels": 1, "sample_rate": ASSEMBLYAI_SAMPLE_RATE}

    def decode_rtp_for_assemblyai(self, packet_data: bytes) -> bytes | None:
        packet = RtpPacket.from_bytes(packet_data)
        if packet.payload_type == TELEPHONE_EVENT_PAYLOAD_TYPE:
            self.ignored_packets += 1
            return None
        if packet.payload_type == PCMU_PAYLOAD_TYPE:
            pcm8 = ulaw_to_pcm16(packet.payload)
        elif packet.payload_type == PCMA_PAYLOAD_TYPE:
            pcm8 = alaw_to_pcm16(packet.payload)
        else:
            self.ignored_packets += 1
            return None
        self.last_sequence = packet.sequence
        self.received_packets += 1
        return upsample_pcm16_8k_to_16k(pcm8)

    def iter_assemblyai_pcm16(
        self,
        datagrams: Iterable[bytes],
        *,
        chunk_ms: int = 100,
    ) -> Iterator[bytes]:
        """Coalesce RTP frames into provider-valid PCM16 streaming chunks.

        UCM G.711 commonly arrives in 20 ms RTP frames, while AssemblyAI
        Streaming v3 accepts input chunks between 50 and 1000 ms. A final
        short tail is padded with silence to the 50 ms provider minimum.
        """
        if not 50 <= chunk_ms <= 1000:
            raise ValueError("chunk_ms must be between 50 and 1000 milliseconds")
        bytes_per_ms = ASSEMBLYAI_SAMPLE_RATE * 2 // 1000
        target_bytes = bytes_per_ms * chunk_ms
        minimum_bytes = bytes_per_ms * 50
        buffer = bytearray()
        for datagram in datagrams:
            decoded = self.decode_rtp_for_assemblyai(datagram)
            if not decoded:
                continue
            buffer.extend(decoded)
            while len(buffer) >= target_bytes:
                yield bytes(buffer[:target_bytes])
                del buffer[:target_bytes]
        if buffer:
            if len(buffer) < minimum_bytes:
                buffer.extend(b"\x00" * (minimum_bytes - len(buffer)))
            yield bytes(buffer)

    def encode_assemblyai_pcm_for_rtp(self, pcm16_16k: bytes, *, marker: bool = False) -> bytes:
        pcm8 = downsample_pcm16_16k_to_8k(pcm16_16k)
        payload = pcm16_to_ulaw(pcm8) if self.outbound_payload_type == PCMU_PAYLOAD_TYPE else pcm16_to_alaw(pcm8)
        packet = RtpPacket(self.outbound_payload_type, self.sequence, self.timestamp, self.ssrc, payload, marker)
        self.sequence = (self.sequence + 1) & 0xFFFF
        self.timestamp = (self.timestamp + len(payload)) & 0xFFFFFFFF
        return packet.to_bytes()


def _unpack_pcm16(pcm16: bytes) -> list[int]:
    if len(pcm16) % 2:
        raise ValueError("PCM16 byte length must be even")
    return [] if not pcm16 else list(struct.unpack("<" + "h" * (len(pcm16) // 2), pcm16))


def _ulaw_decode(value: int) -> int:
    encoded = (~value) & 0xFF
    sign = encoded & 0x80
    exponent = (encoded >> 4) & 0x07
    mantissa = encoded & 0x0F
    sample = ((mantissa << 3) + 0x84) << exponent
    sample -= 0x84
    return -sample if sign else sample


def _ulaw_encode(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    magnitude = min(abs(int(sample)), 32635) + 0x84
    exponent, mask = 7, 0x4000
    while exponent > 0 and not (magnitude & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def _alaw_decode(value: int) -> int:
    encoded = value ^ 0x55
    sign = encoded & 0x80
    exponent = (encoded & 0x70) >> 4
    mantissa = encoded & 0x0F
    if exponent == 0:
        sample = (mantissa << 4) + 8
    elif exponent == 1:
        sample = (mantissa << 5) + 0x108
    else:
        sample = ((mantissa << 4) + 0x108) << (exponent - 1)
    return sample if sign else -sample


def _alaw_encode(sample: int) -> int:
    value = int(sample)
    if value >= 0:
        mask = 0xD5
    else:
        mask = 0x55
        value = -value - 8
    value = min(value, 0x7FFF)
    ends = (0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF, 0x7FFF)
    segment = 0
    while segment < 8 and value > ends[segment]:
        segment += 1
    if segment >= 8:
        return 0x7F ^ mask
    encoded = segment << 4
    encoded |= ((value >> 4) if segment < 2 else (value >> (segment + 3))) & 0x0F
    return encoded ^ mask
