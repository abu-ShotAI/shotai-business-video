# ShotAI MCP：接入、参数与调用证据

[English](../shotai-mcp.md) · [中文完整流程](../workflow.zh.md)

## 客户端与素材库前提

**先从 [ShotAI 官网](https://www.shotai.io) 下载并安装客户端。** 在客户端创建本店集合，导入有权使用的视频，等待镜头分析与索引完成，再启用 MCP 并连接代理；使用期间保持客户端及 MCP 服务可用。先用 `list_collections` 确认本店集合，再限定该集合执行一条 `search_shots` 验证。详见 [安装与开始](setup.md)。

仅在硬盘上存有文件、安装技能或填写路径，均不等于 ShotAI 已入库。连接失败或搜不到素材时，先检查客户端/服务是否可用、集合是否正确、导入与索引是否完成；不要直接把空结果当作素材不存在。

## 接入顺序

1. 优先使用当前会话已经可调用的 ShotAI MCP 工具。先发现工具，再读取实时工具说明 / schema；按真实名称调用，不把本脚本当成必要依赖。宿主 MCP 连接已负责认证时，不读取或复制它的凭据。
2. 只有宿主未暴露相应工具，且用户的本机 ShotAI 已启用 SSE 服务时，才使用 `scripts/shotai_client.py`。Python 3.10+，仅标准库。
3. 脚本只接受 HTTP(S) 回环地址。`localhost` 固定转成 `127.0.0.1`，其余只接受回环 IP；SSE 返回的消息端点必须与初始地址同源。不会使用环境代理或跟随 HTTP 重定向。远程 MCP 连接应交给宿主管理，不能用本后备脚本携带令牌连接远端。

默认地址为 `http://127.0.0.1:23817/sse`。可通过 `SHOTAI_URL` 或 `--url` 调整本机端口。令牌只来自 `SHOTAI_TOKEN` 或用户明确指定的 `--token-file`（纯文本单行，优先于环境变量）；若服务未启用认证，可不提供令牌。不会自动搜索数据库、钥匙串、配置目录或旧任务缓存。不要把令牌写进技能、参数 JSON、命令行字面值或输出包。

以下命令从用户项目目录运行，把 `scripts/shotai_client.py` 换成技能中脚本的绝对路径；`mcp/` 是用户项目输出目录，不在技能安装目录创建：

```bash
python3 scripts/shotai_client.py tools/list --output mcp/tools-live.json
python3 scripts/shotai_client.py call list_collections --args-json mcp/empty.json --output mcp/collections-live.json
python3 scripts/shotai_client.py call search_shots --args-json mcp/search-args.json --output mcp/search-live.json
```

`empty.json` 的内容为 `{}`。有分页时使用服务实际返回的 `nextCursor`：

```bash
python3 scripts/shotai_client.py tools/list --cursor RETURNED_CURSOR --output mcp/tools-page-2-live.json
python3 scripts/shotai_client.py --token-file /path/to/private/shotai-token.txt --timeout 120 call get_shot --args-json mcp/shot-args.json --output mcp/shot-live.json
```

全局选项必须放在 `tools/list` / `call` 前。显式凭据文件只用于本机读取，不纳入成品或分享包。

## 搜索与导出

先列集合，限定本次商家的真实素材集合，再逐句搜索。把查询、候选 shot ID、实际选中理由和不足项留在项目记录中。搜索是找候选；必须查看镜头元数据并抽帧确认画面。镜头的语义相关性、业务归属、源文件和时长均需核对。

搜索参数示例（集合 ID 必须来自本次真实返回）：

```json
{
  "query": "门头入口，客人走入店内，干净明亮的接待空间",
  "collectionIds": ["ACTUAL_COLLECTION_ID"],
  "durationRange": {"min": 1.5},
  "limit": 12
}
```

```json
{
  "shotIds": ["ACTUAL_SHOT_ID"],
  "outputDir": "/absolute/path/to/current-project/mcp-exports",
  "format": "mp4",
  "quality": "high",
  "includeAudio": false
}
```

`export_shots` 会写本地文件；只导出此次项目选中的镜头到本次输出目录。不要为了生成视频创建、重命名或删除用户的媒体库集合，也不要自动导入无关素材。若服务返回后台任务 ID，用 `get_task_status` 查询完成状态，再检查实际文件。只有用户需要剪辑工程交换文件时才用 `export_shots_as_timeline`；它的 `outputPath` 在下述已核对版本中表示**目录**。

## schema 不完整时

实时 `tools/list` 优先。一些 ShotAI 版本只返回 `{"$schema": "http://json-schema.org/draft-07/schema#"}`；这不代表工具没有参数，也不是完整的输入 schema。

下面是历史兼容性参考，**不是当前服务返回的 JSON Schema**。来源：2026-09-23 的上一轮项目留存 `verified_tool_schemas.json`，当时通过只读检查已安装 ShotAI 应用的 `app.asar` 内 `out/main/index.js` 核对。该记录未保留应用版本号，因此不能宣称适用于所有版本。这里只保留已核对参数，没有复制用户集合、媒体路径或令牌。

| 工具 | 必需参数 | 可选参数 |
|---|---|---|
| `search_shots` | `query: string` | `collectionIds: string[]`；`durationRange: {min?: number, max?: number}`；`dateRange: {start?: ISO8601 string, end?: ISO8601 string}`；`limit: number`，当时默认 20 |
| `get_shot` | `shotId: string` | 无已核对可选项 |
| `export_shots` | `shotIds: string[]` | `outputDir: string`；`format: mp4 / mov`；`quality: high / medium / low`；`includeAudio: boolean`。当时默认值为 mp4、high、true |
| `export_shots_as_timeline` | `shotIds: string[]`；`format: edl / fcp7xml / fcpxml / otio` | `outputPath: string`（输出目录）；`projectName: string`；`frameRate: number`，当时默认 30 |
| `get_task_status` | 无 | `taskIds: string[]` |

同一历史运行还成功以 `{}` 调用过 `list_collections`。对没有完整 schema 的新版本，保留本次原始 `tools/list`，在 `schema-basis.json` 写明使用此兼容参考的原因、来源日期和版本未知；若当前只读调用返回参数错误，依据错误或用户授权的本地文档调整。不发送有副作用的“探测调用”猜参数。不要把自己整理的参数表包装成实时 schema。

## 调用证据与错误

CLI 每次写一个 JSON envelope：

```json
{
  "ok": true,
  "recorded_at": "UTC_TIMESTAMP",
  "result": {},
  "evidence": {
    "transport": "live_mcp_sse",
    "cache_used": false,
    "server_initialized": true,
    "server_url": "http://127.0.0.1:23817/sse",
    "server_info": {},
    "calls": []
  }
}
```

`result` 保留服务原始结构并清理凭据；MCP `content[].text` 里可能仍是 JSON 字符串，按需解析。`evidence.calls` 记录每次实际请求的方法、参数、请求 ID、开始/结束 UTC 时间、耗时和状态，包含初始化及通知。`transport` 只说明本次尝试使用 SSE；连接成功需看 `server_initialized`，请求成功需看 `ok` 和对应调用的 `status`。初始化失败也会写报告。服务端消息端点的会话查询串不写入证据。

退出码：`0` 成功，`2` 配置 / 传输 / 服务错误，`3` 超时，`130` 中断。脚本识别 JSON-RPC `error`、MCP `isError`、结构化内容或文本 JSON 中的 `error` / `errors` / `success: false`，并把非空 `failedShots` 视为可能部分成功的失败。不要仅凭 HTTP 200 或 POST 202 判定工具成功。未知文本仍需要操作者判断。

超时或中断不代表服务端动作取消；导出可能已部分完成。先核查当前输出文件或已返回的任务状态，避免盲目重放写操作。脚本不自动重试，不自动重新连接，也不读取缓存；每个命令关闭连接并结束监听线程。较大的导出可显式提高 `--timeout`。

使用宿主 MCP 工具时，也保存本次实际工具名、参数、调用时间、返回结果和错误。复用旧候选时标为 `cached_prior_run` 并附原调用时间；当本次没有调用 ShotAI 时，不能称为“本次已实时检索”。
