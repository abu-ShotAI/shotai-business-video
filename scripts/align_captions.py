#!/usr/bin/env python3
"""Globally align fixed copy with word-timestamp ASR, with fail-closed quality gates."""
import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path


def tokens(text):
    """One Han character or one complete non-Han word; ignore punctuation."""
    text = unicodedata.normalize("NFKC", text).replace("’", "'").casefold()
    result, word = [], []

    def flush():
        if word:
            result.append("".join(word).strip("'"))
            word.clear()

    for index, char in enumerate(text):
        code = ord(char)
        han = 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0x20000 <= code <= 0x3134F
        if han:
            flush()
            result.append(char)
        elif char.isalnum() or unicodedata.category(char).startswith("M"):
            word.append(char)
        elif char == "'" and word and index + 1 < len(text) and text[index + 1].isalnum():
            word.append(char)
        else:
            flush()
    flush()
    return [token for token in result if token]


def read_asr(data):
    if isinstance(data, list):
        words = data
    elif isinstance(data, dict) and isinstance(data.get("words"), list):
        words = data["words"]
    elif isinstance(data, dict) and isinstance(data.get("segments"), list):
        words = [word for segment in data["segments"] for word in segment.get("words", [])]
    else:
        raise ValueError("ASR needs words[] or segments[].words[] with start/end seconds. Segment-only timing is insufficient.")
    observed, spans = [], []
    previous_start = -1.0
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValueError(f"ASR word {index} must be an object.")
        start, end = float(word["start"]), float(word["end"])
        if not math.isfinite(start + end) or start < 0 or end <= start or start < previous_start:
            raise ValueError(f"Invalid or unordered ASR word time at {index}.")
        previous_start = start
        pieces = tokens(str(word.get("word", word.get("text", ""))))
        for offset, token in enumerate(pieces):
            observed.append(token)
            spans.append((start + (end - start) * offset / len(pieces),
                          start + (end - start) * (offset + 1) / len(pieces)))
    if not observed:
        raise ValueError("ASR contains no usable word timestamps.")
    return observed, spans


def global_align(expected, observed):
    """Needleman-Wunsch edit alignment: sub=.85, insertion/deletion=1."""
    n, m = len(expected), len(observed)
    if n * m > 25_000_000:
        raise ValueError("Alignment exceeds 25 million cells; split long narration into independently timed parts.")
    previous = [100 * j for j in range(m + 1)]
    directions = [bytearray([2] * (m + 1))]
    for i, token in enumerate(expected, 1):
        row, trace = [100 * i] + [0] * m, bytearray(m + 1)
        trace[0] = 1
        for j, candidate in enumerate(observed, 1):
            diagonal = previous[j - 1] + (0 if token == candidate else 85)
            deletion, insertion = previous[j] + 100, row[j - 1] + 100
            best = min(diagonal, deletion, insertion)
            row[j] = best
            trace[j] = 0 if best == diagonal else (1 if best == deletion else 2)
        directions.append(trace)
        previous = row
    mapping, edits = {}, []
    i, j = n, m
    while i or j:
        direction = directions[i][j] if i and j else (1 if i else 2)
        if direction == 0:
            mapping[i - 1] = j - 1
            if expected[i - 1] != observed[j - 1]:
                edits.append({"type": "substitution", "reference_index": i - 1,
                              "asr_index": j - 1, "expected": expected[i - 1], "observed": observed[j - 1]})
            i, j = i - 1, j - 1
        elif direction == 1:
            edits.append({"type": "missing_from_asr", "reference_index": i - 1, "expected": expected[i - 1]})
            i -= 1
        else:
            edits.append({"type": "asr_insertion", "asr_index": j - 1, "observed": observed[j - 1]})
            j -= 1
    return mapping, list(reversed(edits)), previous[m] / 100


