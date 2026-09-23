# Voice and music

Optional documentation: [Chinese voice and music guide](zh-CN/voice-music.md).

## Choose and keep a voice

Audition the same 8–15 second passage with two or three candidates. Include the opening, business/place name, a price or number, and a natural ending. Do not generate every candidate's full script before selection. Reuse a provider/voice or audition the user has already chosen; do not ask again or silently switch it. Keep provider, voice ID, language, model and delivery instruction from the selected audition. Submit the approved script continuously, using long natural paragraphs only if chunking is necessary, rather than one fragment per sentence or shot.

| Provider | Chinese candidates | English candidates | Implementation and limits |
|---|---|---|---|
| `edge` | `zh-CN-XiaoxiaoNeural`, `zh-CN-YunxiNeural` | `en-US-JennyNeural`, `en-US-GuyNeural` | Uses `edge-tts`. Query the live catalog first; these IDs are examples, not a guarantee. Verify availability and commercial terms separately. |
| `qwen-demo` | `Serena` or other currently listed voices | `Ryan`, `Aiden` or other currently listed voices | Official Qwen3-TTS CustomVoice demo. The helper checks live interface structure and voice enums before submitting. The 1.7B model supports style instructions. No production SLA is implied. |
| `existing` | An owner's recording or legitimately generated audio | Same | Local processing only. No voice ID or remote request; use this for audio from another chosen TTS provider. |

Serena was the Chinese preference in a reference project, not the default for every restaurant, guesthouse or English video. Follow the current owner's choice. Audition, synthesize, measure and align Chinese and English independently; Chinese caption timestamps do not transfer to English narration.

Run from the user's project and replace `scripts/` with the installed scripts' absolute path. Audio and reports belong in the project, never the skill installation:

```bash
python3 scripts/voice.py --provider edge --lang zh --list-voices
python3 scripts/voice.py --provider qwen-demo --list-voices
python3 scripts/voice.py --provider edge --lang en --voice en-US-JennyNeural --text-file audition.en.txt --stage audition --output audition.en.wav
python3 scripts/voice.py --selection audition.en.voice.json --text-file approved.en.txt --stage full --output narration.en.wav
python3 scripts/voice.py --provider existing --input recorded.zh.wav --text-file approved.zh.txt --tempo 1.10 --output narration.zh.wav
```

Edge `--rate=+10%` changes synthesis rate; `--tempo 1.10` applies FFmpeg pitch-preserving postprocessing. Both default to no speed change. Avoid unintentionally stacking two 10% increases. Reuse the audition report with `--selection`. Rate/tempo may change, but provider, voice, language, model or style must not silently change. To change style, create a new audition with the same voice and reference its new report.

The helper preserves beginning, ending and internal pauses by default. Optional `--trim-edge-silence` trims detected edge silence only, retaining approximately 80 ms at the start and 150 ms at the end, and still requires listening. For “the first sentence is too slow,” listen to the first 3–5 seconds, adjust the opening with the same voice or apply moderate pitch-preserving speed change; never remove approved words. Rebuild or precisely map caption/shot timing after narration changes. A music-only revision must not change narration duration.

The default master is 48 kHz / 24-bit WAV, with two-pass loudness processing targeting -18 LUFS and -1.5 dBTP. Settings are configurable and reports record actual measurements; exact targets are not promised for all material. Use `--no-normalize` for an already approved master when appropriate. Review opening pace, names/numbers, omissions/repetitions and the last word/tail. A complete decode is not evidence of correct pronunciation, complete narration or natural delivery.

## Quotas, failures and other providers

The official Qwen demo adapter performs one generation POST and one bounded wait. HTTP 429, `quota exceeded` and ZeroGPU quota errors stop immediately, write `.voice.json` and return exit code 3. Do not split copy, switch accounts, retry indefinitely or change voices to evade limits. Network/schema failures also stop and preserve request details for diagnosis. Use a new output name after failure; resubmit only after an explicit retry request or confirmed recovery. Do not promise stable commercial batch capacity from a public demo.

Azure, Doubao, ElevenLabs, MiniMax, Fish and production Alibaba Cloud TTS are **not built-in adapters**. If the owner already uses one, implement the contract below against its current official API or import exported audio with `existing`.

