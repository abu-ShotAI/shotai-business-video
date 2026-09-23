# ShotAI MCP: connection, parameters and call evidence

Optional documentation: [Chinese MCP guide](zh-CN/shotai-mcp.md).

## Client and library prerequisites

**First download and install the [ShotAI desktop client](https://www.shotai.io).** In the client, create a collection for the business, import videos the owner has the right to use, wait for shot analysis/indexing to finish, then enable MCP and connect the agent. Keep the client and MCP service available during use. Confirm the collection with `list_collections`, then run one `search_shots` query restricted to it. See [Setup](setup.md).

Files stored only on disk, installing a skill or supplying paths do not mean footage has entered the ShotAI library. For connection failures or empty searches, check client/service availability, collection selection, import completion and indexing before concluding that footage is absent.

## Connection order

1. Prefer ShotAI MCP tools already callable in the current session. Discover tools and read their live descriptions/schemas; use the actual tool names. The bundled client is not mandatory. When the host handles authentication, do not read or copy its credentials.
2. Use `scripts/shotai_client.py` only when the host does not expose the required tools and the user's local ShotAI SSE service is already enabled. It requires Python 3.10+ and only the standard library.
3. The helper accepts HTTP(S) loopback addresses only. It resolves `localhost` to `127.0.0.1` and accepts only loopback IPs otherwise. The message endpoint returned by SSE must share the initial origin. It ignores environment proxies and follows no HTTP redirects. Let the host manage remote MCP connections; do not use this fallback to carry a token to a remote host.

The default endpoint is `http://127.0.0.1:23817/sse`. Change the local port with `SHOTAI_URL` or `--url`. Tokens come only from `SHOTAI_TOKEN` or a user-specified `--token-file` containing one plaintext line; the explicit file takes precedence. No token is required if the service has no authentication. The helper does not search databases, keychains, configuration folders or old job caches. Never put tokens in the skill, argument JSON, literal command-line values or output packages.

Run from the user's project, replacing `scripts/shotai_client.py` with its installed absolute path. `mcp/` is a project output folder, never inside the installed skill:

```bash
python3 scripts/shotai_client.py tools/list --output mcp/tools-live.json
python3 scripts/shotai_client.py call list_collections --args-json mcp/empty.json --output mcp/collections-live.json
python3 scripts/shotai_client.py call search_shots --args-json mcp/search-args.json --output mcp/search-live.json
```

`empty.json` contains `{}`. For pagination, use the actual returned `nextCursor`:

```bash
python3 scripts/shotai_client.py tools/list --cursor RETURNED_CURSOR --output mcp/tools-page-2-live.json
python3 scripts/shotai_client.py --token-file /path/to/private/shotai-token.txt --timeout 120 call get_shot --args-json mcp/shot-args.json --output mcp/shot-live.json
```

Global options must precede `tools/list` or `call`. Credential files are read locally and must not enter final deliverables or shared packages.

## Search and export

List collections first, scope to the current business's actual collection, then search each script intent. Save queries, candidate shot IDs, selection reasons and footage gaps. Search finds candidates: inspect metadata and frames to verify semantic relevance, business ownership, source files and duration.

Example search parameters; collection IDs must come from the current real response:

```json
{
  "query": "The storefront entrance, a guest walking inside, and a clean bright reception area",
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

`export_shots` writes local files. Export only selected shots into the current job output directory. Video creation does not require creating, renaming or deleting the owner's library collections or importing unrelated footage. If a background task ID is returned, use `get_task_status` to confirm completion and inspect actual files. Use `export_shots_as_timeline` only when the user needs an editing-project interchange file; in the historically checked version below, `outputPath` means a **directory**.

## Incomplete schemas

The live `tools/list` takes precedence. Some ShotAI versions return only `{"$schema": "http://json-schema.org/draft-07/schema#"}`. This is neither a complete input schema nor evidence that the tool takes no arguments.

The following is a dated compatibility reference, **not JSON Schema returned by the current server**. Source: a previous project's `verified_tool_schemas.json` on 2026-09-23, checked by read-only inspection of `out/main/index.js` in the installed ShotAI application's `app.asar`. That record did not retain an application version, so applicability to other versions is unknown. Only verified parameter details are retained here, with no user collection, media path or token.

| Tool | Required parameters | Optional parameters |
|---|---|---|
| `search_shots` | `query: string` | `collectionIds: string[]`; `durationRange: {min?: number, max?: number}`; `dateRange: {start?: ISO8601 string, end?: ISO8601 string}`; `limit: number`, then defaulting to 20 |
| `get_shot` | `shotId: string` | None verified |
| `export_shots` | `shotIds: string[]` | `outputDir: string`; `format: mp4 / mov`; `quality: high / medium / low`; `includeAudio: boolean`. Historical defaults were mp4, high, true |
| `export_shots_as_timeline` | `shotIds: string[]`; `format: edl / fcp7xml / fcpxml / otio` | `outputPath: string` (output directory); `projectName: string`; `frameRate: number`, then defaulting to 30 |
| `get_task_status` | None | `taskIds: string[]` |

That run also called `list_collections` successfully with `{}`. For a new version with an incomplete schema, retain the current raw `tools/list` and record the fallback reason, reference date and unknown version in `schema-basis.json`. Adjust based on read-only parameter errors or authorized local documentation. Do not probe mutating calls to guess arguments, and do not present a hand-organized parameter table as live schema.

## Evidence and errors

Every CLI command writes a JSON envelope:

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

`result` preserves the server's original structure with credentials redacted, including JSON encoded in MCP text blocks. `content[].text` may still contain a JSON string; parse it when needed. `evidence.calls` records actual methods, arguments, request IDs, UTC start/end, elapsed time and status, including initialization and notifications. `transport` describes this attempt's SSE transport only: inspect `server_initialized` for connection success and `ok` plus each call's `status` for request success. Initialization failure still produces a report. Session query strings on the server's message endpoint are excluded from evidence.

Exit codes: `0` success, `2` configuration/transport/server error, `3` timeout, `130` interruption. The helper recognizes JSON-RPC `error`, MCP `isError`, structured/text-JSON `error`/`errors`/`success: false` and nonempty `failedShots` as possibly partial failures. HTTP 200 or POST 202 alone does not establish tool success; unknown text still requires operator judgment.

Timeout/interruption does not cancel server-side work; export may have partly completed. Inspect existing output files or returned task status before replaying a write. The helper does not automatically retry, reconnect or read caches; each command closes its connection and listener. Set a longer `--timeout` explicitly for larger exports.

When using host MCP tools, also save the actual tool name, arguments, call time, response and error. Label reused candidates `cached_prior_run` with their original call time. When this job makes no ShotAI call, do not claim live retrieval in this job.
