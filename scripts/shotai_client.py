#!/usr/bin/env python3
"""Local-only ShotAI MCP SSE fallback. Prefer host-provided MCP tools when available."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

DEFAULT_URL = "http://127.0.0.1:23817/sse"
PROTOCOL_VERSION = "2024-11-05"
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ShotAIError(Exception):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details

    def as_dict(self) -> dict:
        value = {"code": self.code, "message": self.message}
        if self.details is not None:
            value["details"] = self.details
        return value


def local_url(value: str) -> str:
    """Do not resolve arbitrary hostnames, follow redirects, or consult proxies."""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("Invalid URL components")
        # Pin localhost to a numeric loopback address rather than trusting DNS.
        if host == "localhost":
            host = "127.0.0.1"
        address = ipaddress.ip_address(host)
        if not address.is_loopback:
            raise ValueError("Not loopback")
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        authority = f"[{host}]" if address.version == 6 else host
        if port is not None:
            authority += f":{port}"
        return urlunsplit((parsed.scheme, authority, parsed.path or "/", parsed.query, ""))
    except (ValueError, TypeError) as exc:
        raise ShotAIError("unsafe_url", "ShotAI must use an HTTP(S) loopback URL without credentials or fragments.") from exc


def origin(value: str) -> tuple:
    parsed = urlsplit(value)
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Sanitize structured results and JSON encoded inside MCP text blocks."""
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            sensitive = ("token" in normalized or normalized in {"authorization", "apikey", "password", "secret", "clientsecret", "sessionid", "cookie", "setcookie"})
            output[key] = "[REDACTED]" if sensitive else redact(item, secrets)
        return output
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [redact(item, secrets) for item in value]
    if not isinstance(value, str):
        return value
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    stripped = value.strip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except (ValueError, RecursionError):
            pass
        else:
            return json.dumps(redact(decoded, secrets), ensure_ascii=False)
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?i)([?&](?:[^=&\s]*token|api[_-]?key|session[_-]?id)=)[^&\s\"'<>]+", r"\1[REDACTED]", value)
    return value


