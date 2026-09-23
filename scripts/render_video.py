#!/usr/bin/env python3
"""Render an evidence-backed ShotAI timeline; Pillow captions are overlaid last."""
import argparse
import concurrent.futures
import json
import math
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def run(command, log=None):
    result = subprocess.run([str(value) for value in command], capture_output=True, text=True)
    if log:
        Path(log).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result.stdout


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))


def resolve(value, base):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def json_file(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finite(value, label, minimum=0):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number.")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{label} must be finite and >= {minimum}.")
    return number


def payloads(value, allow_cached=False):
    """Unwrap native MCP content and structuredContent without assuming tool fields."""
    if isinstance(value, dict):
        yield value
        if value.get("isError") is True or value.get("success") is False:
            raise ValueError("Export record reports a failed MCP operation.")
        if value.get("ok") is False:
            raise ValueError("Export record wrapper reports a failed MCP operation.")
        if isinstance(value.get("evidence"), dict) and value["evidence"].get("cache_used") is True and not allow_cached:
            raise ValueError("Export record reports cached evidence; use a current-task MCP export.")
        if "result" in value:
            yield from payloads(value["result"], allow_cached)
        if "structuredContent" in value:
            yield from payloads(value["structuredContent"], allow_cached)
        for entry in value.get("content", []):
            if isinstance(entry, dict) and entry.get("type") == "text":
                try:
                    nested = json.loads(entry.get("text", ""))
                except json.JSONDecodeError:
                    continue
                yield from payloads(nested, allow_cached)
    elif isinstance(value, list):
        for entry in value:
            yield from payloads(entry, allow_cached)


def verify_export(shot, base, allow_cached=False):
    record_path = resolve(shot["export_record"], base)
    if not record_path.is_file():
        raise ValueError(f"Export record does not exist: {record_path}")
    record = json_file(record_path)
    raw_path = record_path
    if isinstance(record, dict) and "tool_result_path" in record:
        for key in ("shot_id", "collection_id", "file", "original_start"):
            if key not in record:
                raise ValueError(f"Normalized export record lacks {key}: {record_path}")
        if str(record["shot_id"]) != str(shot["shot_id"]) or str(record["collection_id"]) != str(shot["collection_id"]):
            raise ValueError("Normalized export record IDs disagree with the timeline.")
        if resolve(record["file"], record_path.parent) != shot["source_path"]:
            raise ValueError("Normalized export record file disagrees with the timeline.")
        finite(record["original_start"], "original_start")
        raw_path = resolve(record["tool_result_path"], record_path.parent)
        if not raw_path.is_file() or raw_path == record_path:
            raise ValueError("Normalized export record needs a separate original MCP tool-result JSON.")
        record = json_file(raw_path)
    records = list(payloads(record, allow_cached))
    recorded_at = [payload["recorded_at"] for payload in records if "recorded_at" in payload]
    cache_used = any(isinstance(payload.get("evidence"), dict) and payload["evidence"].get("cache_used") is True
                     for payload in records)
    exports = [entry for payload in records for entry in payload.get("exportedFiles", []) if isinstance(entry, dict)]
    for entry in exports:
        file_path = entry.get("filePath", entry.get("file"))
        if str(entry.get("shotId", entry.get("shot_id", ""))) != str(shot["shot_id"]) or not file_path:
            continue
        if resolve(file_path, raw_path.parent) != shot["source_path"]:
            continue
        collection = entry.get("collectionId", entry.get("collection_id"))
        if collection is not None and str(collection) != str(shot["collection_id"]):
            raise ValueError("MCP export collection does not match the timeline.")
        return {"record": str(record_path), "raw_tool_result": str(raw_path), "shot_source_match": True,
                "collection_verified_in_export": collection is not None,
                "collection_id": str(shot["collection_id"]), "cache_used": cache_used,
                "original_recorded_at": recorded_at,
                "provenance_mode": "user_authorized_cached" if allow_cached else "live_required"}
    raise ValueError(f"Source/shot_id pair is absent from exportedFiles in {raw_path}.")


def has_han(text):
    return any(0x3400 <= ord(char) <= 0x9FFF or 0x20000 <= ord(char) <= 0x3134F for char in text)


