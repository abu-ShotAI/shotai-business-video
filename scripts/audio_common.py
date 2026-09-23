"""Shared, local-only audio/FFmpeg helpers for the business-video skill."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess


def run(args, timeout=900):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-3000:])
    return result


def require_ffmpeg():
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            raise RuntimeError(f"{name} is required and must be on PATH")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", path]).stdout)


def finite(value):
    result = float(value)
    return result if math.isfinite(result) else None


def loudness(path, before_filter="", target=-18.0, peak=-1.5):
    filt = (before_filter + "," if before_filter else "") + (
        f"loudnorm=I={target}:TP={peak}:LRA=7:print_format=json")
    stderr = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", path, "-map", "0:a:0",
                  "-af", filt, "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.S)
    if not matches:
        raise RuntimeError("FFmpeg did not report loudness")
    return json.loads(matches[-1])


def decode_audio(path, rate=None, channels=None, duration=None, offset=0.0, loop=False):
    import numpy as np
    source = probe(path)
    stream = next((s for s in source["streams"] if s["codec_type"] == "audio"), None)
    if stream is None:
        raise ValueError(f"No audio stream: {path}")
    rate = rate or int(stream["sample_rate"])
    channels = channels or int(stream["channels"])
    args = ["ffmpeg", "-v", "error", "-nostdin"]
    if loop:
        args += ["-stream_loop", "-1"]
    args += ["-i", path]
    if offset:
        args += ["-ss", offset]
    args += ["-map", "0:a:0"]
    if duration is not None:
        args += ["-t", duration]
    args += ["-ar", rate, "-ac", channels, "-c:a", "pcm_f32le", "-f", "f32le", "-"]
    raw = run(args).stdout
    audio = np.frombuffer(raw, dtype="<f4").reshape(-1, channels).copy()
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Audio is empty or contains non-finite samples")
    return audio, rate


def write_float_wav(path, audio, rate):
    """Write float PCM without normalization, pan law or sample quantization."""
    import numpy as np
    process = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "f32le",
        "-ar", str(rate), "-ac", str(audio.shape[1]), "-i", "pipe:0",
        "-c:a", "pcm_f32le", str(path)], input=np.asarray(audio, dtype="<f4").tobytes(),
        capture_output=True, timeout=900)
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", "replace")[-3000:])


def stream_packets(path, selector):
    data = json.loads(run(["ffprobe", "-v", "error", "-select_streams", selector,
        "-show_packets", "-show_data_hash", "sha256", "-show_entries",
        "packet=pts_time,dts_time,duration_time,data_hash", "-of", "json", path]).stdout)
    return data.get("packets", [])


def compare_packets(before, after):
    if len(before) != len(after):
        return False
    for a, b in zip(before, after):
        if a.get("data_hash") != b.get("data_hash"):
            return False
        for field in ("pts_time", "dts_time", "duration_time"):
            if (field in a) != (field in b):
                return False
            if field in a and abs(float(a[field]) - float(b[field])) > 0.00002:
                return False
    return True
