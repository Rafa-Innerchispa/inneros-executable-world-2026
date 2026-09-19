from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

from .adapters.assemblyai_streaming import AssemblyAIStreamingAdapter
from .audio import WavPCM16Source
from .audit import write_evidence_bundle
from .gateway import VoiceGateway


DEFAULT_OPENING_CONTEXT = (
    "InnerOS VoiceOps is listening for a building operations request. "
    "Consequential actions require explicit verbal authorization."
)


def render_agent_reply(result: dict[str, object]) -> str:
    message = str(result.get("message") or "VoiceOps processed the request.").strip()
    print(f"InnerOS: {message}")
    return message


def live_preflight(*, wav_path: str | None = None, sample_rate: int = 16000) -> dict[str, Any]:
    key_present = bool(os.getenv("ASSEMBLYAI_API_KEY"))
    sdk_present = importlib.util.find_spec("assemblyai") is not None
    report: dict[str, Any] = {
        "assemblyai_api_key_present": key_present,
        "assemblyai_sdk_present": sdk_present,
        "sample_rate": sample_rate,
        "audio_encoding": "pcm_s16le",
        "channels": 1,
        "ready_for_live_stream": key_present and sdk_present,
    }
    if wav_path:
        source = WavPCM16Source(wav_path, sample_rate=sample_rate, real_time=True)
        report["wav"] = source.validate()
        report["ready_for_live_stream"] = bool(report["ready_for_live_stream"])
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="InnerOS VoiceOps AssemblyAI live demo")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--wav", help="PCM16 mono 16 kHz WAV fixture to stream in real time")
    source.add_argument("--microphone", action="store_true", help="Use AssemblyAI MicrophoneStream")
    parser.add_argument("--preflight", action="store_true", help="Check readiness without opening a session")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk-ms", type=int, default=100)
    parser.add_argument("--evidence", default="evidence/latest_live_session.json")
    parser.add_argument("--agent-context", default=DEFAULT_OPENING_CONTEXT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.preflight:
        report = live_preflight(wav_path=args.wav, sample_rate=args.sample_rate)
        for key, value in report.items():
            print(f"{key}={value}")
        return 0 if report["ready_for_live_stream"] else 2

    if not args.wav and not args.microphone:
        raise SystemExit("Choose --wav PATH or --microphone for a live session")

    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(
        gateway,
        sample_rate=args.sample_rate,
        agent_reply_fn=render_agent_reply,
    )

    try:
        adapter.connect(agent_context=args.agent_context)
        if args.wav:
            wav_source = WavPCM16Source(
                args.wav,
                sample_rate=args.sample_rate,
                chunk_ms=args.chunk_ms,
                real_time=True,
            )
            wav_source.validate()
            gateway.evidence.add_event(
                "live_audio_source_ready",
                source_type="wav_fixture",
                path_recorded=False,
                audio_contract=adapter.audio_contract,
            )
            adapter.stream(wav_source)
        else:
            try:
                import assemblyai as aai
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("assemblyai SDK is required for microphone mode") from exc
            microphone = aai.extras.MicrophoneStream(sample_rate=args.sample_rate)
            gateway.evidence.add_event(
                "live_audio_source_ready",
                source_type="microphone",
                device_recorded=False,
                audio_contract=adapter.audio_contract,
            )
            adapter.stream(microphone)
    except KeyboardInterrupt:
        print("Stopping live VoiceOps session.")
    finally:
        adapter.close()
        evidence_path = write_evidence_bundle(gateway.evidence, Path(args.evidence))
        print(f"Evidence: {evidence_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