def discover_font(explicit, text):
    if explicit:
        font = Path(explicit).expanduser().resolve()
        if not font.is_file():
            raise ValueError(f"Font not found: {font}")
        return font
    cjk = has_han(text)
    if shutil.which("fc-match"):
        query = "sans:lang=zh-cn" if cjk else "sans"
        found = run(["fc-match", "-f", "%{file}\n", query]).splitlines()
        if found and Path(found[0]).is_file():
            return Path(found[0])
    candidates = (["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
                   "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"] if cjk else
                  ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates += [str(windows / filename) for filename in (["msyh.ttc", "simhei.ttf"] if cjk else ["arial.ttf", "segoeui.ttf"])]
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate)
    raise ValueError("No suitable font was found. Pass --font with a font supporting all caption characters.")


def text_units(text):
    """Keep every Latin word intact; allow breaks between Han characters."""
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)*|[\u3400-\u9fff]|[^\s]|[ \t]+", text, re.UNICODE)


def wrap_text(text, draw, font, max_width, stroke):
    lines = []
    # Split Han before applying the whole-word tokenizer.
    for paragraph in text.split("\n"):
        units = []
        for part in re.split(r"([\u3400-\u9fff])", paragraph):
            if part:
                units.extend([part] if len(part) == 1 and has_han(part) else text_units(part))
        current = ""
        for unit in units:
            candidate = (current + unit).rstrip()
            box = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke)
            if box[2] - box[0] <= max_width:
                current += unit
                continue
            if not current.strip():
                raise ValueError("A complete caption word exceeds the safe width.")
            lines.append(current.strip())
            current = unit.lstrip()
            box = draw.textbbox((0, 0), current, font=font, stroke_width=stroke)
            if box[2] - box[0] > max_width:
                raise ValueError("A complete caption word exceeds the safe width.")
        if current.strip():
            lines.append(current.strip())
    return lines


def caption_card(text, width, height, font_path, style):
    left = int(style.get("left_margin", width * 0.06))
    right = int(style.get("right_margin", width * (0.14 if height > width else 0.06)))
    bottom = int(style.get("bottom_margin", height * (0.22 if height > width else 0.10)))
    base_size = int(style.get("font_size", width * (0.052 if height > width else 0.026)))
    minimum = int(style.get("min_font_size", max(12, base_size * 0.78)))
    max_lines = int(style.get("max_lines", 2))
    stroke = int(style.get("stroke_width", max(1, base_size * 0.055)))
    if min(left, right, bottom, stroke) < 0 or minimum <= 0 or base_size < minimum or max_lines < 1 or left + right >= width:
        raise ValueError("Invalid caption_style margins, sizes or line count.")
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if not text:
        return image, {"lines": [], "bounds": None}
    draw = ImageDraw.Draw(image)
    for size in range(base_size, minimum - 1, -1):
        font = ImageFont.truetype(str(font_path), size, index=int(style.get("font_index", 0)))
        missing_mask = font.getmask("\U0010ffff")
        missing_signature = (missing_mask.size, bytes(missing_mask))
        for char in set(text):
            if char.isspace():
                continue
            mask = font.getmask(char)
            if (mask.size, bytes(mask)) == missing_signature:
                raise ValueError(f"Font lacks caption character {char!r}. Select a compatible --font.")
        try:
            lines = wrap_text(text, draw, font, width - left - right, stroke)
        except ValueError:
            continue
        if lines and len(lines) <= max_lines:
            break
    else:
        raise ValueError(f"Caption does not fit {max_lines} lines without splitting words: {text!r}. Shorten phrase boundaries.")
    boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke) for line in lines]
    line_height = max(box[3] - box[1] for box in boxes)
    gap = max(4, round(size * 0.24))
    total_height = len(lines) * line_height + (len(lines) - 1) * gap
    top = height - bottom - total_height
    if top < 0:
        raise ValueError("Caption region extends above the frame.")
    for number, (line, box) in enumerate(zip(lines, boxes)):
        x = left + (width - left - right - (box[2] - box[0])) / 2 - box[0]
        y = top + number * (line_height + gap) - box[1]
        draw.text((x, y), line, font=font, fill="white", stroke_width=stroke, stroke_fill=(0, 0, 0, 230))
    bounds = image.getbbox()
    if bounds is None or bounds[0] < left or bounds[2] > width - right or bounds[1] < 0 or bounds[3] > height - bottom + 1:
        raise ValueError("Caption pixels are outside the configured safe region.")
    return image, {"lines": lines, "bounds": bounds, "font_size": size,
                   "safe_region": [left, 0, width - right, height - bottom]}


