# Timeline and caption alignment / 时间线与字幕对齐

Use this contract after the agent has selected footage through live ShotAI MCP and inspected representative frames. These scripts do not search by filename, choose semantic matches, or add music. Python 3.10+, Pillow, `ffmpeg`, and `ffprobe` are required.

本协议用于代理通过本次 ShotAI MCP 检索、导出并看图确认素材后。脚本不根据文件名匹配文案，不代替语义选材，不混入音乐。依赖 Python 3.10+、Pillow、`ffmpeg`、`ffprobe`。

## 1. `timeline.json`

Paths may be absolute or relative to the timeline file. Every shot must resolve to a real exported video. The example paths and IDs below are placeholders, not usable evidence.

路径可为绝对路径或相对 `timeline.json` 的路径。以下 ID、文件路径为示意，不能作为真实导出证据。

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

| Field / 字段 | Meaning / 含义 |
| --- | --- |
| `width`, `height`, `fps` | Optional defaults: 1080 × 1920, 30 fps. Use 1920 × 1080 for landscape. Dimensions must be even integers; fps is an integer. / 默认竖屏；横屏可设 1920 × 1080，尺寸须为偶数。 |
| `voice_file` | Optional narration path. Used only with `--mux-voice`; no source audio is retained. / 可选旁白，仅 `--mux-voice` 使用，素材原声不保留。 |
| `shots[]` | Nonempty, in chronological order. Each follows immediately after the previous shot. / 必填，按成片顺序无缝接续。 |
| `source`, `in`, `duration` | Required. `in` is seconds into the **exported file**, not the original library video. Duration rounds to the nearest output frame. / 必填，入点相对于导出的片段；时长量化到最近整帧。 |
| `shot_id`, `collection_id` | Required actual ShotAI identifiers from this task. / 本次真实 ShotAI 标识，不可自造。 |
| `export_record` | Required original MCP result JSON, supported wrapper, or normalized record pointing to the original result. / 必填导出证据，下节详述。 |
| `fit: "cover"` | Scale to fill and crop. Requires `focus_x`, `focus_y`, and `crop_reviewed: true` after frame inspection. / 填满裁切；看图确认后方可设置标志。 |
| `focus_x`, `focus_y` | Crop alignment 0–1: 0 left/top, 0.5 center, 1 right/bottom. These specify crop-window alignment, not a tracked subject coordinate. / 裁切窗口位置：0 左/上，0.5 居中，1 右/下，不是动态主体追踪坐标。 |
| `fit: "contain"` | Preserve the entire image with black padding. Use when a safe crop is unavailable. / 完整保留画面，以黑边填充，适合无法安全裁切的镜头。 |
| `captions[]` | Optional ordered, non-overlapping `{start,end,text}` in timeline seconds. Independent from shot boundaries. / 可选、按顺序且不重叠；与镜头切点独立。 |

Plan roughly 1–2 second cuts when appropriate to the fixed-copy meaning. Do not stretch or truncate narration to force a cut grid. Make total video length at least the narration length, normally `ceil(audio_seconds × fps)` frames. Validate after frame rounding: each source interval must still fit its exported file.

依据固定文案的语义安排约 1–2 秒镜头，不强迫字幕随每个镜头切换，不为固定网格截断旁白。总帧数通常为 `ceil(旁白秒数 × fps)`；整帧量化后仍须保证每个素材入出点有效。

Horizontal footage is never assumed safe for vertical center cropping. Inspect the crop at the beginning, middle, and end for faces, plated food, beds, room details, and text. If a subject moves out of the static crop, select another shot, use `contain`, or pre-process a separately verified crop; this renderer does not track subjects.

横素材转竖屏须看开头、中间、结尾，确认人脸、菜品、床品、房间细节或文字没有被裁掉。主体移出固定窗口时，换镜头、用 `contain` 或先做经检查的裁切版本；本脚本不追踪主体。

## 2. Export evidence / 导出证据

The renderer parses native ShotAI `exportedFiles` arrays, MCP `content[].text` JSON or `structuredContent`, and the client's `{ok, recorded_at, result, evidence}` wrapper. It verifies each `shot_id` + resolved source path against `exportedFiles[].shotId/filePath`. Failed results and wrappers declaring `evidence.cache_used: true` are rejected by default.

渲染器解析原生 `exportedFiles`、MCP `content[].text` 中的 JSON、`structuredContent`，以及客户端的 `{ok, recorded_at, result, evidence}` 外壳。每镜必须与真实 `shotId/filePath` 对应；失败结果及默认情况下的 `cache_used: true` 会阻断。

Only if the user explicitly chooses offline reuse, pass `--allow-cached-evidence`. Original shot/source validation remains mandatory. The report labels `provenance_mode: "user_authorized_cached"`, retains evidence paths and original `recorded_at` values, and must not describe the result as a live MCP retrieval. Missing original timestamps remain an empty list; do not invent them.

仅当用户明确选择离线复用时，可传 `--allow-cached-evidence`，仍须通过原始导出 ID/路径核对。报告标注 `provenance_mode: "user_authorized_cached"`、保留证据路径及原始 `recorded_at`，不得称为本次实时 MCP 检索。原记录缺失时间时保留空数组，不编造时间。

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

可选逐镜规范化记录必须引用原始工具返回文件，不能只写自述。其路径相对于记录本身。`original_start` 只记库中原始起点，不改变导出片段内的 `in`。

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

