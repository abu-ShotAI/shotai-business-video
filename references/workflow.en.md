# ShotAI Business Video — English Edition

Produce ready-to-review Douyin or TikTok feed videos for independent restaurants, cafés, guesthouses, hotels and local shops. The owner supplies approved copy and an indexed ShotAI footage library. The agent matches real footage, offers selectable narration and music, aligns captions and renders the result.

**First, download the [ShotAI desktop client](https://www.shotai.io) and prepare its library:** install the client → create a collection for the business → import videos the owner has the right to use → wait for shot analysis and indexing to finish → enable MCP in the client and connect the agent, keeping the client and MCP service available during use → call `list_collections` and run one `search_shots` query within the business's collection to confirm retrieval. See [Setup](setup.md) for details.

Videos stored only on disk, installing this skill, or supplying file paths do not make footage searchable through MCP. If footage is missing or search returns no results, check the client/service, collection and indexing status first.

Use ordinary language with the owner. Technical manifests are internal production records, not forms the owner must understand. Respect scope: one requested video is not an unsolicited batch.

## Brief and defaults

Recover existing choices first. Obtain only missing essentials: locked script, business/branch and ShotAI collections, language, voice and music preferences. Default to 1080×1920 at 30 fps, about a minute (normally 35–80 seconds), with roughly 1–2 seconds per shot. Explicit user specifications override defaults.

Preserve approved wording, order, prices, names and claims. Save the exact text and hash. If it is too long, measure narration and offer reasonable speed or a longer version; do not silently cut copy. If drafting is requested, identify a speaker perspective, one pain point and one need without inventing a personal visit.

For bilingual delivery, create separate Chinese and English narration, caption timings and final videos. Translated subtitles over Chinese audio are not an English version. Save translations separately; do not silently localize currency, offers or place names. Resolve material ambiguities. Examples: [Business prompts](examples.md).

## Workflow

### Connect to ShotAI

Read [ShotAI MCP](shotai-mcp.md). After preparing the library above, prefer exposed MCP tools; use the bundled loopback SSE client only when needed. Make actual discovery and collection calls for this job, then confirm retrieval with a search. Scope collection IDs to the correct business, branch, room or menu, and retain the results.

Live MCP retrieval is the selection path. If unavailable, report the concrete blocker and continue independent script/audio work. Do not silently use filename matching or describe cached results as live. Offline cache reuse needs the user's explicit choice and must be labelled. Audio-only changes that select no footage need no new search.

### Choose and synthesize narration

Read [Voice and music](voice-music.md). Accept a selected provider/voice, existing recording, or permission to choose. When the owner wants to select, provide 2–3 short 8–15 second samples with identical text and comparable loudness. Reuse prior choices without repeated approval.

Synthesize connected sentences or the full script. Use long natural paragraphs only when chunking is necessary; never one audio fragment per 1-second shot. Save original/final audio, settings, text hash and measured length. A public Qwen demo is an audition option, not a production guarantee. Stop on quota exhaustion; never change voices or identities silently.

### Align to the final voice

Obtain word timestamps from a provider or available ASR service/local model, cached by audio hash. Use `align_captions.py` with the locked text and deliberate phrase breaks. Review omissions, numbers and proper nouns. Correct subtitles must not conceal missing speech. Character-rate estimates are not precise alignment.

Split by meaning, keeping English words intact. Longer sentences can span several shots; captions need not reset at every cut. For a slow opening, inspect pauses and elongated endings before globally speeding up the video. Change only the affected sentence and map its revised times.

### Fill footage by meaning

Query `search_shots` with a concrete visual sentence and allowed `collectionIds`, for example: A guest drinks tea in a sunlit courtyard beside bamboo. This distinguishes real outdoor tea drinking from an empty indoor tea table.

Use `get_shot` and actual keyframes to verify candidates. Similarity ranks results; it does not prove a match. Dishes, rooms, facilities and actions must support the script and belong to the named business. Report missing footage rather than implying false claims with a vaguely related image.

Export with `export_shots`. Retain its response, shot ID, collection ID, original offset and exported path. Timeline trims are relative to the exported file; never apply original-media timecodes to a trimmed export. Use real voice boundaries for roughly 1–2-second shots, avoid identical adjacent footage and frozen tail padding.

Inspect vertical crops for faces, signs, plated food and facilities. Set per-shot focus; choose another clip or full-frame fit if cropping would hide key information. Do not blindly center-crop landscape footage.

### Render and add music

Follow [Timeline schema](timeline-schema.md) and `render_video.py`: separate clip renders, lossless concat, then captions after other visual processing. ShotAI handles retrieval/export; the local renderer handles composition. State this accurately. A ShotAI EDL/XML export is not automatically the final voice/caption timeline.

Music may be owner-supplied, from an established licensed library, or from a verified source allowing commercial synchronization. Free downloads and in-app listening are not licenses. NC or unknown rights are unsuitable for business videos. Rights may differ by platform and organic versus paid advertising. Record source, license evidence, attribution and edits.

`mix_audio.py` places music quietly beneath speech, ducks it while speech is active and fades its ends. Preserve narrator amplitude and timing. Adding music to an existing cut uses video stream copy: do not change picture, captions, opening pace or footage selection.

### Verify and deliver

Follow [Quality and revisions](quality-revisions.md): fully decode, check length/frame count/timing continuity, captions, complete narration, peaks and credits. Review opening, ending, shot midpoints and cut boundaries. ASR and meters do not constitute listening; describe the checks actually performed.

Deliver MP4, SRT, locked copy/speaker perspective, voice/music settings, credits and concise records. Do not publish posts, create paid campaigns or call unfinished work complete.

Write to `<project>/edit/<job>/`, never the skill installation. Preserve source footage, selected audio, finals, licenses and reproducibility records. Cleanup only an explicit allowlist of this job's rebuildable intermediates, using recoverable job trash and a restoration manifest.

For the complete Chinese edition, read [中文流程](workflow.zh.md).

## Helpers

Read [Setup](setup.md) and each tool's `--help`: `preflight.py`, `shotai_client.py`, `voice.py`, `align_captions.py`, `render_video.py`, `mix_audio.py`, `cleanup.py`. The agent orchestrates these; this is not an unattended publishing application.
