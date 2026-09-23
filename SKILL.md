---
name: shotai-business-video
description: Create or revise script-led Douyin and TikTok videos for restaurants, guesthouses, hotels and local shops using live ShotAI MCP retrieval from an indexed owner footage library, selectable narration, aligned captions and licensed music. Supports separate Chinese and English versions.
metadata:
  short-description: Approved script to business video with ShotAI, voice and music
---

# ShotAI Business Video

Produce ready-to-review Douyin or TikTok feed videos for independent restaurants, cafés, guesthouses, hotels and local shops. The owner supplies approved copy and an indexed ShotAI footage library. The agent matches real footage, offers selectable narration and music, aligns captions and renders the result.

**First, download the [ShotAI desktop client](https://www.shotai.io) and prepare its library:** install the client → create a collection for the business → import videos the owner has the right to use → wait for shot analysis and indexing to finish → enable MCP in the client and connect the agent, keeping the client and MCP service available during use → call `list_collections` and run one `search_shots` query within the business's collection to confirm retrieval. See [Setup](references/setup.md) for details.

Videos stored only on disk, installing this skill, or supplying file paths do not make footage searchable through MCP. If footage is missing or search returns no results, check the client/service, collection and indexing status first.

Use ordinary language with the owner. Technical manifests are internal production records, not forms the owner must understand. Respect scope: one requested video is not an unsolicited batch.

## Language options

English is the default documentation language. Use [the complete Chinese workflow](references/workflow.zh.md) and its Chinese references only when useful; do not load both translations by default. Communicate in the user’s language. Set video output language independently to Chinese (`zh`), English (`en`), or separate versions (`both`), and choose the target platform separately. English instructions do not imply English-only video output. Both installation packages use the same skill name and runtime; install only one.

## Brief and defaults

Recover existing choices first. Obtain only missing essentials: locked script, business/branch and ShotAI collections, video language and platform, voice and music preferences. Accept a specified voice/model, an existing recording, a supplied licensed music track or no music; retain choices already made in the task. Default to 1080×1920 at 30 fps, about a minute (normally 35–80 seconds), with roughly 1–2 seconds per shot. Explicit user specifications override defaults.

Preserve approved wording, order, prices, names and claims. Save the exact text and SHA-256 as the narration and caption baseline. If it is too long, measure narration and offer reasonable speed or a longer version; do not silently cut copy. If drafting is requested, identify a speaker perspective, one pain point and one need without inventing a personal visit.

For bilingual delivery, create separate Chinese and English narration, caption timings and final videos. Translated subtitles over Chinese audio are not an English version. Save translations separately; do not silently localize currency, offers or place names. Resolve material ambiguities. Use [Business prompts](references/examples.md) for common requests and [brief-template.json](assets/brief-template.json) for the internal brief.

## Workflow

### Connect to ShotAI

Read [ShotAI MCP](references/shotai-mcp.md). After preparing the library above, prefer exposed MCP tools; use the bundled loopback SSE client only when needed. Make actual discovery and collection calls for this job, then confirm retrieval with a search. Scope collection IDs to the correct business, branch, room or menu, and retain the results.

Live MCP retrieval is the selection path. If unavailable, report the concrete blocker and continue independent script/audio work. Do not silently use filename matching or describe cached results as live. Offline cache reuse needs the user's explicit choice and must be labelled. Audio-only changes that select no footage need no new search.

### Choose and synthesize narration

Read [Voice and music](references/voice-music.md). Accept a selected provider/voice, existing recording, or permission to choose. When the owner wants to select, provide 2–3 short 8–15 second samples with identical text and comparable loudness. Reuse prior choices without repeated approval. If the user asks the agent to choose, select a suitable option, state the choice and proceed; do not add a selection gate.

Synthesize connected sentences or the full script. Use long natural paragraphs only when chunking is necessary; never one audio fragment per 1-second shot. Save original/final audio, provider/model/voice settings, text hash, speed and measured length. Choose from voices actually available now; Serena at +10% was a past project preference, not a universal default. A public Qwen demo is an audition option, not a production guarantee. Stop on quota exhaustion; never change voices or identities silently.

### Align to the final voice

Obtain word timestamps from a provider or available ASR service/local model, cached by final audio content hash. Reuse an existing local model; revisions that need no new transcription can map verified old timestamps. Use `align_captions.py` with the locked text and deliberate phrase breaks. Review omissions, numbers and proper nouns. Correct subtitles must not conceal missing speech. Character-rate estimates are not precise alignment.

Split by meaning, keeping English words intact. Longer sentences can span several shots; captions need not reset at every cut. For a slow opening, inspect pauses and elongated endings before globally speeding up the video. Change only the affected sentence and map its revised times.

### Fill footage by meaning

Query `search_shots` with a concrete visual sentence and allowed `collectionIds`, for example: A guest drinks tea in a sunlit courtyard beside bamboo. This distinguishes real outdoor tea drinking from an empty indoor tea table.

Use `get_shot` and actual keyframes to verify candidates. Similarity ranks results; it does not prove a match. Dishes, rooms, facilities and actions must support the script and belong to the named business. Report missing footage rather than implying false claims with a vaguely related image: a decorative pond is not a private hot spring, an ordinary cup is not a three-course tea service, and dinner is not breakfast. Do not sacrifice a concrete semantic match merely to avoid repeats.

Export with `export_shots`. Retain its response, shot ID, collection ID, original offset and exported path. Timeline trims are relative to the exported file; never apply original-media timecodes to a trimmed export. Confirm successful exported files. Use real voice boundaries for roughly 1–2-second shots without cutting words or using frozen tail padding. Keep subject identity and sequence consistent, using different source footage for adjacent shots where practical.

Inspect vertical crops for faces, signs, plated food and facilities. Set per-shot focus; choose another clip or full-frame fit if cropping would hide key information. Do not blindly center-crop landscape footage.

### Render and add music

Follow [Timeline schema](references/timeline-schema.md) and `render_video.py`: separate clip renders, lossless concat, then captions after other visual processing. ShotAI handles retrieval/export; the local renderer handles composition. State this accurately. A ShotAI EDL/XML export is not automatically the final voice/caption timeline.

Music may be owner-supplied, from an established licensed library, or from a verified source allowing commercial synchronization. Free downloads and in-app listening are not licenses. NC, ND or unknown rights are unsuitable for this workflow’s business-video mix. Rights may differ by platform and organic versus paid advertising. Record the actual track, author, source, license evidence, attribution and edits. Do not bundle the job’s music into the skill.

`mix_audio.py` places music quietly beneath speech, ducks it while speech is active and fades its ends. Preserve narrator amplitude and timing; do not let automatic whole-mix normalization lower the voice. Adding music to an existing cut uses video stream copy: do not change picture, captions, opening pace or footage selection.

### Verify and deliver

Follow [Quality and revisions](references/quality-revisions.md): fully decode, check length/frame count, black frames, timeline gaps, caption bounds and exact copy coverage, complete narration, clipping, peaks and credits. Review opening, ending, shot midpoints and cut boundaries. ASR and meters do not constitute listening; describe the checks actually performed.

Deliver MP4, SRT, locked copy/speaker perspective, voice/music settings, credits and concise records. Do not publish posts, create paid campaigns or call unfinished work complete.

Write to `<project>/edit/<job>/`, never the skill installation. Preserve source footage references, fixed scripts, selected audio, licensed music, captions, timeline, actual MCP calls, final outputs and QA/reproduction records. Cleanup only an explicit allowlist of this job’s rebuildable intermediates whose dependencies remain available, using recoverable job trash and a restoration manifest. Never clean the owner’s footage, ShotAI library, other jobs or the skill itself.

## Helpers

Read [Setup](references/setup.md), run `scripts/preflight.py` and use each helper’s `--help`. The agent orchestrates the pipeline; this is not an unattended publishing application.

- `shotai_client.py`: configured local SSE fallback.
- `voice.py`: Edge, the Qwen public demo or an existing recording; follow the documented adapter contract for other services.
- `align_captions.py`: locked-copy alignment against existing word-level ASR, with a difference report.
- `render_video.py`: exported shots and caption rendering.
- `mix_audio.py`: narration, licensed music and original picture streams.
- `cleanup.py`: recoverable cleanup of an explicit temporary-file list.
