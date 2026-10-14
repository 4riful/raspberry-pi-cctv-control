#!/usr/bin/python3
"""Authenticated, dependency-free CCTV control web service."""

from __future__ import annotations

import argparse
import base64
import hashlib
import heapq
import hmac
import json
import mimetypes
import os
import secrets
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_BODY = 16 * 1024
MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".jpg", ".jpeg"}
SESSION_TTL = 30 * 24 * 60 * 60
SESSION_SAVE_SLACK = 60 * 60
LOGIN_WINDOW = 15 * 60
LOGIN_LIMIT = 5


def b64_id(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def token_key(token: str) -> str:
    # Sessions are stored by token hash so the on-disk file never holds a usable cookie.
    return hashlib.sha256(token.encode()).hexdigest()


def session_cookie(token: str, max_age: int = SESSION_TTL) -> str:
    return f"cctv_session={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={max_age}"


def decode_id(value: str) -> str:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()


@dataclass
class Session:
    csrf: str
    expires: float


class App:
    def __init__(self, config_path: str):
        self.config = json.loads(Path(config_path).read_text())
        self.web_root = Path(self.config["web_root"]).resolve()
        self.recordings_root = Path(self.config["recordings_root"]).resolve()
        self.credentials = json.loads(Path(self.config["credentials_file"]).read_text())
        self.session_file = Path(self.config.get("session_file", "/var/lib/cctv-control-web/sessions.json"))
        self.sessions: dict[str, Session] = {}
        self.saved_expiry: dict[str, float] = {}
        self.failures: dict[str, list[float]] = {}
        self.lock = threading.Lock()
        self.load_sessions()

    def load_sessions(self) -> None:
        try:
            raw = json.loads(self.session_file.read_text())
        except (OSError, ValueError):
            return
        now = time.time()
        for key, row in raw.items() if isinstance(raw, dict) else ():
            try:
                session = Session(csrf=str(row["csrf"]), expires=float(row["expires"]))
            except (KeyError, TypeError, ValueError):
                continue
            if session.expires > now:
                self.sessions[key] = session
                self.saved_expiry[key] = session.expires

    def save_sessions(self) -> None:
        """Persist sessions so restarts and deploys do not sign the operator out. Caller holds the lock."""
        now = time.time()
        self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
        data = {k: {"csrf": v.csrf, "expires": v.expires} for k, v in self.sessions.items()}
        try:
            temp = self.session_file.with_suffix(".tmp")
            temp.write_text(json.dumps(data, separators=(",", ":")))
            os.replace(temp, self.session_file)
            self.saved_expiry = {k: v.expires for k, v in self.sessions.items()}
        except OSError:
            pass  # Fall back to memory-only sessions if the state directory is unavailable.

    def prune(self) -> None:
        now = time.time()
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
            self.failures = {
                ip: [stamp for stamp in stamps if stamp > now - LOGIN_WINDOW]
                for ip, stamps in self.failures.items()
            }

    def authenticate(self, username: str, password: str) -> bool:
        expected_user = self.credentials["username"]
        salt = base64.b64decode(self.credentials["salt"])
        expected = base64.b64decode(self.credentials["hash"])
        rounds = int(self.credentials["iterations"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
        return hmac.compare_digest(username, expected_user) and hmac.compare_digest(actual, expected)

    def helper(self, payload: dict, timeout: float = 35.0) -> dict:
        raw = json.dumps(payload, separators=(",", ":")).encode() + b"\n"
        if len(raw) > MAX_BODY:
            raise ValueError("helper request too large")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(self.config["helper_socket"])
            client.sendall(raw)
            chunks = bytearray()
            while len(chunks) <= 256 * 1024:
                part = client.recv(65536)
                if not part:
                    break
                chunks.extend(part)
                if b"\n" in part:
                    break
        response = json.loads(bytes(chunks).split(b"\n", 1)[0])
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "Control action failed"))
        return response

    def media_path(self, media_id: str) -> Path:
        relative = Path(decode_id(media_id))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid recording identifier")
        candidate = self.recordings_root.joinpath(relative)
        if candidate.is_symlink() or not candidate.is_file():
            raise FileNotFoundError("Recording not found")
        resolved = candidate.resolve()
        if self.recordings_root not in resolved.parents or resolved.suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError("Invalid recording path")
        return resolved

    def recordings(self, limit: int = 250) -> dict:
        # Keep only the newest `limit` entries in memory; large archives stay cheap to list.
        newest: list[tuple[float, str, int]] = []
        total = 0
        total_bytes = 0
        if self.recordings_root.is_dir() and not self.recordings_root.is_symlink():
            for base, dirs, files in os.walk(self.recordings_root, followlinks=False):
                dirs[:] = [name for name in dirs if not Path(base, name).is_symlink()]
                for name in files:
                    path = Path(base, name)
                    if path.suffix.lower() not in MEDIA_EXTENSIONS or path.is_symlink():
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    total += 1
                    total_bytes += stat.st_size
                    entry = (stat.st_mtime, str(path), stat.st_size)
                    if len(newest) < limit:
                        heapq.heappush(newest, entry)
                    else:
                        heapq.heappushpop(newest, entry)
        rows = []
        for mtime, raw, size in sorted(newest, reverse=True):
            path = Path(raw)
            relative = path.relative_to(self.recordings_root).as_posix()
            rows.append({
                "id": b64_id(relative),
                "name": path.name,
                "relative": relative,
                "bytes": size,
                "modified": int(mtime),
                "kind": "image" if path.suffix.lower() in {".jpg", ".jpeg"} else "video",
            })
        return {"items": rows, "total": total, "bytes": total_bytes, "limited": total > limit}


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "CCTV-Control"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def json_response(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error_json(self, message: str, status: int) -> None:
        self.json_response({"ok": False, "error": message}, status)

    def body_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid content length") from exc
        if length < 0 or length > MAX_BODY:
            raise ValueError("Request body too large")
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc

    def session(self) -> tuple[str, Session] | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("cctv_session")
        if not morsel:
            return None
        token = morsel.value
        key = token_key(token)
        with self.app.lock:
            session = self.app.sessions.get(key)
            if not session or session.expires <= time.time():
                if self.app.sessions.pop(key, None):
                    self.app.save_sessions()
                return None
            session.expires = time.time() + SESSION_TTL
            # Sliding expiry: only rewrite the file when it has drifted, to avoid a disk write per request.
            if session.expires - self.app.saved_expiry.get(key, 0) > SESSION_SAVE_SLACK:
                self.app.save_sessions()
        return token, session

    def require_session(self, csrf: bool = False) -> tuple[str, Session] | None:
        current = self.session()
        if not current:
            self.error_json("Authentication required", HTTPStatus.UNAUTHORIZED)
            return None
        if csrf and not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), current[1].csrf):
            self.error_json("Security token expired; refresh and try again", HTTPStatus.FORBIDDEN)
            return None
        return current

    def serve_static(self, name: str, content_type: str) -> None:
        path = self.app.web_root / name
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.serve_static("index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self.serve_static("styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self.serve_static("app.js", "text/javascript; charset=utf-8")
        elif path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
        elif path == "/api/session":
            current = self.session()
            body = json.dumps({"ok": True, "authenticated": bool(current), "csrf": current[1].csrf if current else None}).encode()
            self.send_response(HTTPStatus.OK)
            if current:
                self.send_header("Set-Cookie", session_cookie(current[0]))  # renew the 30-day cookie on each visit
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            if not self.require_session():
                return
            try:
                self.json_response(self.app.helper({"action": "status"}))
            except Exception as exc:
                self.error_json(str(exc), HTTPStatus.BAD_GATEWAY)
        elif path == "/api/recordings":
            if not self.require_session():
                return
            self.json_response({"ok": True, **self.app.recordings()})
        elif path == "/api/quarantine":
            if not self.require_session():
                return
            try:
                self.json_response(self.app.helper({"action": "quarantine-list"}))
            except Exception as exc:
                self.error_json(str(exc), HTTPStatus.BAD_GATEWAY)
        elif path == "/api/logs":
            if not self.require_session():
                return
            try:
                self.json_response(self.app.helper({"action": "logs"}))
            except Exception as exc:
                self.error_json(str(exc), HTTPStatus.BAD_GATEWAY)
        elif path.startswith("/media/"):
            if not self.require_session():
                return
            try:
                self.serve_media(unquote(path.removeprefix("/media/")))
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND)
            except (ValueError, OSError):
                self.send_error(HTTPStatus.BAD_REQUEST)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def serve_media(self, media_id: str) -> None:
        path = self.app.media_path(media_id)
        size = path.stat().st_size
        start, end = 0, max(size - 1, 0)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            if not range_header.startswith("bytes=") or "," in range_header:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            first, _, last = range_header[6:].partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else end
                else:
                    length = int(last)
                    start = max(size - length, 0)
            except ValueError:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            if start < 0 or start >= size or end < start:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(128 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.body_json()
        except ValueError as exc:
            self.error_json(str(exc), HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/login":
            self.login(payload)
            return
        current = self.require_session(csrf=True)
        if not current:
            return
        if path == "/api/logout":
            with self.app.lock:
                self.app.sessions.pop(token_key(current[0]), None)
                self.app.save_sessions()
            self.send_response(HTTPStatus.OK)
            self.send_header("Set-Cookie", session_cookie("", 0))
            body = b'{"ok":true}'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            if path == "/api/action":
                action = payload.get("action", "")
                allowed = {"start", "stop", "restart", "retention", "poweroff"}
                if action not in allowed:
                    raise ValueError("Unknown action")
                if action == "poweroff" and payload.get("confirmation") != "POWER OFF":
                    raise ValueError("Confirmation phrase does not match")
                result = self.app.helper({"action": action})
            elif path == "/api/recordings/quarantine":
                media_path = self.app.media_path(str(payload.get("id", "")))
                relative = media_path.relative_to(self.app.recordings_root).as_posix()
                result = self.app.helper({"action": "quarantine", "path": relative})
            elif path == "/api/recordings/quarantine-all":
                if payload.get("confirmation") != "QUARANTINE ALL RECORDINGS":
                    raise ValueError("Confirmation phrase does not match")
                result = self.app.helper({"action": "quarantine-all"}, timeout=90)
            elif path == "/api/quarantine/restore":
                result = self.app.helper({"action": "restore", "id": str(payload.get("id", ""))})
            elif path == "/api/quarantine/restore-all":
                result = self.app.helper({"action": "restore-all"}, timeout=90)
            else:
                self.error_json("Not found", HTTPStatus.NOT_FOUND)
                return
            self.json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            self.error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.error_json(str(exc), HTTPStatus.BAD_GATEWAY)

    def login(self, payload: dict) -> None:
        ip = self.client_address[0]
        self.app.prune()
        with self.app.lock:
            attempts = self.app.failures.get(ip, [])
            if len(attempts) >= LOGIN_LIMIT:
                self.error_json("Too many attempts; wait 15 minutes", HTTPStatus.TOO_MANY_REQUESTS)
                return
        username = str(payload.get("username", ""))[:128]
        password = str(payload.get("password", ""))[:512]
        if not self.app.authenticate(username, password):
            with self.app.lock:
                self.app.failures.setdefault(ip, []).append(time.time())
            time.sleep(0.5)
            self.error_json("Incorrect username or password", HTTPStatus.UNAUTHORIZED)
            return
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        with self.app.lock:
            self.app.failures.pop(ip, None)
            self.app.sessions[token_key(token)] = Session(csrf=csrf, expires=time.time() + SESSION_TTL)
            self.app.save_sessions()
        body = json.dumps({"ok": True, "csrf": csrf}).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Set-Cookie", session_cookie(token))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    app = App(args.config)
    server = ControlServer((app.config["listen_host"], int(app.config["listen_port"])), ControlHandler)
    server.app = app  # type: ignore[attr-defined]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(app.config["cert_file"], app.config["key_file"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"CCTV Control listening on https://{app.config['listen_host']}:{app.config['listen_port']}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
