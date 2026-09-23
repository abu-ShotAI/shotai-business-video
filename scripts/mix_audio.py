#!/usr/bin/env python3
"""Mix a licensed music bed while preserving narration samples and video/subtitle packets."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import sys

from audio_common import (compare_packets, decode_audio, finite, loudness, probe,
    require_ffmpeg, run, sha256, stream_packets, write_float_wav, write_json)


def check_license(path, music, platform, usage):
    """Validate the recorded license evidence, not the legal truth of user declarations."""
    manifest_path = Path(path).expanduser().resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("title", "author", "license", "sha256"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Music license manifest requires {field}")
    license_id = data["license"].strip().upper()
    if re.search(r"(?:^|[-_\s])(?:NC|ND)(?:$|[-_\s])|NON.?COMMERCIAL|NO.?DERIVAT|UNKNOWN", license_id):
        raise ValueError("NC, ND and unknown licenses cannot be used by this commercial synchronization workflow")
    if license_id not in ("CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CUSTOM", "OWNED"):
        raise ValueError("Unsupported/unknown music license; verify terms and record a CUSTOM license with evidence")
    for field in ("commercial_use_allowed", "synchronization_allowed"):
        if data.get(field) is not True:
            raise ValueError(f"Music license must explicitly confirm {field}")
    if usage == "ads" and data.get("paid_ads_allowed") is not True:
        raise ValueError("Paid advertising was requested but paid_ads_allowed is not true")
    platforms = data.get("platforms")
    requested = {"douyin", "tiktok"} if platform == "both" else {platform}
    if not isinstance(platforms, list) or not requested.issubset(set(platforms)):
        raise ValueError("The license manifest does not cover the requested platform(s)")
    if data["sha256"].lower() != sha256(music):
        raise ValueError("Music file SHA-256 does not match the verified license manifest")
    if data.get("expires_on") and date.today() > date.fromisoformat(data["expires_on"]):
        raise ValueError("The recorded music license has expired")
    attribution_required = license_id.startswith("CC-BY") or data.get("attribution_required") is True
    if attribution_required and not str(data.get("attribution", "")).strip():
        raise ValueError("This license requires an attribution string for the publishing caption/credits")
    if license_id.startswith("CC"):
        if not str(data.get("license_url", "")).startswith("https://") or not str(data.get("source_url", "")).startswith("https://"):
            raise ValueError("CC music requires source_url and license_url pointing to verified license evidence")
    evidence = None
    if data.get("evidence_file"):
        evidence = Path(data["evidence_file"]).expanduser()
        if not evidence.is_absolute():
            evidence = manifest_path.parent / evidence
        if not evidence.is_file():
            raise ValueError("License evidence_file does not exist")
    if license_id in ("CUSTOM", "OWNED") and evidence is None:
        raise ValueError("CUSTOM/OWNED music requires a saved evidence_file recording the rights grant/ownership")
    return data, manifest_path, evidence


def speech_envelope(voice, rate):
    import numpy as np
    block = max(1, round(rate * 0.01))
    mono_energy = np.mean(voice.astype(np.float64) ** 2, axis=1)
    padded = np.pad(mono_energy, (0, (-len(mono_energy)) % block))
    rms = np.sqrt(padded.reshape(-1, block).mean(axis=1))
    active = (rms > 10 ** (-40 / 20)).astype(float)
    held = np.zeros_like(active)
    for i in range(len(active)):
        held[i] = np.max(active[max(0, i - 18):min(len(active), i + 5)])
    smoothed = np.zeros_like(active)
    state = 0.0
    for i, value in enumerate(held):
        tau = 0.055 if value > state else 0.35
        state += (1 - math.exp(-0.01 / tau)) * (value - state)
        smoothed[i] = state
    return np.interp(np.arange(len(voice)), np.arange(len(smoothed)) * block, smoothed), float(active.mean())


def stream_duration(stream, media):
    value = stream.get("duration")
    if value is None:
        value = media.get("format", {}).get("duration")
    if value is None or not math.isfinite(float(value)) or float(value) <= 0:
        raise ValueError("Cannot determine a finite positive video duration")
    return float(value)


def render(args):
    import numpy as np
    require_ffmpeg()
    video = Path(args.video).expanduser().resolve()
    voice_path = Path(args.voice).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if output.suffix.lower() not in (".mp4", ".mov", ".mkv"):
        raise ValueError("Output must be .mp4, .mov or .mkv")
    if not video.is_file() or not voice_path.is_file():
        raise ValueError("Video and voice must be existing local files")
    artifact_dir = output.with_name(output.stem + ".audio")
    report_path = output.with_suffix(".mix.json")
    if output.exists() or artifact_dir.exists() or report_path.exists():
        raise ValueError("Output artifacts already exist; choose a new output name")
    for key in ("music_lufs", "duck_db", "fade_in", "fade_out", "music_offset", "peak_limit"):
        if not math.isfinite(getattr(args, key)):
            raise ValueError(f"--{key.replace('_', '-')} must be finite")
    if not -50 <= args.music_lufs <= -18 or not 0 <= args.duck_db <= 18:
        raise ValueError("Use music LUFS in [-50,-18] and duck dB in [0,18]")
    if min(args.fade_in, args.fade_out, args.music_offset) < 0 or not -9 <= args.peak_limit <= -0.3:
        raise ValueError("Fades/offset must be nonnegative and peak limit between -9 and -0.3 dBTP")
    music = None if str(args.music).lower() == "none" else Path(args.music).expanduser().resolve()
    license_data = license_path = evidence = None
    if music is not None:
        if not music.is_file() or not args.music_license:
            raise ValueError("A music file requires --music-license with verified commercial synchronization rights")
        license_data, license_path, evidence = check_license(args.music_license, music, args.platform, args.usage)
    elif args.music_license:
        raise ValueError("--music-license is unnecessary when --music none")
    source_probe = probe(video)
    videos = [s for s in source_probe["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("This helper expects exactly one video stream")
    duration = stream_duration(videos[0], source_probe)
    if abs(float(videos[0].get("start_time", 0))) > 0.0001:
        raise ValueError("Video must start at time zero; normalize the timeline before mixing")
    voice, rate = decode_audio(voice_path)
    if rate not in (44100, 48000):
        raise ValueError("Use voice.py to prepare a 48 kHz master first; this mixer never resamples narration")
    if voice.shape[1] not in (1, 2):
        raise ValueError("Only mono/stereo narration is supported; no implicit downmix is performed")
    frame_count = round(duration * rate)
    if len(voice) > frame_count + 1:
        raise ValueError("Narration extends beyond the video; rebuild the timeline instead of truncating words")
    original_voice_samples = len(voice)
    # Video duration is packet/frame-derived; one-sample rounding must not truncate narration.
    frame_count = max(frame_count, len(voice))
    if voice.shape[1] == 1:
        voice_stereo = np.repeat(voice, 2, axis=1)
    else:
        voice_stereo = voice.copy()
    voice_stereo = np.pad(voice_stereo, ((0, frame_count - len(voice_stereo)), (0, 0)))
    voice_peak = float(np.max(np.abs(voice_stereo)))
    peak_ceiling = 10 ** (args.peak_limit / 20)
    if voice_peak >= peak_ceiling:
        raise ValueError("Narration alone has insufficient peak headroom; adjust its master explicitly before mixing")
    if args.fade_in + args.fade_out > duration:
        raise ValueError("Music fades overlap; shorten fade durations")
    output.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir()
    report = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "started", "source_video": str(video), "voice": str(voice_path),
        "output": str(output), "usage": args.usage, "platform": args.platform,
        "voice_sha256_before": sha256(voice_path), "source_video_sha256": sha256(video)}
    write_json(report_path, report)
    try:
        dry_path = artifact_dir / "voice_unity_stereo.wav"
        write_float_wav(dry_path, voice_stereo, rate)
        bed = np.zeros_like(voice_stereo)
        measured_music = None
        activity = 0.0
        music_gain = 0.0
        headroom_scale = 1.0
        if music is not None:
            music_duration = float(probe(music)["format"]["duration"])
            if args.music_offset >= music_duration:
                raise ValueError("Music offset lies beyond the track")
            if not args.loop_music and music_duration - args.music_offset + 1 / rate < duration:
                raise ValueError("Music excerpt is shorter than the video; choose another excerpt or explicitly --loop-music")
            bed, _ = decode_audio(music, rate=rate, channels=2, duration=frame_count / rate,
                                  offset=args.music_offset, loop=args.loop_music)
            if len(bed) < frame_count:
                # Decoder/container duration rounding may produce a tiny tail gap, never narration truncation.
                if (frame_count - len(bed)) / rate > 0.05:
                    raise ValueError("Decoded music does not cover the requested excerpt")
                bed = np.pad(bed, ((0, frame_count - len(bed)), (0, 0)))
            bed = bed[:frame_count]
            excerpt = artifact_dir / "music_excerpt.wav"
            write_float_wav(excerpt, bed, rate)
            measured_music = loudness(excerpt)
            music_i = finite(measured_music["input_i"])
            if music_i is None:
                raise ValueError("Music excerpt is silent")
            music_gain = 10 ** ((args.music_lufs - music_i) / 20)
            envelope, activity = speech_envelope(voice_stereo, rate)
            gain = music_gain * 10 ** (-args.duck_db * envelope / 20)
            fade = np.ones(frame_count)
            attack = round(args.fade_in * rate)
            release = round(args.fade_out * rate)
            if attack:
                fade[:attack] = np.sin(np.linspace(0, math.pi / 2, attack)) ** 2
            if release:
                fade[-release:] = np.cos(np.linspace(0, math.pi / 2, release)) ** 2
            bed = (bed.astype(np.float64) * gain[:, None] * fade[:, None]).astype(np.float32)
            # If peaks collide, attenuate only music. Never limit/normalize the summed voice.
            positive = bed > 0
            negative = bed < 0
            allowed = [1.0]
            if positive.any():
                allowed.append(float(np.min((peak_ceiling - voice_stereo[positive]) / bed[positive])))
            if negative.any():
                allowed.append(float(np.min((-peak_ceiling - voice_stereo[negative]) / bed[negative])))
            headroom_scale = min(allowed)
            if headroom_scale < 1:
                headroom_scale = max(0.0, headroom_scale * 0.98)
                bed *= headroom_scale
        mixed = (voice_stereo.astype(np.float64) + bed.astype(np.float64)).astype(np.float32)
        peak = float(np.max(np.abs(mixed)))
        if peak > peak_ceiling + 1e-7:
            raise ValueError("Unexpected pre-encode peak; no master limiter was applied")
        dry_read, _ = decode_audio(dry_path)
        pcm_unchanged = np.array_equal(dry_read[:original_voice_samples], voice_stereo[:original_voice_samples])
        if not pcm_unchanged:
            raise RuntimeError("Narration sample-preservation check failed")
        residual_error = float(np.max(np.abs((mixed.astype(np.float64) - bed.astype(np.float64)) - voice_stereo.astype(np.float64))))
        if residual_error > 1e-7:
            raise RuntimeError("Narration contribution differs beyond float32 addition precision")
        bed_path = artifact_dir / "music_bed.wav"
        mixed_path = artifact_dir / "mix.wav"
        write_float_wav(bed_path, bed, rate)
        write_float_wav(mixed_path, mixed, rate)
        provisional = artifact_dir / ("final" + output.suffix)
        # Copy every video/subtitle packet. Original video audio is replaced by the supplied master.
        command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", video, "-i", mixed_path,
            "-map", "0:v:0", "-map", "1:a:0", "-map", "0:s?", "-map_metadata", "0", "-map_chapters", "0",
            "-c:v", "copy", "-c:s", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", rate, "-ac", "2"]
        if output.suffix.lower() in (".mp4", ".mov"):
            command += ["-movflags", "+faststart"]
        command += [provisional]
        run(command)
        run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", provisional, "-f", "null", "-"])
        video_before = stream_packets(video, "v:0")
        video_after = stream_packets(provisional, "v:0")
        packet_preserved = compare_packets(video_before, video_after)
        if not packet_preserved:
            raise RuntimeError("Video packet contents/timestamps changed during muxing")
        subtitles_before = stream_packets(video, "s")
        subtitles_after = stream_packets(provisional, "s")
        if not compare_packets(subtitles_before, subtitles_after):
            raise RuntimeError("Embedded subtitle packets/timestamps changed during muxing")
        final_loudness = loudness(provisional)
        final_tp = finite(final_loudness["input_tp"])
        if final_tp is None or final_tp > args.peak_limit + 0.5:
            raise ValueError("AAC true peak exceeds the limit; lower the voice master explicitly or use a lower music target")
        if sha256(voice_path) != report["voice_sha256_before"]:
            raise RuntimeError("The input narration changed during mixing")
        # Sidecar subtitles are copied verbatim. Burned-in subtitles are covered by the video packet check.
        sidecars = []
        for suffix in (".srt", ".vtt", ".ass"):
            existing = video.with_suffix(suffix)
            if existing.is_file():
                target = output.with_suffix(suffix)
                if target.exists():
                    raise ValueError(f"Subtitle output already exists: {target}")
                shutil.copy2(existing, target)
                if sha256(existing) != sha256(target):
                    raise RuntimeError("Sidecar subtitle copy mismatch")
                sidecars.append({"file": str(target), "sha256": sha256(target)})
        credits = "No music used. / 未使用配乐。\n"
        if license_data:
            portable_license = dict(license_data)
            if evidence:
                evidence_copy = artifact_dir / ("license-evidence" + evidence.suffix)
                shutil.copy2(evidence, evidence_copy)
                portable_license["evidence_file"] = evidence_copy.name
                portable_license["evidence_sha256"] = sha256(evidence_copy)
            write_json(artifact_dir / "music-license.json", portable_license)
            credits = (f"{license_data['title']} — {license_data['author']}\n"
                f"{license_data['license']}\n" + str(license_data.get("attribution", "")) + "\n"
                + str(license_data.get("source_url", "")) + "\n" + str(license_data.get("license_url", "")) + "\n")
        (artifact_dir / "music-credits.txt").write_text(credits, encoding="utf-8")
        provisional.replace(output)
        report.update({"status": "complete_pending_listening", "duration_seconds": duration,
            "output_sha256": sha256(output), "full_decode_pass": True,
            "picture_bitstream_and_timestamps_unchanged": True, "video_packet_count": len(video_after),
            "embedded_subtitle_packets_and_timestamps_unchanged": True, "sidecar_subtitles": sidecars,
            "voice_input_unchanged": True, "voice_time_shift_seconds": 0,
            "voice_original_sample_count": original_voice_samples, "voice_sample_rate": rate,
            "voice_gain_per_channel": [1.0, 1.0], "voice_pan_law": "unity dual mono if mono; stereo channels unchanged",
            "voice_pcm_samples_unchanged_before_lossy_encoding": pcm_unchanged,
            "voice_contribution_max_float_error": residual_error,
            "narration_tail_trimmed": False, "voice_tail_padding_seconds": (frame_count - original_voice_samples) / rate,
            "audio_encoding_note": "AAC is lossy; PCM voice contribution is unchanged before encoding, not bit-identical inside AAC",
            "music": license_data, "music_sha256": sha256(music) if music else None,
            "music_offset_seconds": args.music_offset if music else None, "music_looped": args.loop_music if music else False,
            "music_target_lufs_before_ducking": args.music_lufs if music else None,
            "music_duck_db": args.duck_db if music else 0, "speech_activity_fraction": activity,
            "music_gain": music_gain, "music_extra_headroom_gain": headroom_scale,
            "fade_in_seconds": args.fade_in if music else 0, "fade_out_seconds": args.fade_out if music else 0,
            "pre_encode_sample_peak": peak, "final_loudness": final_loudness,
            "music_bed_loudness": loudness(bed_path) if music else None,
            "mix_master": str(mixed_path), "voice_stem": str(dry_path), "music_stem": str(bed_path),
            "credits_file": str(artifact_dir / "music-credits.txt"),
            "license_check_scope": "manifest consistency and file binding; rights evidence must be verified by the operator"})
        write_json(report_path, report)
        return report
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)[:2000]})
        write_json(report_path, report)
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", required=True)
    p.add_argument("--voice", required=True, help="Approved 44.1/48 kHz mono/stereo narration; never retimed here")
    p.add_argument("--music", default="none", help="Local licensed music file, or none")
    p.add_argument("--music-license", help="Verified license manifest JSON, required with music")
    p.add_argument("--output", required=True)
    p.add_argument("--platform", choices=["douyin", "tiktok", "both"], default="both")
    p.add_argument("--usage", choices=["organic", "ads"], default="organic")
    p.add_argument("--music-lufs", type=float, default=-30)
    p.add_argument("--duck-db", type=float, default=3.5)
    p.add_argument("--fade-in", type=float, default=0.75)
    p.add_argument("--fade-out", type=float, default=1.4)
    p.add_argument("--music-offset", type=float, default=0)
    p.add_argument("--loop-music", action="store_true", help="Explicitly loop a short track; listen to the seam")
    p.add_argument("--peak-limit", type=float, default=-1, help="dBTP ceiling; music-only attenuation preserves voice")
    return p


def main():
    try:
        result = render(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
