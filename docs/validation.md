# Validation scope / 验证范围

The workflow was developed against a real local ShotAI library. Packaged helpers were then exercised independently with synthetic fixtures, so no private footage, tokens or downloaded music is required to inspect this repository.

已在实际本地ShotAI流程基础上提炼工具，再用独立合成数据验证。仓库不包含个人视频、令牌、第三方音乐或模型。

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
