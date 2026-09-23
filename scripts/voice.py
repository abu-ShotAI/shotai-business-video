#!/usr/bin/env python3
"""Generate a continuous voice take or process an existing recording. No automatic retries."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from audio_common import finite, loudness, probe, require_ffmpeg, run, sha256, write_json

QWEN_BASE = "https://qwen-qwen3-tts.hf.space"
QUOTA_WORDS = re.compile(r"quota|rate.?limit|too many requests|zerogpu.*(?:exceeded|limit)|配额|额度", re.I)


class QuotaError(RuntimeError):
    """Stop this run; do not switch accounts, providers or split requests to bypass quota."""


def service_error(value):
    message = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if QUOTA_WORDS.search(message):
        raise QuotaError(message[:1200])
    raise RuntimeError(message[:1200])


def http(url, payload=None, timeout=60, limit=8 * 1024 * 1024):
    headers = {"User-Agent": "shotai-business-video/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        started = time.monotonic()
        # Socket inactivity is capped at 30 s; the overall body deadline is also bounded.
        # read1 returns available bytes, so periodic SSE heartbeats cannot extend this indefinitely.
        with urllib.request.urlopen(request, timeout=min(timeout, 30)) as response:
            chunks = []
            size = 0
            is_sse = "text/event-stream" in response.headers.get("Content-Type", "")
            while True:
                if time.monotonic() - started > timeout:
                    raise TimeoutError("Service response exceeded its total time budget; no retry was sent")
                chunk = response.read1(min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise RuntimeError("Service response exceeded the configured size limit")
                if is_sse:
                    current = b"".join(chunks).replace(b"\r\n", b"\n")
                    # Return on a fully framed terminal event even if the service keeps the socket open.
                    if re.search(rb"event: (?:error|complete)\n(?:[^\n]*\n)*\n", current):
                        break
            return b"".join(chunks)
    except urllib.error.HTTPError as exc:
        message = exc.read(1200).decode("utf-8", "replace")
        if exc.code == 429 or QUOTA_WORDS.search(message):
            raise QuotaError(f"HTTP {exc.code}: {message}") from exc
        raise RuntimeError(f"HTTP {exc.code}: {message}") from exc


def parse_qwen_events(events):
    """Parse a complete Gradio SSE response. Public for offline service-fixture tests."""
    for block in re.split(r"\r?\n\r?\n", events):
        event = ""
        data = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
        if event in ("error", "complete"):
            raw = "\n".join(data)
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                service_error(raw or "Malformed service response")
            if event == "error":
                service_error(value)
            if not isinstance(value, list) or not value or not isinstance(value[0], dict) or not value[0].get("url"):
                service_error(value)
            return value[0]["url"], value[1:]
    # Explicit quota messages take precedence even when the SSE framing is incomplete.
    service_error(events[-1200:] or "Service did not return a completed take")


def qwen_info(transport=http):
    data = json.loads(transport(QWEN_BASE + "/gradio_api/info"))
    endpoint = data.get("named_endpoints", {}).get("/generate_custom_voice")
    if not endpoint:
        raise RuntimeError("Official demo CustomVoice endpoint is unavailable; do not substitute another model")
    parameters = endpoint.get("parameters", [])
    expected = ["text", "language", "speaker", "instruct", "model_size"]
    if [p.get("parameter_name") for p in parameters] != expected:
        raise RuntimeError("Official demo schema changed; inspect its live API before updating this adapter")
    return {p["parameter_name"]: p.get("type", {}).get("enum") for p in parameters}


def synth_qwen(text, settings, destination, work, transport=http):
    info = qwen_info(transport)
    language = {"zh": "Chinese", "en": "English"}[settings["lang"]]
    for name, value in (("speaker", settings["voice"]), ("language", language), ("model_size", settings["model_size"])):
        if value not in (info.get(name) or []):
            raise ValueError(f"Unsupported current demo {name}: {value}; inspect --list-voices")
    request = {"data": [text, language, settings["voice"], settings["instruction"], settings["model_size"]]}
    write_json(work / "request.json", request)
    submission = json.loads(transport(QWEN_BASE + "/gradio_api/call/generate_custom_voice", payload=request))
    event_id = submission.get("event_id")
    if not isinstance(event_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", event_id):
        service_error(submission)
    write_json(work / "submission.json", submission)
    # One POST and one bounded wait. No retries and no submission after a quota error.
    events = transport(QWEN_BASE + "/gradio_api/call/generate_custom_voice/" + event_id, timeout=420).decode("utf-8")
    (work / "events.txt").write_text(events, encoding="utf-8")
    url, status = parse_qwen_events(events)
    # Only download the audio artifact from the same official service.
    if urllib.parse.urlsplit(url).scheme != "https" or urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(QWEN_BASE).netloc:
        raise RuntimeError("Demo returned an unexpected audio host; inspect it before downloading")
    destination.write_bytes(transport(url, timeout=120, limit=64 * 1024 * 1024))
    return {"endpoint": QWEN_BASE, "model": "Qwen3-TTS-12Hz-" + settings["model_size"] + "-CustomVoice",
            "status": status, "generation_requests": 1}


async def edge_voices():
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts is not installed in this Python environment") from exc
    return await edge_tts.list_voices()


async def synth_edge(text, settings, destination):
    import edge_tts
    voices = await edge_voices()
    matches = [v for v in voices if v.get("ShortName") == settings["voice"]]
    if not matches or not matches[0].get("Locale", "").startswith(settings["lang"] + "-"):
        raise ValueError("The chosen Edge voice is unavailable or has a different language; run --list-voices")
    await edge_tts.Communicate(text, settings["voice"], rate=settings["rate"]).save(str(destination))
    return {"voice_verified_online": matches[0], "generation_requests": 1,
            "note": "edge-tts may internally stream chunks; this script submits the complete text once"}


def edge_trim_filter(raw, threshold=-55.0, head=0.08, tail=0.15):
    """Optional edge-only silence trim with retained guards. Never removes internal pauses."""
    duration = float(probe(raw)["format"]["duration"])
    log = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", raw, "-af",
        f"silencedetect=noise={threshold}dB:d=0.10", "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
    start = max(0.0, ends[0] - head) if starts and ends and starts[0] <= 0.001 else 0.0
    end = max(start, starts[-1] + tail) if starts and ends and abs(ends[-1] - duration) < 0.02 else duration
    end = min(end, duration)
    if end <= start + 0.1:
        raise ValueError("Recording is silent or too short after conservative edge trimming")
    return f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS", {
        "enabled": True, "start_removed_seconds": start, "end_removed_seconds": duration - end,
        "threshold_dbfs": threshold, "head_guard_seconds": head, "tail_guard_seconds": tail,
        "requires_listening_review": True}


def settings_from_args(args):
    previous = {}
    if args.selection:
        source = json.loads(Path(args.selection).read_text(encoding="utf-8"))
        previous = source.get("settings", source)
    defaults = {"lang": "zh", "rate": "+0%", "tempo": 1.0, "instruction": "", "model_size": "1.7B"}
    settings = {}
    for name in ("provider", "voice", "lang", "rate", "tempo", "instruction", "model_size"):
        explicit = getattr(args, name)
        if name in ("provider", "voice", "lang", "instruction", "model_size") and name in previous and explicit is not None and explicit != previous[name]:
            raise ValueError(f"--{name.replace('_', '-')} differs from the selected take; make a new explicit voice selection")
        settings[name] = explicit if explicit is not None else previous.get(name, defaults.get(name))
    if settings["provider"] not in ("edge", "qwen-demo", "existing"):
        raise ValueError("Choose --provider edge|qwen-demo|existing or provide --selection")
    if settings["provider"] != "existing" and not settings["voice"]:
        raise ValueError("Choose --voice after auditioning; no universal default voice is imposed")
    if not re.fullmatch(r"[+-]\d+%", settings["rate"]) or not -50 <= int(settings["rate"][:-1]) <= 100:
        raise ValueError("--rate must be a signed percentage between -50% and +100%")
    if settings["provider"] != "edge" and settings["rate"] != "+0%":
        raise ValueError("Native --rate is supported by Edge only; use --tempo for Qwen or existing recordings")
    if settings["lang"] not in ("zh", "en") or settings["model_size"] not in ("0.6B", "1.7B"):
        raise ValueError("Unsupported language or Qwen model size in selection")
    if settings["instruction"] and settings["provider"] != "qwen-demo":
        raise ValueError("--instruction is supported by Qwen CustomVoice only")
    if settings["provider"] == "qwen-demo" and settings["model_size"] == "0.6B" and settings["instruction"]:
        raise ValueError("Style instructions require Qwen CustomVoice 1.7B; 0.6B does not support them")
    if not math.isfinite(settings["tempo"]) or not 0.5 <= settings["tempo"] <= 2:
        raise ValueError("--tempo must be between 0.5 and 2.0")
    return settings


def process(args):
    require_ffmpeg()
    if not args.output:
        raise ValueError("--output is required")
    output = Path(args.output).expanduser().resolve()
    if output.suffix.lower() != ".wav":
        raise ValueError("--output must be a WAV master; generate previews from the master separately")
    report_path = output.with_suffix(".voice.json")
    work = output.with_name(output.stem + ".voice-work")
    if output.exists() or report_path.exists() or work.exists():
        raise ValueError("Output or working take already exists; use a new output name to preserve previous selections")
    settings = settings_from_args(args)
    if not -35 <= args.target_lufs <= -10 or not -9 <= args.true_peak <= -1:
        raise ValueError("Use target LUFS in [-35, -10] and true peak in [-9, -1] dBTP")
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else None
    if settings["provider"] != "existing" and (not text or not text.strip()):
        raise ValueError("--text-file containing the approved full text is required for synthesis")
    if settings["provider"] == "existing" and not args.input:
        raise ValueError("--input is required with --provider existing")
    if settings["provider"] != "existing" and args.input:
        raise ValueError("--input is supported by existing only")
    if text and len(text) > 16000:
        raise ValueError("This helper handles short business-video narration; text exceeds 16,000 characters")
    output.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir()
    report = {"schema_version": 1, "stage": args.stage, "settings": settings,
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "started",
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None,
        "text_character_count": len(text) if text is not None else None,
        "retry_policy": "one generation request; stop on any service error, especially quota",
        "text_modified": False, "output": str(output)}
    write_json(report_path, report)
    raw = work / ("raw.mp3" if settings["provider"] == "edge" else "raw.wav")
    try:
        if settings["provider"] == "existing":
            raw = Path(args.input).expanduser().resolve()
            if not raw.is_file():
                raise ValueError("Input recording does not exist")
            source = {"provider": "existing", "generation_requests": 0}
        elif settings["provider"] == "edge":
            source = asyncio.run(asyncio.wait_for(synth_edge(text, settings, raw), timeout=420))
        else:
            source = synth_qwen(text, settings, raw, work)
        raw_probe = probe(raw)
        raw_audio = next(s for s in raw_probe["streams"] if s["codec_type"] == "audio")
        channels = int(raw_audio["channels"])
        if channels not in (1, 2):
            raise ValueError("Only mono and stereo narration are supported")
        filters = []
        trimming = {"enabled": False, "start_removed_seconds": 0, "end_removed_seconds": 0}
        if args.trim_edge_silence:
            filt, trimming = edge_trim_filter(raw)
            filters.append(filt)
        if settings["tempo"] != 1:
            filters.append(f"atempo={settings['tempo']}")
        before_filter = ",".join(filters)
        measured = loudness(raw, before_filter, args.target_lufs, args.true_peak)
        if finite(measured["input_i"]) is None:
            raise ValueError("Narration has no measurable speech/audio")
        if not args.no_normalize:
            filters.append(f"loudnorm=I={args.target_lufs}:TP={args.true_peak}:LRA=7:linear=true:"
                f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                f"offset={measured['target_offset']}")
        temporary = work / "master.wav"
        command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", raw, "-map", "0:a:0"]
        if filters:
            command += ["-af", ",".join(filters)]
        command += ["-ar", "48000", "-ac", channels, "-c:a", "pcm_s24le", temporary]
        run(command)
        run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", temporary, "-f", "null", "-"])
        final = loudness(temporary)
        if finite(final["input_tp"]) is None or float(final["input_tp"]) >= 0:
            raise ValueError("Output clips or is silent; inspect the raw take")
        temporary.replace(output)
        report.update({"status": "audio_ready_pending_listening_and_text_check", "source": source,
            "raw_file": str(raw), "raw_sha256": sha256(raw), "sha256": sha256(output),
            "duration_seconds": float(probe(output)["format"]["duration"]),
            "raw_duration_seconds": float(raw_probe["format"]["duration"]),
            "pitch_preserved": True, "synthesis_mode": "complete_text_one_request" if settings["provider"] != "existing" else "existing_recording",
            "trimming": trimming, "normalization": {"enabled": not args.no_normalize,
                "target_lufs": args.target_lufs, "true_peak_limit_dbtp": args.true_peak,
                "measured_before": measured, "measured_after": final},
            "audio_format": {"sample_rate": 48000, "channels": channels, "codec": "pcm_s24le"},
            "full_decode_pass": True, "review_required": ["first sentence pace", "complete approved text", "last word and tail", "pronunciation"]})
        write_json(report_path, report)
        return report
    except Exception as exc:
        report.update({"status": "quota_exhausted" if isinstance(exc, QuotaError) else "failed", "error": str(exc)[:2000],
                       "automatic_retry": False, "voice_fallback": False})
        write_json(report_path, report)
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--provider", choices=["edge", "qwen-demo", "existing"])
    p.add_argument("--text-file")
    p.add_argument("--input", help="Existing audio, used only by the existing provider")
    p.add_argument("--output", help="New .wav master")
    p.add_argument("--voice", help="Exact provider voice ID, validated against the live catalog")
    p.add_argument("--lang", choices=["zh", "en"])
    p.add_argument("--rate", help="Edge native signed percentage, e.g. +10%%; use --rate=-10%% for negative")
    p.add_argument("--tempo", type=float, help="Pitch-preserving postprocessing multiplier; default 1.0")
    p.add_argument("--instruction", help="Qwen CustomVoice delivery instruction")
    p.add_argument("--model-size", choices=["0.6B", "1.7B"])
    p.add_argument("--selection", help="Prior audition .voice.json; keeps provider/voice/language/style")
    p.add_argument("--stage", choices=["audition", "full"], default="full")
    p.add_argument("--target-lufs", type=float, default=-18)
    p.add_argument("--true-peak", type=float, default=-1.5)
    p.add_argument("--no-normalize", action="store_true")
    p.add_argument("--trim-edge-silence", action="store_true", help="Opt-in conservative head/tail silence trim; listen afterwards")
    p.add_argument("--list-voices", action="store_true", help="Query the selected provider live; no synthesis")
    return p


def main():
    args = parser().parse_args()
    try:
        if args.list_voices:
            if args.provider == "edge":
                voices = asyncio.run(edge_voices())
                result = [v for v in voices if not args.lang or v.get("Locale", "").startswith(args.lang + "-")]
            elif args.provider == "qwen-demo":
                result = qwen_info()
            else:
                raise ValueError("--list-voices requires --provider edge or qwen-demo")
        else:
            result = process(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "quota_exhausted": isinstance(exc, QuotaError), "retried": False}, ensure_ascii=False), file=sys.stderr)
        return 3 if isinstance(exc, QuotaError) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