An adapter must accept the complete approved UTF-8 text/SHA-256, explicit provider/model/voice/language and speed/style settings. Use user-authorized environment credentials without writing secrets to reports. Before starting, check current official API/voice availability and commercial terms. Produce connected full narration; retain the raw audio, response request ID, settings and output SHA-256/duration. Classify quota/auth/validation/temporary errors with a concrete stopping reason and no automatic provider or voice substitution. Then use the same processing, listening and alignment workflow. Do not label an unimplemented provider “supported.”

## Choose and license music

Use the owner's chosen local track, authorized platform track or no music; existing selections remain in force. If no preference is given, offer two or three short excerpts when useful—for example light rhythmic instrumental music for food or sparse warm instrumentation for a stay. These are suggestions, not fixed brand rules; sparse music without competing vocals often keeps the message clear. If no track has verified rights, deliver a dry-voice preview and state that music selection remains open.

The mixer receives local files only and downloads no tracks. Downloadable, “royalty-free” or platform-previewable music is not automatically cleared across platforms, territories or paid ads. Verify the actual track's official page/contract for commercial synchronization, platform, territory/expiry and paid advertising; retain evidence before filling the manifest. A manifest records verified rights: **its booleans do not create permission**. `organic` means an organic business post and still counts as commercial use. Set `--usage ads` only for explicitly requested paid advertising.

```json
{
  "title": "Actual track title",
  "author": "Actual creator or rights holder",
  "license": "CUSTOM",
  "source_url": "https://rights-holder.example/track",
  "license_url": "https://rights-holder.example/license",
  "evidence_file": "saved-license.txt",
  "sha256": "ACTUAL_64_CHARACTER_SHA256_OF_THE_MUSIC_FILE",
  "commercial_use_allowed": true,
  "synchronization_allowed": true,
  "paid_ads_allowed": false,
  "platforms": ["douyin", "tiktok"],
  "attribution_required": true,
  "attribution": "The complete attribution required by the actual license",
  "expires_on": "2030-12-31"
}
```

This illustrates fields, not a usable license. Resolve `evidence_file` relative to the manifest; include `expires_on` only when rights expire. Accepted identifiers are `CC0-1.0`, `CC-BY-3.0`, `CC-BY-4.0`, `CUSTOM` and `OWNED`, each requiring verified provenance. CC tracks need official source and license links; `CUSTOM`/`OWNED` needs saved license/ownership evidence. NC, ND, unknown licenses, hash mismatches, expired rights, missing platform coverage or missing requested advertising rights stop the mix. Review complex restrictions or choose another track; do not relabel unknown music as `CUSTOM`.

```bash
python3 scripts/mix_audio.py --video picture.zh.mp4 --voice narration.zh.wav --music licensed-track.wav --music-license music-license.json --platform douyin --usage organic --output final.zh.mp4
python3 scripts/mix_audio.py --video picture.en.mp4 --voice narration.en.wav --music none --platform tiktok --output final.en.mp4
```

Default music gain targets about -30 LUFS before up to 3.5 dB speech ducking, with 0.75 s fade-in and 1.4 s fade-out; these are configurable starting points. Short music is not looped automatically. With explicit `--loop-music`, listen to the loop seam. Narration starts at zero, keeps all samples and is neither resampled, shifted nor trimmed; only tail silence may be added. Mono duplicates to left/right at unity gain and stereo channels preserve amplitude. The mix is not globally normalized; peak collisions reduce music only. If narration exceeds video duration, stop and rebuild the picture timeline instead of cutting speech.

The mixer copies video and embedded subtitles without re-encoding picture, checks packet contents/timestamps, and checks hashes for external SRT/VTT/ASS. Outputs include `.mix.json` plus mixed/dry/music WAVs in `.audio/` for review. These verify unchanged narration timing and per-channel contribution **before** lossy AAC encoding, including float error and post-encode true peak. Do not claim bit-identical narration in the AAC delivery. Retain `music-credits.txt` and license evidence, and include required attribution in the published caption/credits; a local sidecar alone does not satisfy public attribution.

## Runtime and help

Python 3.10+, FFmpeg/ffprobe on PATH; `numpy` is required for mixing. `edge-tts` is optional and required only for Edge. Qwen uses Python's standard HTTP library, validates the live official demo and sends only supplied text/settings. No credentials, accounts, browser data or music are bundled.

```bash
python3 scripts/voice.py --help
python3 scripts/mix_audio.py --help
```