def video_properties(info):
    streams = [stream for stream in info.get("streams", []) if stream.get("codec_type") == "video"]
    if not streams:
        raise ValueError("Source has no video stream.")
    stream = streams[0]
    duration = finite(stream.get("duration", info.get("format", {}).get("duration")), "source duration", 0.001)
    rotation = float(stream.get("tags", {}).get("rotate", 0))
    for side in stream.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    width, height = int(stream["width"]), int(stream["height"])
    if round(abs(rotation)) % 180 == 90:
        width, height = height, width
    return stream, duration, width, height


def prepare(data, base, allow_cached=False):
    width, height, fps = data.get("width", 1080), data.get("height", 1920), data.get("fps", 30)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (width, height, fps)):
        raise ValueError("width, height, fps must be integers.")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("Dimensions must be even and >=64, fps must be 1..120.")
    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Timeline shots must be a nonempty list.")
    source_info, prepared, cursor = {}, [], 0
    for index, item in enumerate(shots, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Shot {index} must be an object.")
        for key in ("source", "in", "duration", "shot_id", "collection_id", "export_record", "fit"):
            if key not in item or item[key] is None or item[key] == "":
                raise ValueError(f"Shot {index} lacks required {key}.")
        shot = dict(item)
        shot["source_path"] = resolve(shot["source"], base)
        if not shot["source_path"].is_file():
            raise ValueError(f"Source missing: {shot['source_path']}")
        start, duration = finite(shot["in"], "in"), finite(shot["duration"], "duration", 1 / fps)
        frames = math.floor(duration * fps + 0.5)
        actual_duration = frames / fps
        shot.update(index=index, start_frame=cursor, frames=frames, actual_duration=actual_duration, source_in=start)
        cursor += frames
        if shot["source_path"] not in source_info:
            source_info[shot["source_path"]] = video_properties(probe(shot["source_path"]))
        stream, source_duration, source_width, source_height = source_info[shot["source_path"]]
        if start + actual_duration > source_duration + 0.001:
            raise ValueError(f"Shot {index} requests {start + actual_duration:.6f}s of a {source_duration:.6f}s source.")
        if shot["fit"] not in ("cover", "contain"):
            raise ValueError("fit must be cover or contain.")
        if shot["fit"] == "cover":
            if shot.get("crop_reviewed") is not True or any(key not in shot for key in ("focus_x", "focus_y")):
                raise ValueError(f"Shot {index} cover requires focus_x/focus_y and crop_reviewed:true after visual inspection.")
            for key in ("focus_x", "focus_y"):
                if not 0 <= finite(shot[key], key) <= 1:
                    raise ValueError(f"{key} must be 0..1.")
        evidence = verify_export(shot, base, allow_cached)
        shot.update(evidence=evidence, source_duration=source_duration, source_width=source_width, source_height=source_height)
        prepared.append(shot)
    raw_captions = data.get("captions", [])
    if not isinstance(raw_captions, list):
        raise ValueError("captions must be a list.")
    captions = []
    last_end = 0.0
    for index, caption in enumerate(raw_captions, 1):
        if not isinstance(caption, dict) or not isinstance(caption.get("text"), str) or not caption["text"].strip():
            raise ValueError(f"Caption {index} needs text.")
        start, end = finite(caption["start"], "caption start"), finite(caption["end"], "caption end")
        if end <= start or start < last_end - 0.000001 or end > cursor / fps + 0.000001:
            raise ValueError(f"Caption {index} overlaps, is unordered, empty, or extends beyond the timeline.")
        if math.floor(end * fps + 0.5) <= math.floor(start * fps + 0.5):
            raise ValueError(f"Caption {index} is shorter than one output frame.")
        captions.append({**caption, "start": start, "end": end})
        last_end = end
    return width, height, fps, cursor, prepared, captions


def srt_time(value):
    hour, rest = divmod(round(value * 1000), 3_600_000)
    minute, rest = divmod(rest, 60_000)
    second, ms = divmod(rest, 1000)
    return f"{hour:02}:{minute:02}:{second:02},{ms:03}"


def check_video(path, frames, width, height, fps):
    info = probe(path)
    stream = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
    if int(stream["width"]) != width or int(stream["height"]) != height:
        raise RuntimeError(f"Wrong rendered dimensions: {path}")
    if Fraction(stream["avg_frame_rate"]) != fps or int(stream.get("nb_frames", -1)) != frames:
        raise RuntimeError(f"Wrong rendered frame count/rate: {path}")
    if abs(float(stream["duration"]) - frames / fps) > 1 / fps + 0.002:
        raise RuntimeError(f"Wrong rendered video duration: {path}")
    return info


def render(args):
    for program in ("ffmpeg", "ffprobe"):
        if not shutil.which(program):
            raise ValueError(f"Required program is unavailable: {program}")
    data, base = json_file(args.timeline), args.timeline.resolve().parent
    width, height, fps, total_frames, shots, captions = prepare(data, base, args.allow_cached_evidence)
    output = args.output.expanduser().resolve()
    work = (args.work_dir.expanduser().resolve() if args.work_dir else output.parent / (output.stem + "_render_work"))
    voice = resolve(data["voice_file"], base) if data.get("voice_file") else None
    protected = {args.timeline.resolve(), *[shot["source_path"] for shot in shots]}
    if voice:
        protected.add(voice)
    protected.update(Path(shot["evidence"][key]) for shot in shots for key in ("record", "raw_tool_result"))
    srt = output.with_suffix(".srt")
    report_path = args.report.resolve() if args.report else output.with_suffix(".render_report.json")
    if output in protected:
        raise ValueError("Output must not overwrite an input.")
    if srt in protected or report_path in protected or report_path in {output, srt}:
        raise ValueError("SRT/report paths must not overwrite inputs or the rendered video.")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must use the .mp4 extension.")
    if output.parent == work:
        raise ValueError("Put the final output outside --work-dir.")
    if any(path.parent == work for path in protected):
        raise ValueError("Use a dedicated --work-dir containing no timeline, source, voice, or evidence input.")
    if output.exists() and not args.overwrite:
        raise ValueError("Output exists. Choose a new filename or pass --overwrite.")
    if args.mux_voice:
        if not voice or not voice.is_file():
            raise ValueError("--mux-voice requires an existing timeline voice_file.")
        info = probe(voice)
        if not any(stream["codec_type"] == "audio" for stream in info["streams"]):
            raise ValueError("voice_file has no audio stream.")
        audio_duration = float(info["format"]["duration"])
        if audio_duration > total_frames / fps + 0.001:
            raise ValueError("Timeline is shorter than narration; extend the shot plan instead of truncating speech.")
    output.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    font = discover_font(args.font, "".join(caption["text"] for caption in captions)) if captions else None
    style = data.get("caption_style", {})
    cards, caption_reports = {}, []
    for index, caption in enumerate(captions, 1):
        card, report = caption_card(caption["text"], width, height, font, style)
        card_path = work / f"caption_{index:03d}.png"
        card.save(card_path)
        cards[index] = card_path
        caption_reports.append({"index": index, "text": caption["text"], **report, "image": str(card_path)})
    def segment(shot):
        path = work / f"shot_{shot['index']:04d}.mp4"
        filters = ["scale=trunc(iw*sar/2)*2:ih", "setsar=1"]
        if shot["fit"] == "cover":
            filters += [f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos",
                        f"crop={width}:{height}:(iw-ow)*{float(shot['focus_x']):.8f}:(ih-oh)*{float(shot['focus_y']):.8f}"]
        else:
            filters += [f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos",
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"]
        filters += ["setsar=1", f"fps={fps}", f"trim=end_frame={shot['frames']}", "setpts=PTS-STARTPTS", "format=yuv420p"]
        run(["ffmpeg", "-v", "warning", "-y", "-threads", "2", "-filter_threads", "1",
             "-ss", shot["source_in"], "-i", shot["source_path"], "-an", "-sn", "-dn",
             "-vf", ",".join(filters), "-frames:v", shot["frames"], "-c:v", "libx264",
             "-preset", args.preset, "-crf", args.crf, "-threads", "2", "-video_track_timescale", fps * 1000,
             "-map_metadata", "-1", path], work / f"shot_{shot['index']:04d}.log")
        check_video(path, shot["frames"], width, height, fps)
        return path
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        paths = list(pool.map(segment, shots))
    concat = work / "segments.ffconcat"
    # Relative generated filenames avoid concat path quoting and Unicode ambiguities.
    concat.write_text("ffconcat version 1.0\n" + "".join(f"file '{path.name}'\n" for path in paths), encoding="utf-8")
    joined = work / "joined.mp4"
    run(["ffmpeg", "-v", "warning", "-y", "-f", "concat", "-safe", "1", "-i", concat, "-an", "-c:v", "copy", joined], work / "concat.log")
    check_video(joined, total_frames, width, height, fps)
    ranges, cursor = [], 0
    for index, caption in enumerate(captions, 1):
        start, end = math.floor(caption["start"] * fps + 0.5), math.floor(caption["end"] * fps + 0.5)
        if start > cursor:
            ranges.append((None, start - cursor))
        ranges.append((index, end - start))
        cursor = end
    if cursor < total_frames:
        ranges.append((None, total_frames - cursor))
    if sum(count for _, count in ranges) != total_frames:
        raise RuntimeError("Caption frame schedule is inconsistent.")
    temp_output = work / "final.pending.mp4"
    command = ["ffmpeg", "-v", "warning", "-y", "-threads", "2", "-filter_complex_threads", "1",
               "-i", str(joined), "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{width}x{height}",
               "-framerate", str(fps), "-i", "pipe:0"]
    if args.mux_voice:
        command += ["-i", str(voice)]
    command += ["-filter_complex", "[0:v][1:v]overlay=shortest=1:format=auto,format=yuv420p[v]", "-map", "[v]"]
    if args.mux_voice:
        command += ["-map", "2:a:0", "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        command += ["-an"]
    command += ["-frames:v", str(total_frames), "-t", f"{total_frames / fps:.9f}", "-c:v", "libx264",
                "-preset", args.preset, "-crf", str(args.crf), "-threads", "2", "-video_track_timescale", str(fps * 1000),
                "-movflags", "+faststart", "-map_metadata", "-1", str(temp_output)]
    blank = bytes(width * height * 4)
    with (work / "final.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        try:
            for index, count in ranges:
                if index is None:
                    pixels = blank
                else:
                    with Image.open(cards[index]) as card:
                        pixels = card.convert("RGBA").tobytes()
                for _ in range(count):
                    process.stdin.write(pixels)
            process.stdin.close()
            if process.wait():
                raise RuntimeError((work / "final.log").read_text(encoding="utf-8")[-6000:])
        except BaseException:
            process.kill()
            process.wait()
            raise
    info = check_video(temp_output, total_frames, width, height, fps)
    run(["ffmpeg", "-v", "error", "-xerror", "-i", temp_output, "-f", "null", "-"], work / "decode.log")
    os.replace(temp_output, output)
    srt.write_text("\n\n".join(f"{index}\n{srt_time(caption['start'])} --> {srt_time(caption['end'])}\n{caption['text']}"
                                for index, caption in enumerate(captions, 1)) + ("\n" if captions else ""), encoding="utf-8")
    report = {"output": str(output), "width": width, "height": height, "fps": fps, "total_frames": total_frames,
              "duration": total_frames / fps, "container_duration": float(info["format"]["duration"]),
              "audio_mode": "narration_only" if args.mux_voice else "silent", "music_mixed": False,
              "provenance_mode": "user_authorized_cached" if args.allow_cached_evidence else "live_required",
              "full_decode_pass": True, "font": str(font) if font else None, "captions": caption_reports,
              "srt": str(srt), "work_dir": str(work),
              "shots": [{"index": shot["index"], "shot_id": shot["shot_id"], "collection_id": shot["collection_id"],
                         "source": str(shot["source_path"]), "in": shot["source_in"], "requested_duration": shot["duration"],
                         "rendered_duration": shot["actual_duration"], "frames": shot["frames"],
                         "start_frame": shot["start_frame"], "fit": shot["fit"],
                         "focus_x": shot.get("focus_x"), "focus_y": shot.get("focus_y"), "evidence": shot["evidence"]} for shot in shots],
              "review_note": "Export/source IDs are checked. Agent must separately verify collection membership and that current-task MCP evidence and crop_reviewed reflect live retrieval and visual inspection."}
    write_json(report_path, report)
    print(json.dumps({"output": str(output), "report": str(report_path), "duration": total_frames / fps,
                      "audio_mode": report["audio_mode"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", help="Explicit font file supporting all caption characters")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mux-voice", action="store_true", help="Mux narration only; default output is silent for mix_audio")
    parser.add_argument("--allow-cached-evidence", action="store_true",
                        help="Use cached exports only after the user explicitly chooses offline mode; label the output report")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--preset", default="fast", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"])
    parser.add_argument("--crf", type=int, default=19)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if not 1 <= args.jobs <= 8 or not 0 <= args.crf <= 40:
            raise ValueError("jobs must be 1..8 and crf 0..40.")
        render(args)
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
        print(f"Render failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
