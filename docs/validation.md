# Validation scope

[简体中文](validation.zh-CN.md)

The workflow was developed against a real local ShotAI library. Packaged helpers were then exercised independently with synthetic fixtures, so no private footage, tokens or downloaded music is required to inspect this repository.


| Area | Checks completed |
|---|---|
| Local MCP adapter | 10 mock-SSE checks: initialize/list/call, structured errors, bounded waits, disconnection, loopback/same-origin restrictions and secret redaction |
| Audio helpers | 28 offline checks: preserved-pitch tempo, selection reuse, quota stop, narration preservation, packet-copy mixing and license manifest rejection cases |
| Fixed-copy guard | 7 cases: exact/layout-only acceptance; currency, decimal, percentage, sign and unit changes rejected |
| Rendering | Chinese portrait 1080×1920, English landscape 1920×1080, crop focus, contain fit, captions, frame count and full decode |
| Pipeline integration | Chinese/English render output fed to mixer with unchanged picture packets and subtitles |
| Cleanup/preflight | 7 cases covering dry-run, recoverability, preserved finals, traversal, symlinks, changed files and missing dependencies/inputs |
| Independent scenarios | Restaurant with disconnected MCP; English hotel with missing footage/unknown music rights; opening-only revision |

Forward review found and resolved a cached-evidence mode conflict, a currency-symbol preservation bug, an output-directory documentation mismatch and an English revision-rule ambiguity.

These checks do not certify every current ShotAI version, remote TTS service, OS/font combination or third-party license. The package's new TTS adapters were tested offline; online availability, model/voice catalogs, quotas and terms must be checked in the production environment. An ASR model is not bundled. No claim of subjective listening quality is made by technical checks alone.

## Rebuild the language packages

Run python3 tools/package.py from the repository root. The builder includes only skill instructions, references, templates, helpers and requirements. Both entry languages appear in dist/, with SHA-256 hashes in dist/manifest.json.
## Inline player recheck — 2026-09-24

The third attachment and the actual signed video source both matched the repository file in a complete anonymous download. H.264 High@3.1/yuv420p, AAC-LC stereo, 540×960 at 30 fps and a front-loaded moov box decoded without errors. A browser playback check advanced to 0:15 of 0:50. One initial Range request timed out, then succeeded on retry; the cause was not established. Native video markup and an open/download fallback are retained.
