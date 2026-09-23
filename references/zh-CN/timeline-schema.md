# 时间线与字幕对齐

[English](../timeline-schema.md) · [中文完整流程](../workflow.zh.md)

本协议用于代理通过本次 ShotAI MCP 检索、导出并看图确认素材后。脚本不根据文件名匹配文案，不代替语义选材，不混入音乐。依赖 Python 3.10+、Pillow、`ffmpeg`、`ffprobe`。

## 1. `timeline.json`

路径可为绝对路径或相对 `timeline.json` 的路径。每镜必须指向真实导出视频。以下 ID、文件路径为示意，不能作为真实导出证据。

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

| 字段 | 含义 |
|---|---|
| `width`、`height`、`fps` | 可选，默认 1080×1920、30 fps。横屏可设 1920×1080。尺寸为偶整数，帧率为整数。 |
| `voice_file` | 可选旁白路径，仅 `--mux-voice` 使用；不保留素材原声。 |
| `shots[]` | 非空，按成片顺序排列；每镜紧接前镜。 |
| `source`、`in`、`duration` | 必填。`in` 为导出文件内的秒数，不是库中原始视频的时码；时长量化到最近输出整帧。 |
| `shot_id`、`collection_id` | 本次真实 ShotAI 标识，不可自造。 |
| `export_record` | 必填，可为原始 MCP 返回、支持的外壳，或引用原始返回的规范化记录。 |
| `fit: "cover"` | 填满并裁切。实际看图后必须设置 `focus_x`、`focus_y`、`crop_reviewed: true`。 |
| `focus_x`、`focus_y` | 裁切窗口对齐位置 0–1：0 左/上，0.5 居中，1 右/下，不是动态主体追踪坐标。 |
| `fit: "contain"` | 完整保留画面，以黑边填充；适合无法安全裁切的镜头。 |
| `captions[]` | 可选，按顺序且不重叠的 `{start,end,text}`，时间单位为成片秒数，与镜头切点独立。 |

依据固定文案的语义安排约 1–2 秒镜头，不强迫字幕随每个镜头切换，不为固定网格截断旁白。总帧数通常为 `ceil(旁白秒数 × fps)`；整帧量化后仍须保证每个素材入出点有效。

横素材转竖屏须看开头、中间、结尾，确认人脸、菜品、床品、房间细节或文字没有被裁掉。主体移出固定窗口时，换镜头、用 `contain` 或先做经检查的裁切版本；本脚本不追踪主体。

## 2. 导出证据

渲染器解析原生 `exportedFiles`、MCP `content[].text` 中的 JSON、`structuredContent`，以及客户端的 `{ok, recorded_at, result, evidence}` 外壳。每镜必须与真实 `shotId/filePath` 对应；失败结果及默认情况下的 `cache_used: true` 会阻断。

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

部分导出 API 不返回集合归属：有则核对，无则报告中 `collection_verified_in_export` 为 false。代理仍须留存本次 `get_shot`/搜索结果，核对集合、当次调用、语义和素材归属。渲染成功不代表这些判断已完成，不得将旧任务结果冒充本次 MCP 调用。

## 3. 固定文案字幕对齐

输入为 UTF-8 原稿、按原顺序切分的字幕短句，以及词级 ASR JSON。短句支持字符串列表、含 `text` 的对象列表或 `{phrases:[...]}`；词级 ASR 支持 `[{word,start,end}]`、`{words:[...]}` 或 faster-whisper 的 `{segments:[{words:[...]}]}`，其中 `text` 可代替 `word`。时间必须相对于最终所选语速的旁白。只有句级时间的 ASR 不够；若更改语速，重新识别或按已验证的精确映射更新时间。

```bash
python3 scripts/align_captions.py \
  --script job/script.txt \
  --phrases job/phrases.json \
  --asr job/asr.json \
  --audio-duration 31.24 \
  --output job/captions.json \
  --report job/alignment_report.json
```

每次对齐后检查退出码与报告。全局 ASR 对齐以汉字和完整英文单词为单位，**仅与 ASR 比较时**忽略大小写与标点。对齐前，字幕短句拼接必须与固定原稿完全一致，只允许空白和换行变化；货币符号、小数点、百分号、负号、单位、标点和大小写都不得改变。一个 ASR 中文词内按字均分其已测时间；漏词没有伪造时间，报告记为 null。

默认上限为 5% 漏词、20% 编辑差异、连续漏词最多 2 个；每句至少 80% 有映射且 50% 完全匹配。不通过时退出码为 2，只写失败报告，不生成新字幕。**每次检查退出码和 `accepted`，失败后不得使用旧字幕文件。** 听取异常处，必要时重做 TTS/识别，不能单纯放宽阈值放行错误旁白。

成功输出为 `{accepted:true,captions:[...],alignment_report:...}`；将 `captions` 数组写入时间线。默认在实测短句起点前留 30 ms、终点后留 60 ms，并去除重叠。字幕按可读短句划分，短镜头可在同条字幕下切换。

## 4. 渲染与验收

```bash
python3 scripts/render_video.py job/timeline.json --output job/picture.mp4
```

默认输出**无声画面**，供独立混音脚本使用。加 `--mux-voice` 可生成仅含旁白的审片版：不保留素材原声、不加配乐；旁白较短则补静音，时间线会截断旁白则拒绝。配乐、旁白压低音乐和最终响度由独立混音流程完成。

每镜统一编码后无损拼接；Pillow 生成字幕卡片，最后编码时叠在画面变换之后，不依赖 libass。可用 `--font` 指定字体，否则自动发现平台字体。缺字、越界、过长短句会在渲染前阻断，英文单词不会拆开换行。

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

产物包括 MP4、同名 SRT、渲染报告及工作目录（逐镜片段、日志、字幕图片）。已有 MP4 需 `--overwrite`，审片迭代宜换文件名保留历史。脚本检查逐镜和整片的帧数、尺寸、帧率、时长及完整解码，报告保留证据映射与量化后时长。

交付前看切点和开中尾，确认裁切文意及字幕可读性。有听审能力时听最终混音；否则明确只做ASR/技术音频检查，不声称听过。自动检查不能证明镜头语义正确、停顿自然或平台UI未遮挡。
