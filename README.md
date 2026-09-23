# ShotAI Business Video

[中文说明](README.zh-CN.md) · [Download ShotAI](https://www.shotai.io) · [English skill package](dist/shotai-business-video-en.zip) · [中文技能包](dist/shotai-business-video-zh.zip)

Turn approved business copy and your own footage into narrated Douyin or TikTok videos. Built for independent restaurants, cafés, guesthouses, hotels and local shops, with selectable voices and licensed background music.

**Install the ShotAI desktop client and import your footage first.** This skill is not a stock-video service. ShotAI MCP can find only footage that has been added to the ShotAI library and finished its analysis/indexing. Installing this skill or supplying a folder path does not make disk files searchable.

## Real production examples

These are the user's actual Nanxun guesthouse videos from the workflow that informed this skill. Both use **Chinese Serena narration and a 16:9 layout**; they are not examples of English or vertical output. Click a preview image to open its MP4 file, or use the video links below. The repository contains compact web copies.

### 1. A weekend to rest / 把周末留给休息

**58.57 seconds · 38 shots · 1–2 seconds per shot.** An urban worker's weekend-reset perspective, with gentle guitar beneath the narration.

[![A weekend to rest — video preview](docs/examples/weekend-reset.jpg)](docs/examples/weekend-reset.mp4)

[Open MP4](docs/examples/weekend-reset.mp4) · [Download MP4](https://raw.githubusercontent.com/abu-ShotAI/shotai-business-video/main/docs/examples/weekend-reset.mp4) · [Poster](docs/examples/weekend-reset.jpg)

Music: **Clear Air — Kevin MacLeod** ([official source](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100626)), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Excerpted, faded, level-adjusted and mixed under narration.

### 2. Make the stay part of the journey / 把住处也当作旅程

**68.93 seconds · 44 shots · 1–2 seconds per shot.** A slow traveler's view of the rooms, breakfast and tea, with a tightened opening and gentle piano.

[![Make the stay part of the journey — video preview](docs/examples/slow-stay-details.jpg)](docs/examples/slow-stay-details.mp4)

[Open MP4](docs/examples/slow-stay-details.mp4) · [Download MP4](https://raw.githubusercontent.com/abu-ShotAI/shotai-business-video/main/docs/examples/slow-stay-details.mp4) · [Poster](docs/examples/slow-stay-details.jpg)

Music: **Meditation Impromptu 01 — Kevin MacLeod** ([official source](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100163)), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Excerpted, faded, level-adjusted and mixed under narration.

The examples reuse previously selected footage from an indexed ShotAI library; the second video's revised opening used two fresh MCP searches/exports. They predate the packaged helpers. Web previews are 960×540 copies of the 1080p originals with the audio and duration preserved. **Example media is displayed with user authorization and is not licensed under the code's MIT license.** [Production details and media credits](docs/examples/CREDITS.md).

## Start here: prepare the footage library

1. **Download and install [ShotAI](https://www.shotai.io).** Open the desktop client.
2. **Create a collection for the correct business or branch.** Keep footage for unrelated properties separate.
3. **Import video files or folders you have the right to use.** Include entrances, food/rooms, facilities, details and real service actions.
4. **Wait for shot analysis and semantic indexing to complete.** Files that have not finished indexing may be missing from semantic search.
5. **Enable/configure the client's MCP connection and connect your AI agent.** Follow the settings available in your installed version. Keep the client and local MCP service available while searching/exporting.
6. **Verify the connection.** Ask the agent to list collections, select yours, and run a sample search such as “a guest drinking tea in the courtyard.” Confirm that results belong to your business before generating a video.

If search is empty, first check that the client/service is running, the right collection was selected and indexing has completed. Retrying keywords cannot retrieve footage that was never imported. See [MCP setup](references/shotai-mcp.md).

## Install this skill

Download either the [English](dist/shotai-business-video-en.zip) or [Chinese](dist/shotai-business-video-zh.zip) package. They share the same skill name and scripts, so install **one**, not both. Extract the included shotai-business-video folder into your agent's skill directory; for Codex this is normally ~/.codex/skills/. Start a new session and invoke $shotai-business-video.

Alternatively, install from the repository with a skill installer that accepts GitHub repositories. Both entry languages support separate Chinese and English video outputs.

## Ask in ordinary language

> Use $shotai-business-video to turn my approved café script into a 60-second vertical TikTok video. Use only my Willow Café collection. Let me choose between two English voices and quiet licensed instrumental tracks. Keep the script and prices exactly as supplied.

> 用 $shotai-business-video，把我的固定文案和 ShotAI 里的本店素材做成抖音竖屏视频。先给两个中文音色试听，配乐用轻柔纯音乐，不改文案和套餐价格。

The agent handles the internal timeline and manifests. Owners do not need to write JSON.

## What the workflow does

| Stage | Result |
|---|---|
| Approved copy | Exact script, business identity and desired viewpoint preserved |
| Live ShotAI MCP | Meaning-based searches, frame checks and exported clips with provenance |
| Selectable narration | Voice auditions, continuous TTS or owner recording; measured timing |
| Captions and edit | Word-based alignment, usually 1–2 second shots, reviewed vertical crops |
| Selectable music | Verified commercial synchronization rights, speech ducking, fades and credits |
| Delivery | MP4, SRT, settings/QA records and recoverable cleanup |

Default delivery is 1080×1920 at 30 fps, normally 35–80 seconds. Your fixed script takes priority over an arbitrary duration. Chinese and English versions are narrated and timed separately, not just subtitle swaps. The skill does not publish posts or launch paid ads.

## Requirements and boundaries

- ShotAI desktop client, imported/indexed footage, and a working MCP connection.
- Python 3.10+, FFmpeg/FFprobe, the libraries in [requirements.txt](requirements.txt), and suitable fonts.
- Provider word timestamps or an available ASR service/local model. An ASR model is not bundled.
- Built-in voice routes: Edge, the official Qwen public demo, and existing recordings. Other production providers use the documented adapter contract. Demo quotas and provider usage terms still apply.
- Music must cover the intended platform and commercial use. Paid ads may require different rights. Installable skill archives contain no footage or music; the separately published examples above include credited music.

ShotAI handles footage search and clip export; local FFmpeg/Pillow tools compose video, captions and audio. A music-only edit copies the existing picture stream. See [full setup](references/setup.md), [English workflow](references/workflow.en.md), [voice/music](references/voice-music.md), and [timeline format](references/timeline-schema.md).

## Validation

Local mock-MCP tests, synthetic audio/video checks, Chinese portrait and English caption rendering, and independent scenario reviews were completed. These are not a claim that every remote TTS service, ShotAI build or music license has been certified. Details: [validation scope](docs/validation.md).

## License

MIT for the skill's scripts and documentation. The example videos and posters are excluded from that grant; see [media rights](docs/examples/CREDITS.md). ShotAI, provider services, models, footage, fonts and music retain their own terms. See [LICENSE](LICENSE).
