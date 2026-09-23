# 安装与开始 / Setup and quick start

## 先准备 ShotAI 素材库 / Prepare the ShotAI library first

**下载客户端 / Download the desktop client: [ShotAI 官网 / Official website](https://www.shotai.io)**

1. 下载并安装 ShotAI 客户端。
2. 在客户端为本店创建集合，分店素材需要能明确区分。
3. 将有权使用的视频导入该集合。
4. 等待镜头分析和索引完成；文件导入不等于已经可以检索。
5. 在客户端启用 MCP，按当前客户端提供的连接方式接入代理；使用期间保持客户端及 MCP 服务可用。具体界面以当前版本为准。
6. 先调用 `list_collections` 确认本店集合，再限定该集合运行一条 `search_shots`，确认能返回已入库的素材。接入细节见 [ShotAI MCP](shotai-mcp.md)。

仅在硬盘上存有视频、安装本技能或填写素材路径，都不会让 MCP 自动找到素材。缺素材或搜索无结果时，先核对客户端/服务是否可用、集合是否正确、视频是否已导入且镜头索引完成，再调整搜索描述。

1. Download and install the ShotAI desktop client.
2. Create a collection for the business in the client, keeping branches distinguishable.
3. Import videos the owner has the right to use into that collection.
4. Wait for shot analysis and indexing to finish; importing a file alone does not make it searchable.
5. Enable MCP in the client and connect the agent using the connection details provided by the current client. Keep the client and MCP service available during use; interface details vary by version.
6. Call `list_collections` to identify the business's collection, then run one `search_shots` query restricted to it and confirm that indexed footage is returned. See [ShotAI MCP](shotai-mcp.md) for connection details.

Videos stored only on disk, installing this skill, or supplying footage paths do not make footage searchable through MCP. For missing footage or empty results, check client/service availability, the selected collection, import completion and shot indexing before changing the query.

## 安装技能

把整个 shotai-business-video 目录放进技能目录，例如 ~/.codex/skills/shotai-business-video/。中文包入口是中文，英文包入口是英文；两包同名同运行脚本，选择其一安装，不重复放入发现路径。每包仍有另一语言完整说明，两种语言视频都能制作。新会话调用 $shotai-business-video。

Install the whole shotai-business-video folder in the agent skills directory, e.g. ~/.codex/skills/. Choose the Chinese or English package, not both: the runtime and skill name are identical. Both support separate Chinese and English videos. Invoke $shotai-business-video in a new session. This is an agent skill, not a standalone desktop app.

## 前提 / Prerequisites

- 完成上述 ShotAI 素材库准备。优先已配置 MCP 工具；后备 SSE 见 [shotai-mcp.md](shotai-mcp.md)。技能不自动读取数据库令牌、开启服务或扩大权限。
- Python 3.10+、FFmpeg、FFprobe；Pillow、NumPy、SoundFile。Edge路线需要edge-tts。
- 中文/英文字体，可传 --font。字体存在仍需检查实际缺字和换行。
- 最终旁白词时间戳来自TTS或已有ASR服务/本地模型。本技能附对齐器，不附ASR模型；无词时间戳就报告缺项，不伪造同步。
- 用户授权音乐或可核实许可的音源。本包不含商家素材、API令牌、付费账号或第三方音乐。

An indexed ShotAI library and configured MCP connection are required for footage selection. ASR or provider word timestamps must be available separately. No recognition model, music track or private credential is bundled.

缺库时可用项目隔离环境，不修改系统配置：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install Pillow numpy soundfile edge-tts
```

Windows uses .venv\Scripts\python.exe instead. Install FFmpeg/FFprobe and required system fonts separately when missing. Paid TTS providers are not automatically configured.

## 示例命令 / Example commands

从用户项目目录运行，SKILL指向实际技能路径，输出全部放job目录。代理从日常对话补齐brief，不要求店主填写timeline。

```bash
SKILL="$HOME/.codex/skills/shotai-business-video"
python3 "$SKILL/scripts/preflight.py" --project . --script script.zh.txt --provider edge
```

1. 实时MCP检索、关键帧核对与导出，保存调用证据。
2. 用短文试听，选中后用同一选择记录生成整稿：

```bash
python3 "$SKILL/scripts/voice.py" --provider edge --list-voices
python3 "$SKILL/scripts/voice.py" --provider edge --voice zh-CN-XiaoxiaoNeural --lang zh --text-file audition.zh.txt --output edit/job/voice-sample.wav --stage audition
python3 "$SKILL/scripts/voice.py" --selection edit/job/voice-sample.voice.json --text-file script.zh.txt --output edit/job/narration.wav --stage full --tempo 1.1
```

音色ID是例子，按实时列表选择。已有录音：

```bash
python3 "$SKILL/scripts/voice.py" --provider existing --input owner-voice.wav --text-file script.zh.txt --output edit/job/narration.wav
```

3. 获得词级ASR后对齐。phrases.json是按语义拆分且拼回等于原文的短语列表，格式见 [timeline-schema.md](timeline-schema.md)。

```bash
python3 "$SKILL/scripts/align_captions.py" --script script.zh.txt --asr edit/job/asr.json --phrases edit/job/phrases.json --output edit/job/captions.json --report edit/job/alignment-report.json
```

4. 代理用实际语音边界与已核验导出素材生成timeline，渲染字幕画面后混音：

```bash
python3 "$SKILL/scripts/render_video.py" edit/job/timeline.json --output edit/job/picture.mp4
python3 "$SKILL/scripts/mix_audio.py" --video edit/job/picture.mp4 --voice edit/job/narration.wav --music licensed-music.mp3 --music-license edit/job/music-license.json --platform douyin --usage organic --output edit/job/final.zh.mp4
```

无配乐用 --music none，无需许可证。英文使用独立英文稿/音色/ASR/时间轴，平台选tiktok。明确付费广告才用 --usage ads并核对广告许可。

5. 检查交付；只清理显式缓存清单：

```bash
python3 "$SKILL/scripts/cleanup.py" --job edit/job --manifest edit/job/cleanup.json
python3 "$SKILL/scripts/cleanup.py" --job edit/job --manifest edit/job/cleanup.json --apply
```

默认dry-run，--apply移至job/.trash/<timestamp>/并记录恢复路径，不永久删除。示例：

```json
{
  "cache_roots": ["render_work"],
  "preserve": ["final.zh.mp4", "narration.wav", "timeline.json", "music-license.json"],
  "files": [{"path": "render_work/segment_001.mp4", "rebuildable": true, "reason": "Generated clip; source export remains", "dependencies": ["timeline.json", "exports/shot.mp4"]}]
}
```

## 范围与验证 / Scope and validation

执行前读各工具--help。依赖检查不等于在线TTS/ShotAI认证可用。技术检查不替代语义选镜、裁切/字体目检和声音试听。

本技能做过模拟本地MCP、合成音视频及中英字幕测试；具体结果与限制见分享包旁验证说明。公共TTS配额、音乐使用范围和不同ShotAI版本仍须在实际使用时检查，不承诺未经实测的第三方API。
