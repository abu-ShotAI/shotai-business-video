# Timeline and caption alignment

Optional documentation: [Chinese timeline guide](zh-CN/timeline-schema.md).

Use this contract after the agent has selected footage through live ShotAI MCP and inspected representative frames. These scripts do not search by filename, choose semantic matches, or add music. Python 3.10+, Pillow, `ffmpeg`, and `ffprobe` are required.

## 1. `timeline.json`

Paths may be absolute or relative to the timeline file. Every shot must resolve to a real exported video. The example paths and IDs below are placeholders, not usable evidence.

```json
{
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "voice_file": "voice/narration.wav",
  "shots": [
    {
      "source": "exports/shot-a.mp4",
      "in": 0.2,
      "duration": 1.6,
      "shot_id": "ACTUAL_SHOT_ID",
      "collection_id": "ACTUAL_COLLECTION_ID",
      "export_record": "mcp/export-shots-result.json",
      "fit": "cover",
      "focus_x": 0.5,
      "focus_y": 0.5,
      "crop_reviewed": true
    },
    {
      "source": "exports/shot-b.mp4",
      "in": 0,
      "duration": 1.6,
      "shot_id": "ANOTHER_ACTUAL_SHOT_ID",
      "collection_id": "ACTUAL_COLLECTION_ID",
      "export_record": "mcp/export-shots-result.json",
      "fit": "contain"
    }
  ],
  "captions": [
    {"start": 0.1, "end": 1.4, "text": "每天新鲜现做。"},
    {"start": 1.5, "end": 3.1, "text": "Freshly prepared every day."}
  ]
}
```

| Field| Meaning|
| --- | --- |
| `width`, `height`, `fps` | Optional defaults: 1080 × 1920, 30 fps. Use 1920 × 1080 for landscape. Dimensions must be even integers; fps is an integer.|
| `voice_file` | Optional narration path. Used only with `--mux-voice`; no source audio is retained.|
| `shots[]` | Nonempty, in chronological order. Each follows immediately after the previous shot.|
| `source`, `in`, `duration` | Required. `in` is seconds into the **exported file**, not the original library video. Duration rounds to the nearest output frame.|
| `shot_id`, `collection_id` | Required actual ShotAI identifiers from this task.|
| `export_record` | Required original MCP result JSON, supported wrapper, or normalized record pointing to the original result.|
| `fit: "cover"` | Scale to fill and crop. Requires `focus_x`, `focus_y`, and `crop_reviewed: true` after frame inspection.|
| `focus_x`, `focus_y` | Crop alignment 0–1: 0 left/top, 0.5 center, 1 right/bottom. These specify crop-window alignment, not a tracked subject coordinate.|
| `fit: "contain"` | Preserve the entire image with black padding. Use when a safe crop is unavailable.|
| `captions[]` | Optional ordered, non-overlapping `{start,end,text}` in timeline seconds. Independent from shot boundaries.|

Plan roughly 1–2 second cuts when appropriate to the fixed-copy meaning. Do not stretch or truncate narration to force a cut grid. Make total video length at least the narration length, normally `ceil(audio_seconds × fps)` frames. Validate after frame rounding: each source interval must still fit its exported file.

Horizontal footage is never assumed safe for vertical center cropping. Inspect the crop at the beginning, middle, and end for faces, plated food, beds, room details, and text. If a subject moves out of the static crop, select another shot, use `contain`, or pre-process a separately verified crop; this renderer does not track subjects.

## 2. Export evidence

The renderer parses native ShotAI `exportedFiles` arrays, MCP `content[].text` JSON or `structuredContent`, and the client's `{ok, recorded_at, result, evidence}` wrapper. It verifies each `shot_id` + resolved source path against `exportedFiles[].shotId/filePath`. Failed results and wrappers declaring `evidence.cache_used: true` are rejected by default.

Only if the user explicitly chooses offline reuse, pass `--allow-cached-evidence`. Original shot/source validation remains mandatory. The report labels `provenance_mode: "user_authorized_cached"`, retains evidence paths and original `recorded_at` values, and must not describe the result as a live MCP retrieval. Missing original timestamps remain an empty list; do not invent them.

```json
{
  "ok": true,
  "recorded_at": "2026-01-01T12:00:00Z",
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"success\":true,\"exportedFiles\":[{\"shotId\":\"ACTUAL_SHOT_ID\",\"filePath\":\"/absolute/path/exports/shot-a.mp4\"}]}"
    }]
  },
  "evidence": {"cache_used": false}
}
```

A normalized per-shot record is optional. Paths inside it are relative to its own file. It must point to a separate original tool-result JSON; self-authored normalized fields alone do not pass provenance checks. `original_start` describes the shot's source-library offset only; it does not change timeline `in`.

