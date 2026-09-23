# 验收与局部修改 / Quality and revisions

## 制作事实

- 固定稿与配音一致。ASR同音字可用原文作字幕，但不能以正确字幕掩盖漏读、数字或专名误读。
- 素材属于正确商家/分店/房型；具体菜品、设施和动作可见。通用tag不等于语义验收。
- 入出时间相对于实际媒体；短素材不能冻结尾帧补时长。字幕按最终声音定时。
- 实时MCP、历史缓存、人工判断分别记录。只有本次调用才能写本次通过ShotAI。

## 验证

1. 用ffprobe核对尺寸、帧率、帧数、音画长度；完整ffmpeg解码检查。
2. 检查音频削顶、峰值、首尾完整、异常长静音。总时长正常不等于首句节奏正常。
3. 查看首尾、每镜中点及切点前后帧；竖屏看脸、招牌、餐盘是否裁掉。字幕避开平台底部及右侧UI，通常底部至少预留15%，附带竖屏渲染器默认更保守的22%，实际预览优先于固定像素。
4. 字幕不重叠、不负时长、不越界，英文不拆词，汉字不缺字。字体存在仍需看实际字形。
5. 有可用听审能力时，听开头、专名、数字、转句和收尾及音乐人声比例。无法听审就只报告ASR/技术验证。
6. 音乐许可对应实际音频SHA，署名随交付；MP4元数据不能替代发布页可见署名。

## 最小修改

| 反馈 | 处理 | 验证 |
|---|---|---|
| 首句太慢 | 缩长停顿、保留词边余量，必要时局部保音高提速 | 保存逐段原→新时间映射，后文PCM不变，字幕/画面随时间差更新 |
| 换配音 | 原稿按新声音连续合成、重新对齐 | 不套用旧字幕时码，长度变化重新检查镜头 |
| 换一个镜头 | 只对该意图用ShotAI检索/核验/导出 | 其他顺序/时长不变，记录新来源 |
| 加/换音乐 | 画面stream copy，仅混音，讲话duck、首尾fade | 视频包SHA与PTS/DTS/duration不变，字幕字节一致，旁白零时间偏移 |
| 改成英文 | 独立译稿、英文配音、字幕与时间轴 | 不把仅换字幕称英文版，品牌事实和单位不擅变 |

音频拼接在低电平区，通常约30ms淡入淡出，不能压在字头上。变速/删静音保存映射，验证后文样本一致或说明修改范围。

## 清理

保留固定稿、最终旁白、许可音源、成片/SRT、timeline、MCP证据、QA、复现参数。临时片段/抽帧可重建且无依赖缺失后，用cleanup.py显式文件清单移入任务回收目录。不要整目录删除render_work或qa，其中可能有唯一音频和记录。

## English summary

Verify decoded outputs, not just successful commands. Check exact script coverage, crop safety, frame/timestamp continuity, readable captions, unclipped audio and documented music rights. Review the changed region and affected boundaries when the rest is demonstrably identical. Music-only edits preserve picture bitstream and caption timing; speech retiming requires synchronized timeline updates. Keep word padding/fades in quiet regions. Technical checks are not listening. Cleanup only listed reproducible intermediates inside the job, retaining recovery mappings and source/final/license records.