def service_error(result: Any) -> dict | None:
    """MCP errors may be nested in a text block even with HTTP/JSON-RPC success."""
    if not isinstance(result, dict):
        return None
    if result.get("isError") is True:
        return {"reason": "MCP isError=true", "result": result}
    candidates = [result]
    if isinstance(result.get("structuredContent"), dict):
        candidates.append(result["structuredContent"])
    content = result.get("content")
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                decoded = json.loads(block.get("text", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(decoded, dict):
                candidates.append(decoded)
    for candidate in candidates:
        if candidate.get("error") or candidate.get("errors") or candidate.get("success") is False:
            return {"reason": "Structured service error", "result": candidate}
        if candidate.get("failedShots"):
            return {"reason": "One or more shots failed (possibly a partial export)", "result": candidate}
    return None


class ShotAIClient:
    def __init__(self, url: str = DEFAULT_URL, token: str | None = None, timeout: float = 120, startup_timeout: float = 10):
        self.url = local_url(url)
        if urlsplit(self.url).query:
            raise ShotAIError("unsafe_url", "Do not put credentials or query parameters in SHOTAI_URL; use SHOTAI_TOKEN or --token-file.")
        if timeout <= 0 or startup_timeout <= 0:
            raise ShotAIError("configuration_error", "Timeouts must be positive.")
        if token and ("\r" in token or "\n" in token):
            raise ShotAIError("configuration_error", "The token must be a single line.")
        self.timeout, self.startup_timeout = timeout, startup_timeout
        self._token = token or ""
        self._endpoint: str | None = None
        self._condition = threading.Condition()
        self._ready, self._closed = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._stream_socket: socket.socket | None = None
        self._stream_connection: http.client.HTTPConnection | None = None
        self._error: ShotAIError | None = None
        self._sequence = 0
        self._pending: set[int] = set()
        self._replies: dict[int, dict] = {}
        self.calls: list[dict] = []
        self.initialized = False
        self.server_info: Any = None

    def __enter__(self) -> ShotAIClient:
        return self.connect()

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, text/event-stream", "User-Agent": "shotai-business-video/1.0"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        return headers

    @staticmethod
    def _connection(url: str, timeout: float) -> http.client.HTTPConnection:
        parsed = urlsplit(url)
        cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        return cls(parsed.hostname, parsed.port, timeout=timeout)

    @staticmethod
    def _target(url: str) -> str:
        parsed = urlsplit(url)
        return parsed.path + ("?" + parsed.query if parsed.query else "")

    def connect(self) -> ShotAIClient:
        if self._thread is not None:
            raise ShotAIError("client_state", "Create a new client for each SSE session.")
        self._thread = threading.Thread(target=self._listen, name="shotai-sse", daemon=True)
        self._thread.start()
        try:
            if not self._ready.wait(self.startup_timeout):
                raise ShotAIError("startup_timeout", "The SSE server did not supply a message endpoint before the startup timeout.")
            if self._error:
                raise self._error
            response = self.call("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "shotai-business-video", "version": "1.0"}}, timeout=self.startup_timeout)
            if not isinstance(response, dict) or response.get("protocolVersion") != PROTOCOL_VERSION:
                raise ShotAIError("protocol_error", "The server did not negotiate the supported MCP protocol version.", response)
            self.server_info = response.get("serverInfo")
            self.notify("notifications/initialized")
            self.initialized = True
            return self
        except BaseException:
            self.close()
            raise

    def _fail(self, error: ShotAIError) -> None:
        with self._condition:
            if not self._closed.is_set():
                self._error = error
            self._ready.set()
            self._condition.notify_all()

    def _event(self, event: str, data: str) -> None:
        if event == "endpoint":
            endpoint = local_url(urljoin(self.url, data.strip()))
            if origin(endpoint) != origin(self.url):
                raise ShotAIError("unsafe_endpoint", "The SSE message endpoint must use the same local origin.")
            if self._endpoint and endpoint != self._endpoint:
                raise ShotAIError("protocol_error", "The server changed the active SSE message endpoint.")
            self._endpoint = endpoint
            self._ready.set()
            return
        try:
            message = json.loads(data)
        except ValueError as exc:
            raise ShotAIError("protocol_error", "The SSE server returned invalid JSON.") from exc
        if not isinstance(message, dict):
            raise ShotAIError("protocol_error", "The SSE message must be a JSON-RPC object.")
        with self._condition:
            request_id = message.get("id")
            if isinstance(request_id, int) and request_id in self._pending:
                self._replies[request_id] = message
                self._condition.notify_all()

    def _listen(self) -> None:
        connection = self._connection(self.url, self.startup_timeout)
        self._stream_connection = connection
        try:
            connection.connect()
            self._stream_socket = connection.sock
            if self._closed.is_set():
                return
            connection.request("GET", self._target(self.url), headers=self._headers())
            response = connection.getresponse()
            if response.status != 200:
                raise ShotAIError("http_error", f"SSE connection returned HTTP {response.status}; redirects are not followed.")
            if "text/event-stream" not in response.getheader("Content-Type", "").lower():
                raise ShotAIError("protocol_error", "The server did not return text/event-stream.")
            # Calls have their own deadlines; an idle stream must not expire.
            if self._stream_socket:
                self._stream_socket.settimeout(None)
            event, data, size = "message", [], 0
            while not self._closed.is_set():
                raw = response.readline(MAX_MESSAGE_BYTES + 1)
                if not raw:
                    raise ShotAIError("disconnected", "The SSE connection closed before the client finished.")
                size += len(raw)
                if size > MAX_MESSAGE_BYTES:
                    raise ShotAIError("protocol_error", "The SSE event exceeded the message size limit.")
                line = raw.decode("utf-8").rstrip("\r\n")
                if not line:
                    if data:
                        self._event(event, "\n".join(data))
                    event, data, size = "message", [], 0
                elif line.startswith(":"):
                    continue
                else:
                    field, _, value = line.partition(":")
                    value = value[1:] if value.startswith(" ") else value
                    if field == "event":
                        event = value
                    elif field == "data":
                        data.append(value)
        except ShotAIError as exc:
            self._fail(exc)
        except (OSError, http.client.HTTPException, UnicodeError) as exc:
            self._fail(ShotAIError("transport_error", f"SSE transport failed: {type(exc).__name__}."))
        finally:
            connection.close()

    def _post(self, payload: dict, timeout: float) -> None:
        if self._closed.is_set() or self._error:
            raise self._error or ShotAIError("client_closed", "The client is closed.")
        if not self._endpoint:
            raise ShotAIError("client_state", "No SSE message endpoint is available.")
        connection = self._connection(self._endpoint, timeout)
        expired = threading.Event()
        active_socket: list[socket.socket] = []

        def expire() -> None:
            expired.set()
            if active_socket:
                try:
                    active_socket[0].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                active_socket[0].close()

        # Socket timeouts alone restart on every read; bound slow HTTP replies too.
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {**self._headers(), "Content-Type": "application/json"}
            connection.connect()
            if connection.sock:
                active_socket.append(connection.sock)
            if expired.is_set():
                raise ShotAIError("request_timeout", "The MCP connection exceeded its deadline before sending the request.")
            connection.request("POST", self._target(self._endpoint), body=body, headers=headers)
            response = connection.getresponse()
            content = response.read(MAX_MESSAGE_BYTES + 1)
            if expired.is_set():
                raise ShotAIError("request_timeout", "The MCP POST exceeded its deadline; its server-side outcome may be unknown.")
            if len(content) > MAX_MESSAGE_BYTES:
                raise ShotAIError("protocol_error", "The HTTP response exceeded the message size limit.")
            if not 200 <= response.status < 300:
                raise ShotAIError("http_error", f"MCP request returned HTTP {response.status}; redirects are not followed.", content[:4096].decode("utf-8", errors="replace"))
        except (TimeoutError, socket.timeout) as exc:
            raise ShotAIError("request_timeout", "The MCP POST timed out; its server-side outcome may be unknown.") from exc
        except (OSError, http.client.HTTPException) as exc:
            if expired.is_set():
                raise ShotAIError("request_timeout", "The MCP POST exceeded its deadline; its server-side outcome may be unknown.") from exc
            raise ShotAIError("transport_error", f"MCP POST failed: {type(exc).__name__}. Its server-side outcome may be unknown.") from exc
        finally:
            timer.cancel()
            connection.close()

    def _record(self, method: str, params: Any, request_id: int | None) -> tuple[dict, float]:
        record = {"method": method, "request_id": request_id, "started_at": utc_now(), "status": "pending", "params": redact(params, (self._token,))}
        with self._condition:
            self.calls.append(record)
        return record, time.monotonic()

    @staticmethod
    def _finish(record: dict, started: float, error: ShotAIError | None = None) -> None:
        record.update({"finished_at": utc_now(), "duration_ms": round((time.monotonic() - started) * 1000, 2), "status": error.code if error else "success"})

    def notify(self, method: str, params: dict | None = None) -> None:
        record, started = self._record(method, params, None)
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        try:
            self._post(payload, self.timeout)
        except ShotAIError as exc:
            self._finish(record, started, exc)
            raise
        self._finish(record, started)

    def call(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        timeout = self.timeout if timeout is None else timeout
        with self._condition:
            self._sequence += 1
            request_id = self._sequence
            self._pending.add(request_id)
        record, started = self._record(method, params or {}, request_id)
        deadline = started + timeout
        try:
            self._post({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}, timeout)
            with self._condition:
                while request_id not in self._replies:
                    if self._error or self._closed.is_set():
                        raise self._error or ShotAIError("client_closed", "The client closed during the request.")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ShotAIError("request_timeout", f"{method} did not return before the deadline; its server-side outcome may be unknown.")
                    self._condition.wait(remaining)
                reply = self._replies.pop(request_id)
            if "error" in reply:
                raise ShotAIError("rpc_error", "ShotAI returned a JSON-RPC error.", reply["error"])
            if "result" not in reply:
                raise ShotAIError("protocol_error", "The JSON-RPC response has neither a result nor an error.")
            result = reply["result"]
            if method == "tools/call":
                error = service_error(result)
                if error:
                    raise ShotAIError("tool_error", error["reason"], error["result"])
            self._finish(record, started)
            return result
        except ShotAIError as exc:
            self._finish(record, started, exc)
            raise
        finally:
            with self._condition:
                self._pending.discard(request_id)
                self._replies.pop(request_id, None)

    def list_tools(self, cursor: str | None = None) -> Any:
        return self.call("tools/list", {"cursor": cursor} if cursor else {})

    def tool(self, name: str, arguments: dict) -> Any:
        return self.call("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        self._closed.set()
        with self._condition:
            self._condition.notify_all()
        if self._stream_socket:
            try:
                self._stream_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._stream_socket.close()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=min(self.startup_timeout + 0.2, 2))
        if self._stream_connection:
            self._stream_connection.close()

    def evidence(self) -> dict:
        return {"transport": "live_mcp_sse", "cache_used": False, "server_initialized": self.initialized, "server_url": self.url, "server_info": self.server_info, "calls": self.calls}


def read_token(filename: str | None) -> str | None:
    if filename:
        token = Path(filename).expanduser().read_text(encoding="utf-8").strip()
        if not token:
            raise ShotAIError("configuration_error", "The explicitly supplied token file is empty.")
        return token
    return os.environ.get("SHOTAI_TOKEN", "").strip() or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("SHOTAI_URL", DEFAULT_URL))
    parser.add_argument("--token-file", help="Explicit path to a plain-text bearer token. Overrides SHOTAI_TOKEN.")
    parser.add_argument("--timeout", type=float, default=120, help="Per-request deadline in seconds (default: 120).")
    parser.add_argument("--startup-timeout", type=float, default=10, help="SSE/initialize timeout in seconds (default: 10).")
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("tools/list", aliases=["list"], help="Fetch the current server tool list.")
    list_parser.add_argument("--cursor", help="Pagination cursor returned by the previous tools/list call.")
    list_parser.add_argument("--output", help="Write the sanitized JSON result and call evidence here.")
    call_parser = sub.add_parser("call", help="Call a named ShotAI tool with a JSON object from a file.")
    call_parser.add_argument("tool")
    call_parser.add_argument("--args-json", required=True, help="JSON object file; pass an empty object for no arguments.")
    call_parser.add_argument("--output", help="Write the sanitized JSON result and call evidence here.")
    args = parser.parse_args(argv)
    client, token = None, None
    envelope: dict = {"ok": False, "recorded_at": utc_now()}
    exit_code = 1
    try:
        token = read_token(args.token_file)
        arguments = {}
        if args.command == "call":
            arguments = json.loads(Path(args.args_json).expanduser().read_text(encoding="utf-8"))
            if not isinstance(arguments, dict):
                raise ShotAIError("input_error", "--args-json must contain a JSON object.")
        client = ShotAIClient(args.url, token, args.timeout, args.startup_timeout)
        with client:
            result = client.tool(args.tool, arguments) if args.command == "call" else client.list_tools(args.cursor)
        envelope.update({"ok": True, "result": result})
        exit_code = 0
    except ShotAIError as exc:
        envelope["error"] = exc.as_dict()
        exit_code = 3 if exc.code.endswith("timeout") else 2
    except (OSError, ValueError) as exc:
        envelope["error"] = {"code": "input_or_io_error", "message": f"Could not read configuration or arguments: {type(exc).__name__}."}
        exit_code = 2
    except KeyboardInterrupt:
        if client:
            client.close()
        envelope["error"] = {"code": "interrupted", "message": "Interrupted; an in-flight server action may still finish."}
        exit_code = 130
    envelope["evidence"] = client.evidence() if client else {"transport": "not_started", "cache_used": False, "server_initialized": False, "calls": []}
    output = json.dumps(redact(envelope, (token or "",)), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            path = Path(args.output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
        except OSError:
            print(output, end="")
            print("Could not write --output; the sanitized report is on stdout.", file=sys.stderr)
            return 2
    else:
        print(output, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
