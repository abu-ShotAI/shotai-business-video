# Voice and music / 声音与配乐

## 中文

### 选择声音

先用同一段短文制作 2–3 个试听，短文含开场、店名/地名、价格或数字和一句自然收尾。每段约 8–15 秒即可，避免先为全部候选生成整篇。用户已经明确指定服务商、音色或认可试听时，直接沿用；不重复索要选择。保留试听报告中的服务商、音色 ID、语言、模型和风格指令，整篇一次提交，避免逐句拼接导致语调跳变。

| 选项 | 中文候选 | 英文候选 | 实际支持与边界 |
|---|---|---|---|
| `edge` | `zh-CN-XiaoxiaoNeural`、`zh-CN-YunxiNeural` | `en-US-JennyNeural`、`en-US-GuyNeural` | `edge-tts`；先在线列音色，不能假定这些 ID 永远可用。服务可用性和商用条款需另外确认。 |
| `qwen-demo` | `Serena` 等当前列表中的候选 | `Ryan`、`Aiden` 等当前列表中的候选 | 官方 Qwen3-TTS CustomVoice 演示接口；脚本运行前检查接口结构与枚举，不是生产服务 SLA。1.7B 支持风格指令。 |
| `existing` | 用户自录音频或已合法生成的文件 | 同左 | 仅本地处理；不要求音色 ID、不提交远程请求，适合用户自选其他 TTS。 |

Serena 是本次参考流程里用户选中的中文偏好，并非所有饭店、民宿或英语项目的默认声音。正式使用必须以目标用户的声音选择为准。中文和英文分别试听、生成、测量与对齐，不能把中文字幕时间戳直接套给英文。

从用户项目目录执行，将下例 `scripts/` 换成技能中 scripts 的绝对路径；所有相对音频/报告路径都属于用户项目，不能在技能安装目录内产生：

```bash
python3 scripts/voice.py --provider edge --lang zh --list-voices
python3 scripts/voice.py --provider qwen-demo --list-voices
python3 scripts/voice.py --provider edge --lang en --voice en-US-JennyNeural --text-file audition.en.txt --stage audition --output audition.en.wav
python3 scripts/voice.py --selection audition.en.voice.json --text-file approved.en.txt --stage full --output narration.en.wav
python3 scripts/voice.py --provider existing --input recorded.zh.wav --text-file approved.zh.txt --tempo 1.10 --output narration.zh.wav
```

`--rate=+10%` 是 Edge 的合成语速；`--tempo 1.10` 是 FFmpeg 保音高后期提速。默认都不加速，避免无意叠加两个 10%。复用选定试听时用 `--selection`，可调整 `tempo`/`rate`，但不能无声地换服务商、音色、语言、模型或风格。需要修改风格时先生成同音色的新试听，再引用新报告。

脚本默认保留完整首尾、不裁中间停顿；`--trim-edge-silence` 只对检测到的首尾静音做可选裁剪，保留约 80 ms 开头和 150 ms 结尾，仍需试听。不要为“第一句太慢”去掉字词。先试听前 3–5 秒，用同声线调整开场表达或适量保音高提速；改动声音时重新生成字幕和镜头时间轴。仅给已有成片加音乐时不可改变旁白时长。

默认旁白为 48 kHz / 24-bit WAV，经两遍响度处理，目标 -18 LUFS、真峰值 -1.5 dBTP。参数可调，报告记录真实测量，不保证所有素材机械地精确命中目标。已有满意母带可用 `--no-normalize`。审核开场节奏、店名/地名/数字、全文是否漏读重复，以及最后一个字和尾音；脚本的完整解码检查不能代替听审和文案对照。

### 配额、失败和其他 TTS

Qwen 官方演示仅执行一次合成提交与有界等待。HTTP 429、`quota exceeded`、ZeroGPU 配额等立即停止，写入 `.voice.json`，返回退出码 3；不拆文案绕额度、不换账号、不无限重试、不擅自换音色。网络/格式错误也停止，保留原始请求信息便于定位；失败后使用新的输出名，只有用户要求重试或已确认服务恢复时再重新提交。演示服务不适合承诺商用批量稳定性。

Azure、火山/豆包、ElevenLabs、MiniMax、Fish、阿里云生产 API 等**未内置适配器**。若目标用户已有服务，按下面合同接入或先由该服务导出音频，再用 `existing`。

