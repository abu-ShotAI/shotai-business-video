# Setup and quick start

Optional documentation: [Chinese setup](zh-CN/setup.md).

## Prepare the ShotAI library first

**Download and install the [ShotAI desktop client](https://www.shotai.io).**

1. Create a collection for the business in the client, keeping branches distinguishable.
2. Import videos the owner has the right to use into that collection.
3. Wait for shot analysis and indexing to finish; importing a file alone does not make it searchable.
4. Enable MCP in the client and connect the agent using the current client's connection details. Keep the client and MCP service available during use; interface details vary by version.
5. Call `list_collections` to identify the business's collection, then run one `search_shots` query restricted to it and confirm that indexed footage is returned. See [ShotAI MCP](shotai-mcp.md).

Videos stored only on disk, installing this skill, or supplying footage paths do not make footage searchable through MCP. For missing footage or empty results, check client/service availability, the selected collection, import completion and shot indexing before changing the query.

## Install the skill and choose languages

Place the complete `shotai-business-video` folder in the agent's skills directory, for example `~/.codex/skills/shotai-business-video/`, and invoke `$shotai-business-video` in a new session. This is an agent skill, not a standalone desktop app.

Use the English package by default; the Chinese package is an optional documentation entry point. They share the same skill name and runtime, so install **only one** in the discovery path. Both include the other language's instructions and support Chinese (`zh`), English (`en`), or separate videos in both languages (`both`). Communicate in the user's language, select video language explicitly from the request and choose the platform separately. The documentation language does not decide the narration language.

## Prerequisites

- The indexed ShotAI library and MCP connection described above. Prefer exposed MCP tools; use the [local SSE fallback](shotai-mcp.md) only when appropriate. The skill does not search databases for tokens, enable services or expand permissions.
- Python 3.10+, FFmpeg/ffprobe, Pillow, NumPy and SoundFile. Edge additionally requires `edge-tts`.
- Fonts for the requested language. Pass `--font` when needed, then inspect actual glyph coverage and line wrapping.
- Final-narration word timestamps from TTS or a separately available ASR service/local model. This skill bundles an aligner, not an ASR model. Report missing timestamps instead of fabricating precise synchronization.
- Owner-authorized music or an independently verified license. The package contains no owner footage, API tokens, paid accounts or third-party music.

Use a project-local environment for missing Python dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install Pillow numpy soundfile edge-tts
```

Windows uses `.venv\Scripts\python.exe` instead. Install FFmpeg/ffprobe and system fonts separately when missing. Paid TTS providers are not automatically configured.

## Example commands

Run from the owner's project. Set `SKILL` to the installed skill's actual path and place every output inside the job directory. The agent derives the production brief from ordinary conversation; the owner need not fill in a timeline.

```bash
SKILL="$HOME/.codex/skills/shotai-business-video"
python3 "$SKILL/scripts/preflight.py" --project . --script script.en.txt --provider edge
```

1. Retrieve footage through live MCP, inspect candidate frames, export selected shots and save the actual call evidence.
2. Audition short text, then reuse the chosen voice record for the complete script:

```bash
python3 "$SKILL/scripts/voice.py" --provider edge --list-voices
python3 "$SKILL/scripts/voice.py" --provider edge --voice en-US-JennyNeural --lang en --text-file audition.en.txt --output edit/job/voice-sample.wav --stage audition
python3 "$SKILL/scripts/voice.py" --selection edit/job/voice-sample.voice.json --text-file script.en.txt --output edit/job/narration.wav --stage full --tempo 1.1
```

The voice ID is an example: choose from the live catalog. To use an existing recording:

```bash
python3 "$SKILL/scripts/voice.py" --provider existing --input owner-voice.wav --text-file script.en.txt --output edit/job/narration.wav
```

3. Obtain word-level ASR, then align it. `phrases.json` contains deliberate semantic phrases that concatenate to the approved script; see [Timeline schema](timeline-schema.md).

```bash
python3 "$SKILL/scripts/align_captions.py" --script script.en.txt --asr edit/job/asr.json --phrases edit/job/phrases.json --output edit/job/captions.json --report edit/job/alignment-report.json
```

4. Build the timeline from real voice boundaries and verified exports. Render picture and captions, then mix:

```bash
python3 "$SKILL/scripts/render_video.py" edit/job/timeline.json --output edit/job/picture.mp4
python3 "$SKILL/scripts/mix_audio.py" --video edit/job/picture.mp4 --voice edit/job/narration.wav --music licensed-music.mp3 --music-license edit/job/music-license.json --platform tiktok --usage organic --output edit/job/final.en.mp4
```

For no music, use `--music none`; no music license is needed. A Chinese version uses a separate Chinese script, voice, ASR and timeline; choose `douyin` for a Douyin delivery. Use `--usage ads` only for explicitly requested paid advertising and verify advertising rights.

5. Review and deliver. Cleanup uses only an explicit cache allowlist:

```bash
python3 "$SKILL/scripts/cleanup.py" --job edit/job --manifest edit/job/cleanup.json
python3 "$SKILL/scripts/cleanup.py" --job edit/job --manifest edit/job/cleanup.json --apply
```

The default is dry-run. `--apply` moves files to `job/.trash/<timestamp>/` and records restoration paths; it does not permanently delete them. Example:

```json
{
  "cache_roots": ["render_work"],
  "preserve": ["final.en.mp4", "narration.wav", "timeline.json", "music-license.json"],
  "files": [{"path": "render_work/segment_001.mp4", "rebuildable": true, "reason": "Generated clip; source export remains", "dependencies": ["timeline.json", "exports/shot.mp4"]}]
}
```

## Scope and validation

Read each helper's `--help` before use. A dependency check does not establish live TTS/ShotAI authentication or availability. Technical checks do not replace semantic shot selection, crop/font inspection or listening.

The workflow has been tested with simulated local MCP, generated audiovisual fixtures and Chinese/English captions; consult the distribution's validation report for its actual results and limits. Recheck public-TTS quotas, music rights and current ShotAI behavior in each real run. Do not claim support for untested third-party APIs.