def load_phrases(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("phrases")
    if not isinstance(data, list) or not data:
        raise ValueError("Phrases must be a nonempty list, or {phrases: [...]}.")
    result = []
    for value in data:
        text = value if isinstance(value, str) else value.get("text") if isinstance(value, dict) else None
        if not isinstance(text, str) or not tokens(text):
            raise ValueError("Every phrase must have nonempty fixed-copy text.")
        result.append(text.strip())
    return result


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def align(args):
    reference = args.script.read_text(encoding="utf-8-sig").strip()
    expected = tokens(reference)
    phrases = load_phrases(args.phrases)
    # ASR can omit punctuation, but the subtitle source must not alter fixed copy.
    # Token equality alone would accept $199 -> €199 or 1.99 -> 199.
    compact_script = re.sub(r"\s+", "", reference)
    compact_phrases = re.sub(r"\s+", "", "".join(phrases))
    if not expected or compact_phrases != compact_script or tokens(" ".join(phrases)) != expected:
        raise ValueError("Phrases must reproduce the fixed script exactly and in order; only whitespace/line-break changes are allowed.")
    observed, spans = read_asr(json.loads(args.asr.read_text(encoding="utf-8-sig")))
    mapping, edits, cost = global_align(expected, observed)
    for edit in edits:
        if "asr_index" in edit:
            edit["time"] = list(spans[edit["asr_index"]])
    missing = sum(edit["type"] == "missing_from_asr" for edit in edits)
    missing_run = longest_missing_run = 0
    for index in range(len(expected)):
        missing_run = missing_run + 1 if index not in mapping else 0
        longest_missing_run = max(longest_missing_run, missing_run)
    missing_ratio, edit_ratio = missing / len(expected), len(edits) / len(expected)
    issues = []
    if missing_ratio > args.max_missing_ratio:
        issues.append(f"Missing-token ratio {missing_ratio:.3f} exceeds {args.max_missing_ratio:.3f}.")
    if edit_ratio > args.max_edit_ratio:
        issues.append(f"Edit ratio {edit_ratio:.3f} exceeds {args.max_edit_ratio:.3f}.")
    if longest_missing_run > args.max_missing_run:
        issues.append(f"Consecutive missing tokens {longest_missing_run} exceeds {args.max_missing_run}.")
    last_asr_end = max(end for _, end in spans)
    audio_duration = args.audio_duration if args.audio_duration is not None else last_asr_end
    if audio_duration <= 0 or not math.isfinite(audio_duration) or last_asr_end > audio_duration + 0.05:
        raise ValueError("ASR words exceed --audio-duration, or the duration is invalid.")
    captions, phrase_reports, cursor = [], [], 0
    for number, text in enumerate(phrases, 1):
        count = len(tokens(text))
        indices = list(range(cursor, cursor + count))
        aligned = [index for index in indices if index in mapping]
        exact = [index for index in aligned if expected[index] == observed[mapping[index]]]
        coverage, exact_ratio = len(aligned) / count, len(exact) / count
        if coverage < args.min_phrase_coverage or exact_ratio < args.min_phrase_exact:
            issues.append(f"Phrase {number} has insufficient ASR support: mapped={coverage:.3f}, exact={exact_ratio:.3f}.")
        phrase_reports.append({"phrase_index": number, "text": text, "reference_start": cursor,
                               "reference_end": cursor + count, "mapped_ratio": coverage, "exact_ratio": exact_ratio,
                               "missing_tokens": [expected[i] for i in indices if i not in mapping]})
        if aligned:
            start = max(0.0, spans[mapping[aligned[0]]][0] - args.lead_ms / 1000)
            end = min(audio_duration, spans[mapping[aligned[-1]]][1] + args.tail_ms / 1000)
            captions.append({"start": round(start, 6), "end": round(end, 6), "text": text, "phrase_index": number})
        cursor += count
    for previous, following in zip(captions, captions[1:]):
        previous["end"] = min(previous["end"], following["start"])
    if any(caption["end"] - caption["start"] < 0.03 for caption in captions):
        issues.append("A phrase has less than 30 ms of supported time after removing overlap.")
    token_times = [{"token": token, "asr_index": mapping.get(index),
                    "start": spans[mapping[index]][0] if index in mapping else None,
                    "end": spans[mapping[index]][1] if index in mapping else None}
                   for index, token in enumerate(expected)]
    report = {"accepted": not issues, "script": str(args.script.resolve()), "asr": str(args.asr.resolve()),
              "expected_tokens": len(expected), "asr_tokens": len(observed), "edit_cost": cost,
              "edit_ratio": edit_ratio, "missing_ratio": missing_ratio, "longest_missing_run": longest_missing_run,
              "thresholds": {key: getattr(args, key) for key in ("max_missing_ratio", "max_edit_ratio",
                             "max_missing_run", "min_phrase_coverage", "min_phrase_exact")},
              "issues": issues, "edits": edits, "phrases": phrase_reports, "token_times": token_times,
              "timing_note": "Missing reference tokens are never assigned invented timestamps. Chinese characters within one ASR word share its measured interval.",
              "output_written": not issues}
    write_json(args.report, report)
    if issues:
        print(json.dumps({"accepted": False, "issues": issues, "report": str(args.report)}, ensure_ascii=False), file=sys.stderr)
        return 2
    write_json(args.output, {"accepted": True, "captions": captions, "alignment_report": str(args.report.resolve())})
    print(json.dumps({"accepted": True, "captions": len(captions), "output": str(args.output), "report": str(args.report)}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, required=True, help="UTF-8 fixed-copy text")
    parser.add_argument("--asr", type=Path, required=True, help="Word-timestamp JSON, including faster-whisper schema")
    parser.add_argument("--phrases", type=Path, required=True, help="Ordered caption phrases preserving script tokens")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audio-duration", type=float)
    parser.add_argument("--max-missing-ratio", type=float, default=0.05)
    parser.add_argument("--max-edit-ratio", type=float, default=0.20)
    parser.add_argument("--max-missing-run", type=int, default=2)
    parser.add_argument("--min-phrase-coverage", type=float, default=0.80)
    parser.add_argument("--min-phrase-exact", type=float, default=0.50)
    parser.add_argument("--lead-ms", type=float, default=30)
    parser.add_argument("--tail-ms", type=float, default=60)
    args = parser.parse_args()
    try:
        for key in ("max_missing_ratio", "max_edit_ratio", "min_phrase_coverage", "min_phrase_exact"):
            if not 0 <= getattr(args, key) <= 1:
                raise ValueError(f"{key} must be between 0 and 1.")
        if args.max_missing_run < 0 or args.lead_ms < 0 or args.tail_ms < 0:
            raise ValueError("Missing-run and caption padding settings must be nonnegative.")
        if args.output.resolve() in {args.script.resolve(), args.asr.resolve(), args.phrases.resolve(), args.report.resolve()}:
            raise ValueError("Output path must differ from inputs and report.")
        if args.report.resolve() in {args.script.resolve(), args.asr.resolve(), args.phrases.resolve()}:
            raise ValueError("Report path must differ from inputs.")
        return align(args)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        report = {"accepted": False, "output_written": False, "issues": [str(error)]}
        if args.report.resolve() not in {args.script.resolve(), args.asr.resolve(), args.phrases.resolve(), args.output.resolve()}:
            write_json(args.report, report)
        print(f"Alignment failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