适配器合同：输入必须包括批准全文的 UTF-8/SHA-256、明确的 provider/model/voice/language、速度和风格参数；鉴权来自用户明确提供的环境变量，不写入报告；开始前查询当前官方 API/音色和商用使用条件；一次生成连续完整旁白，保留原始音频、响应 request ID、参数和输出 SHA-256；错误分类为 quota/auth/validation/temporary，记录明确停止原因，不自动切服务或声线。合成后进入同一音频处理/听审/对齐流程。不得把未实际实现的供应商标为“已支持”。

### 选择配乐

用户可指定本地音乐、已授权平台曲目或“无音乐”；已有选择持续生效。未指定时可挑 2–3 段短样对比，例如餐饮的轻快器乐、住宿的低密度温暖器乐。不要把这些风格当规则；低密度、无强人声竞争通常更利于听清信息。没有已核实授权的音乐时交付干声预览，并说明配乐仍待选择。

脚本只接收本地文件，不下载曲目。能下载、标成“免版税”、抖音/TikTok 曲库可试听，都不等于可以跨平台、跨地区或投广告。从实际曲目的官方页面/合同确认商业同步、目标平台、地区/到期日及付费广告范围，保存证据后填写 manifest。manifest 的布尔值是核实结果，**不是凭空创造授权**。`organic` 指商家自然发布，仍属商业用途；只有明确要投广告才用 `--usage ads`。

```json
{
  "title": "曲目真实标题",
  "author": "真实作者或权利人",
  "license": "CUSTOM",
  "source_url": "https://rights-holder.example/track",
  "license_url": "https://rights-holder.example/license",
  "evidence_file": "saved-license.txt",
  "sha256": "实际音乐文件的64位SHA-256",
  "commercial_use_allowed": true,
  "synchronization_allowed": true,
  "paid_ads_allowed": false,
  "platforms": ["douyin", "tiktok"],
  "attribution_required": true,
  "attribution": "官方许可所要求的完整署名文字",
  "expires_on": "2030-12-31"
}
```

上例仅说明字段，不是授权文件。`evidence_file` 相对于 manifest 所在目录；`expires_on` 仅在有到期日时填写。允许标识为 `CC0-1.0`、`CC-BY-3.0`、`CC-BY-4.0`、`CUSTOM`、`OWNED`，但均须核实真实来源。CC 曲目必须记录官方来源和许可链接；`CUSTOM`/`OWNED` 必须有保存的授权/权属证据。NC、ND、未知许可、文件哈希不符、未覆盖平台或未覆盖所请求广告用途都会停止。复杂的限制条件应人工确认，必要时换曲目；不要把未知授权改名成 `CUSTOM`。

```bash
python3 scripts/mix_audio.py --video picture.zh.mp4 --voice narration.zh.wav --music licensed-track.wav --music-license music-license.json --platform douyin --usage organic --output final.zh.mp4
python3 scripts/mix_audio.py --video picture.en.mp4 --voice narration.en.wav --music none --platform tiktok --output final.en.mp4
```

默认音乐先按约 -30 LUFS 设置增益，讲话时再衰减最多 3.5 dB，淡入 0.75 秒、淡出 1.4 秒；均可配置。不自动循环短音乐，显式 `--loop-music` 后需听循环接缝。旁白从第 0 秒开始，只补尾静音，不重采样、不移位、不裁尾、不归一化总混音：单声道按 1.0 增益复制到左右声道，立体声各声道保幅；峰值冲突时只降低音乐。旁白长于视频时停止，先重建视频时间轴。

`mix_audio.py` 复制视频与字幕流，不重编码画面；校验视频/内嵌字幕的包内容和时间戳、外置 SRT/VTT/ASS 的哈希，保留音乐署名及许可证据。输出包含 `.mix.json` 和 `.audio/` 内的混音/干声/音乐 WAV，供复核。AAC 压缩有损，不能声称成片中的旁白比特完全不变；报告验证的是**编码前每声道旁白贡献与时间不变**，并给出浮点误差及编码后真峰值。发布时将 `music-credits.txt` 所需署名带入视频描述/署名处；只保存 sidecar 不能代替公开署名。

## English

### Choose and keep a voice

Audition the same 8–15 second passage with two or three candidates. Include the opening, business name, a number, and a natural ending. Reuse a voice the user has already chosen; do not ask again or silently switch it. Keep provider, voice ID, language, model, and delivery instruction from the selected audition. Submit the complete approved script in one request instead of synthesizing every sentence separately. Generate and align Chinese and English independently.

