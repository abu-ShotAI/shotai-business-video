# Quality and revisions

Optional documentation: [Chinese quality guide](zh-CN/quality-revisions.md).

## Production facts

- Match narration to the approved script. ASR homophones can use the original wording in captions, but correct captions must not conceal missing speech or mispronounced numbers/proper names.
- Footage must belong to the correct business, branch and room type. Specific dishes, facilities and actions must be visible; generic tags are not semantic review.
- Use in/out points relative to the actual media. Do not freeze a short source's final frame to fill time. Time captions against the final narration.
- Record live MCP results, historical caches and manual judgments separately. Only actual calls made during this job count as live ShotAI use in this job.

## Verification

1. Use ffprobe to check dimensions, frame rate, frame count and audio/video length; fully decode with ffmpeg.
2. Check clipping, peaks, complete opening/ending and unusually long silence. A reasonable total length does not establish a well-paced first sentence.
3. Inspect the first/last frames, every shot's midpoint and both sides of cuts. Check faces, signs and dishes after vertical cropping. Keep captions clear of bottom/right platform UI: reserve at least about 15% at the bottom as a starting point; the bundled portrait renderer uses a more conservative 22%. The actual app preview matters more than a fixed pixel rule.
4. Reject overlapping, negative-duration or out-of-range captions. Keep English words intact and check Chinese glyph coverage; an installed font may still lack the needed glyphs.
5. When listening tools are available, hear the opening, names, numbers, sentence transitions, ending and music/voice balance. If unavailable, report only ASR/technical audio checks.
6. Match music licensing evidence to the actual audio SHA-256 and deliver required credits. MP4 metadata does not replace attribution visible on the publishing page.

## Make the smallest requested revision

| Feedback | Change | Verify |
|---|---|---|
| First sentence is too slow | Shorten long pauses with word-edge guards; apply local pitch-preserving speed change if needed | Save piecewise old-to-new timing; preserve body PCM and update affected captions/picture |
| Change the voice | Synthesize the original script continuously with the new selection, then realign | Do not reuse old caption timestamps; review shot timing after duration changes |
| Replace one shot | Search, inspect and export through ShotAI for that intent only | Preserve other order/durations and record the new source |
| Add or replace music | Stream-copy picture and only remix audio; duck under speech and fade ends | Video packet hashes, PTS/DTS/durations and caption bytes remain unchanged; no narration offset |
| Make an English version | Create a separate translated script, English narration, captions and timeline | Subtitles alone are not an English version; preserve brand facts and units |

Splice audio in low-level regions, usually with about 30 ms fades that do not land on word attacks. Save a time mapping for speed/silence edits. Verify unchanged body samples or describe the actual changed scope.

## Cleanup

Keep the locked script, final narration, licensed audio, final MP4/SRT, timeline, MCP evidence, QA and reproduction settings. After confirming that temporary clips/frames are rebuildable and their dependencies remain available, use `cleanup.py` with an explicit file allowlist to move them into recoverable job trash. Do not delete whole `render_work` or `qa` directories: they may contain unique audio or records.