```json
{
  "shot_id": "ACTUAL_SHOT_ID",
  "collection_id": "ACTUAL_COLLECTION_ID",
  "file": "../exports/shot-a.mp4",
  "original_start": 8.2,
  "tool_result_path": "export-shots-result.json"
}
```

Export APIs may omit collection membership. If present, the renderer checks it; otherwise `collection_verified_in_export` is false in the report. The agent must preserve and inspect this task's `get_shot`/search response for collection membership, freshness, semantic relevance, and ownership. A successful render is not proof of those judgments. Never reuse an earlier task's result as a live MCP call.

## 3. Fixed-copy alignment

Inputs are UTF-8 `script.txt`, `phrases.json` (a list of strings, objects with `text`, or `{phrases:[...]}`), and word-timestamp ASR JSON. The supported ASR shapes are `[{word,start,end}]`, `{words:[...]}`, and faster-whisper-style `{segments:[{words:[...]}]}`. `text` may substitute for `word`. Timestamps are seconds relative to the **final, selected-speed narration file**. Segment-only ASR is not accepted. After a speed change, obtain new timestamps or update them using a verified exact time mapping.

```bash
python3 scripts/align_captions.py \
  --script job/script.txt \
  --phrases job/phrases.json \
  --asr job/asr.json \
  --audio-duration 31.24 \
  --output job/captions.json \
  --report job/alignment_report.json
```

The global ASR alignment treats each Han character and each English word as a token. Case and punctuation are ignored **only when comparing with ASR**. Before alignment, the source phrases must concatenate to the fixed script exactly, allowing only whitespace and line-break changes. Currency signs, decimal points, percent signs, negative signs, units, punctuation, and case must remain unchanged. Chinese characters inside one ASR word divide that measured word interval evenly; no timestamp is invented for a token absent from ASR.

Default gates are maximum 5% missing tokens, 20% total edit ratio, at most 2 consecutive missing tokens, at least 80% mapped tokens per phrase, and at least 50% exact matches per phrase. A failed gate returns exit code 2 and writes a rejected report, without generating new captions. **Check the exit code and `accepted` every time; do not reuse an existing captions file after failure.** Inspect edits and listen to the flagged audio; retry TTS or ASR as needed. Do not relax thresholds merely to make a wrong narration pass.

Successful output is `{accepted:true,captions:[...],alignment_report:...}`. Copy its `captions` array into the timeline. Captions use actual phrase support with 30 ms lead and 60 ms tail by default, with overlaps removed. Subtitle splits should follow readable phrases; shorter cuts can continue beneath the same subtitle.

## 4. Rendering and QA

```bash
python3 scripts/render_video.py job/timeline.json --output job/picture.mp4
```

Default output is **silent** for the separate audio mixer. To make a narration-only review file, add `--mux-voice`; it uses the entire narration without source audio or music, pads a shorter voice track with silence, and refuses a timeline that would cut off speech. The independent mixer remains responsible for background music, ducking, and final loudness.

Each shot is independently encoded to the same size, pixel format, frame rate and time base, then concatenated by stream copy. Pillow generates RGBA subtitle cards, overlaid in the final encode after image transforms. No libass dependency. `--font` explicitly chooses a font; otherwise the script discovers an installed platform font. Missing glyphs, unsafe text bounds, or phrases too long for the configured line count fail before the video render. English words never split across lines.

`caption_style` is optional. Pixel values refer to output resolution. Portrait defaults reserve 6% left, 14% right and 22% bottom for a conservative feed layout; platform overlays vary, so inspect the target app preview. Landscape defaults use 6% side margins and 10% bottom. For a different product placement or account UI, set explicit margins.

```json
{
  "caption_style": {
    "left_margin": 65,
    "right_margin": 151,
    "bottom_margin": 422,
    "font_size": 56,
    "min_font_size": 44,
    "max_lines": 2,
    "stroke_width": 3,
    "font_index": 0
  }
}
```

Outputs are the requested MP4, an adjacent `.srt`, an adjacent `.render_report.json`, and `<output-stem>_render_work/` containing per-shot clips, logs, and caption PNGs. Existing MP4s require `--overwrite`; use a new filename for revisions when preserving review history. The script verifies each clip and the full output's frame count, dimensions, fps, duration, and full decode. It reports shot/source evidence and actual rounded durations.

Before delivery, review cut boundaries and representative beginning/middle/end frames for crop meaning and caption readability. Listen to the final mix when an audio-capable review tool is available; otherwise explicitly report that only ASR/technical audio checks were performed. Automated checks do not prove a semantically correct shot, a natural pause or an unobstructed platform layout.