部分导出 API 不返回集合归属：有则核对，无则报告中 `collection_verified_in_export` 为 false。代理仍须留存本次 `get_shot`/搜索结果，核对集合、当次调用、语义和素材归属。渲染成功不代表这些判断已完成，不得将旧任务结果冒充本次 MCP 调用。

## 3. Fixed-copy alignment / 固定文案字幕对齐

Inputs are UTF-8 `script.txt`, `phrases.json` (a list of strings, objects with `text`, or `{phrases:[...]}`), and word-timestamp ASR JSON. The supported ASR shapes are `[{word,start,end}]`, `{words:[...]}`, and faster-whisper-style `{segments:[{words:[...]}]}`. `text` may substitute for `word`. Timestamps are seconds relative to the **final, selected-speed narration file**. Segment-only ASR is not accepted.

输入为 UTF-8 原稿、按原顺序切分的字幕短句，以及词级 ASR JSON，支持上述三种结构。时间必须相对于最终所选语速的旁白。只有句级时间的 ASR 不够；若更改语速，重新识别或按已验证的精确映射更新时间。

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

全局 ASR 对齐以汉字和完整英文单词为单位，**仅与 ASR 比较时**忽略大小写与标点。对齐前，字幕短句拼接必须与固定原稿完全一致，只允许空白和换行变化；货币符号、小数点、百分号、负号、单位、标点和大小写都不得改变。一个 ASR 中文词内按字均分其已测时间；漏词没有伪造时间，报告记为 null。

Default gates are maximum 5% missing tokens, 20% total edit ratio, at most 2 consecutive missing tokens, at least 80% mapped tokens per phrase, and at least 50% exact matches per phrase. A failed gate returns exit code 2 and writes a rejected report, without generating new captions. **Check the exit code and `accepted` every time; do not reuse an existing captions file after failure.** Inspect edits and listen to the flagged audio; retry TTS or ASR as needed. Do not relax thresholds merely to make a wrong narration pass.

默认上限为 5% 漏词、20% 编辑差异、连续漏词最多 2 个；每句至少 80% 有映射且 50% 完全匹配。不通过时退出码为 2，只写失败报告，不生成新字幕。**每次检查退出码和 `accepted`，失败后不得使用旧字幕文件。** 听取异常处，必要时重做 TTS/识别，不能单纯放宽阈值放行错误旁白。

Successful output is `{accepted:true,captions:[...],alignment_report:...}`. Copy its `captions` array into the timeline. Captions use actual phrase support with 30 ms lead and 60 ms tail by default, with overlaps removed. Subtitle splits should follow readable phrases; shorter cuts can continue beneath the same subtitle.

成功后将输出中的 `captions` 数组写入时间线。默认在实测短句起点前留 30 ms、终点后留 60 ms，并去除重叠。字幕按可读短句划分，短镜头可在同条字幕下切换。

## 4. Rendering and QA / 渲染与验收

```bash
python3 scripts/render_video.py job/timeline.json --output job/picture.mp4
```

Default output is **silent** for the separate audio mixer. To make a narration-only review file, add `--mux-voice`; it uses the entire narration without source audio or music, pads a shorter voice track with silence, and refuses a timeline that would cut off speech. The independent mixer remains responsible for background music, ducking, and final loudness.

默认输出**无声画面**，供独立混音脚本使用。加 `--mux-voice` 可生成仅含旁白的审片版：不保留素材原声、不加配乐；旁白较短则补静音，时间线会截断旁白则拒绝。配乐、旁白压低音乐和最终响度由独立混音流程完成。

Each shot is independently encoded to the same size, pixel format, frame rate and time base, then concatenated by stream copy. Pillow generates RGBA subtitle cards, overlaid in the final encode after image transforms. No libass dependency. `--font` explicitly chooses a font; otherwise the script discovers an installed platform font. Missing glyphs, unsafe text bounds, or phrases too long for the configured line count fail before the video render. English words never split across lines.

每镜统一编码后无损拼接；Pillow 生成字幕卡片，最后编码时叠在画面变换之后，不依赖 libass。可用 `--font` 指定字体，否则自动发现平台字体。缺字、越界、过长短句会在渲染前阻断，英文单词不会拆开换行。

`caption_style` is optional. Pixel values refer to output resolution. Portrait defaults reserve 6% left, 14% right and 22% bottom for a conservative feed layout; platform overlays vary, so inspect the target app preview. Landscape defaults use 6% side margins and 10% bottom. For a different product placement or account UI, set explicit margins.

可选 `caption_style` 使用输出像素值。竖屏默认预留左 6%、右 14%、底 22%；实际平台遮挡各异，仍须在目标平台预览。横屏默认左右 6%、底 10%，可按账号 UI 或商品卡位置调整。

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

产物包括 MP4、同名 SRT、渲染报告及工作目录（逐镜片段、日志、字幕图片）。已有 MP4 需 `--overwrite`，审片迭代宜换文件名保留历史。脚本检查逐镜和整片的帧数、尺寸、帧率、时长及完整解码，报告保留证据映射与量化后时长。

Before delivery, review cut boundaries and representative beginning/middle/end frames for crop meaning and caption readability. Listen to the final mix when an audio-capable review tool is available; otherwise explicitly report that only ASR/technical audio checks were performed. Automated checks do not prove a semantically correct shot, a natural pause or an unobstructed platform layout.

交付前看切点和开中尾，确认裁切文意及字幕可读性。有听审能力时听最终混音；否则明确只做ASR/技术音频检查，不声称听过。自动检查不能证明镜头语义正确、停顿自然或平台UI未遮挡。