Implemented providers:

- `edge`: `edge-tts`; query the live catalog before using candidates such as Chinese Xiaoxiao/Yunxi or English Jenny/Guy. Candidate IDs appear in the table above. Availability and commercial terms require separate verification.
- `qwen-demo`: the official Qwen3-TTS CustomVoice demo; its current schema and voice enums are checked before submission. Serena is one Chinese candidate; Ryan and Aiden are English candidates if currently listed. Serena was a preference in the reference project, not a universal business default. The demo has no production availability promise.
- `existing`: local recordings or audio exported from a provider the user has selected. No voice ID or remote request is required.

Use `--selection selected.voice.json` for the full take. Edge `--rate=+10%` changes synthesis rate; `--tempo 1.10` speeds the recording with pitch preserved. They are separate controls and do not need to be combined. The helper leaves the beginning, ending, and internal pauses intact by default. Optional `--trim-edge-silence` keeps conservative guards and still requires listening. If the first sentence feels slow, audition that opening using the same voice; never remove approved words. Rebuild caption/shot timing whenever narration timing changes.

The default master is 48 kHz / 24-bit WAV, with two-pass loudness processing targeting -18 LUFS and -1.5 dBTP. The report records actual measurements. Use `--no-normalize` for an already approved master when appropriate. Listen to the opening, names/numbers, entire text, and last word; decoding successfully is not evidence of correct pronunciation or complete narration.

Quota errors stop immediately, with exit code 3 and a saved error report. The Qwen adapter performs one generation POST and one bounded wait, with no automatic retries. Do not split text, change accounts, or switch voices to evade a limit. Network and schema failures also stop. Preserve the selected take and resume only after an explicit retry request or confirmed service recovery, using a new output name.

Commercial providers such as Azure, Doubao, ElevenLabs, MiniMax, Fish, and production Alibaba Cloud TTS are **not built-in adapters**. Implement against their current official API or import their output with `existing`. An adapter must preserve the approved text/hash and selected voice/model/language/settings, use authorized credentials without logging secrets, save the raw take and request ID, return output duration/hash, and classify quota/auth/validation/temporary failures without automatic voice or provider substitution.

### Choose and license music

Use the user's chosen local track, authorized platform track, or no music. If they have no preference, offer a few short suitable excerpts. Do not promise that downloadable, royalty-free, or platform-previewable music is cleared for a commercial business, both platforms, every territory, or paid advertising. Verify the actual track's official license/contract, keep the evidence, and record its scope. A manifest records verified rights; its booleans do not create permission.

`--usage organic` is the default and still means commercial business use. Choose `ads` only for paid advertising; it requires `paid_ads_allowed: true`. The license manifest above shows the fields, not a usable license. Bind it to the exact music file with SHA-256 and list only covered platforms. Preserve required attribution. NC, ND, unknown licenses, mismatched files, expired rights, or missing requested platform/ad coverage stop the mix. `CUSTOM` or `OWNED` requires a saved evidence file; do not relabel unknown music as custom.

The mixer receives local files only. Default bed loudness is approximately -30 LUFS before up to 3.5 dB speech ducking, with 0.75 s fade-in and 1.4 s fade-out. These are adjustable starting points. Short music is not looped unless `--loop-music` is explicit. Narration starts at zero and retains all samples: mono duplicates to left/right at unity gain, stereo channels keep their original amplitudes, and only tail silence may be added. Peak collisions reduce music only. If narration outlasts the video, rebuild the timeline instead of cutting the narration.

Video and embedded subtitle streams are copied without re-encoding; packet contents and timing are checked. Sidecar SRT/VTT/ASS files are copied byte-for-byte. The report and `.audio/` stems verify that narration timing and per-channel contribution are unchanged **before** lossy AAC encoding; do not claim bit-identical narration in the AAC delivery. Keep `music-credits.txt` and include any required credit in the published caption/credits—the local file alone does not satisfy public attribution.

Run examples from the user project and replace `scripts/` with the installed skill scripts path. Do not create audio or reports inside the skill installation.

## Runtime and help / 运行环境

Python 3.10+, FFmpeg/ffprobe on PATH; `numpy` is required for mixing. `edge-tts` is optional and required only for Edge. Qwen uses Python's standard HTTP library, validates the live official demo, and sends only the supplied text/settings. No credentials, accounts, browser data, or music are bundled.

```bash
python3 scripts/voice.py --help
python3 scripts/mix_audio.py --help
```
