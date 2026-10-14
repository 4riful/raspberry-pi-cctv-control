#!/usr/bin/python3
"""Root broker exposing only fixed CCTV operations over a local Unix socket."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("CCTV_CONTROL_CONFIG", "/etc/cctv-control/config.json"))
try:
    CONFIG = json.loads(CONFIG_PATH.read_text())
except (OSError, ValueError):
    CONFIG = {}

RECORDINGS = Path(CONFIG.get("recordings_root", "/var/lib/motion"))
# Quarantine lives inside the recordings tree so moves are same-mount renames: the helper's
# systemd sandbox gives each ReadWritePaths entry its own bind mount, and rename() across
# mounts fails with EXDEV even on the same disk. Hidden top-level dirs are never listed.
QUARANTINE = Path(CONFIG.get("quarantine_root", str(RECORDINGS / ".cctv-quarantine")))
SOCKET_PATH = Path(CONFIG.get("helper_socket", "/run/cctv-control/control.sock"))
LOCK_PATH = Path("/run/cctv-control/mutate.lock")
CAMERA = Path(CONFIG.get("camera_device", "/dev/video0"))
MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".jpg", ".jpeg"}
MAX_REQUEST = 16 * 1024


def run(command: list[str], timeout: int = 20, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=check)


def systemctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return run(["/usr/bin/systemctl", *args], check=check)


def log(message: str, priority: str = "notice") -> None:
    run(["/usr/bin/logger", "-p", f"authpriv.{priority}", "-t", "cctv-control", message[:800]])


def safe_relative(value: str, root: Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Invalid path")
    candidate = root.joinpath(relative)
    if candidate.is_symlink():
        raise ValueError("Symbolic links are not allowed")
    resolved_parent = candidate.parent.resolve()
    if root.resolve() != resolved_parent and root.resolve() not in resolved_parent.parents:
        raise ValueError("Path escapes managed storage")
    return candidate


def recording_files() -> list[Path]:
    files = []
    if not RECORDINGS.is_dir() or RECORDINGS.is_symlink():
        return files
    for base, dirs, names in os.walk(RECORDINGS, followlinks=False):
        dirs[:] = [name for name in dirs if not name.startswith(".") and not Path(base, name).is_symlink()]
        for name in names:
            path = Path(base, name)
            if path.suffix.lower() in MEDIA_EXTENSIONS and not path.is_symlink() and path.is_file():
                files.append(path)
    return files


def is_open(path: Path) -> bool:
    target = str(path.resolve())
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        fd_dir = process / "fd"
        try:
            for descriptor in fd_dir.iterdir():
                try:
                    if os.path.realpath(descriptor) == target:
                        return True
                except OSError:
                    continue
        except (OSError, PermissionError):
            continue
    return False


def new_batch() -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    batch = QUARANTINE / f"{stamp}-{os.urandom(4).hex()}"
    batch.mkdir(parents=True, mode=0o750)
    return batch


def move_to_batch(path: Path, batch: Path) -> str:
    relative = path.relative_to(RECORDINGS)
    destination = batch / relative
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-duplicate-{int(time.time())}{destination.suffix}")
    os.replace(path, destination)
    return destination.relative_to(QUARANTINE).as_posix()


def remove_empty_recording_dirs() -> None:
    for base, dirs, _ in os.walk(RECORDINGS, topdown=False, followlinks=False):
        if any(part.startswith(".") for part in Path(base).relative_to(RECORDINGS).parts):
            continue
        for name in dirs:
            path = Path(base, name)
            if name.startswith("."):
                continue
            try:
                if not path.is_symlink():
                    path.rmdir()
            except OSError:
                pass


def quarantine_one(relative: str) -> dict:
    path = safe_relative(relative, RECORDINGS)
    if any(part.startswith(".") for part in path.relative_to(RECORDINGS).parts):
        raise ValueError("Recording not found")
    if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("Recording not found")
    if is_open(path) or time.time() - path.stat().st_mtime < 180:
        raise ValueError("This clip is still being recorded; try again when the event ends")
    batch = new_batch()
    item_id = move_to_batch(path, batch)
    remove_empty_recording_dirs()
    log(f"quarantined recording {relative}")
    return {"ok": True, "message": "Recording moved to 24-hour quarantine", "id": item_id}


def quarantine_all() -> dict:
    was_active = systemctl("is-active", "--quiet", "motioneye.service").returncode == 0
    if was_active:
        systemctl("stop", "motioneye.service", check=True)
    moved = []
    try:
        files = recording_files()
        if files:
            batch = new_batch()
            for path in files:
                moved.append(move_to_batch(path, batch))
        remove_empty_recording_dirs()
    finally:
        if was_active:
            systemctl("start", "motioneye.service", check=True)
    log(f"quarantined all recordings count={len(moved)}", "warning")
    return {"ok": True, "message": f"{len(moved)} recordings moved to 24-hour quarantine", "count": len(moved)}


def quarantine_items() -> list[dict]:
    rows = []
    if not QUARANTINE.is_dir() or QUARANTINE.is_symlink():
        return rows
    for batch in QUARANTINE.iterdir():
        if not batch.is_dir() or batch.is_symlink():
            continue
        for base, dirs, names in os.walk(batch, followlinks=False):
            dirs[:] = [name for name in dirs if not Path(base, name).is_symlink()]
            for name in names:
                path = Path(base, name)
                if path.suffix.lower() not in MEDIA_EXTENSIONS or path.is_symlink():
                    continue
                stat = path.stat()
                rows.append({
                    "id": path.relative_to(QUARANTINE).as_posix(),
                    "name": path.name,
                    "bytes": stat.st_size,
                    "quarantined": int(batch.stat().st_mtime),
                    "expires": int(batch.stat().st_mtime + 86400),
                })
    rows.sort(key=lambda row: row["quarantined"], reverse=True)
    return rows


def restore_one(item_id: str) -> dict:
    source = safe_relative(item_id, QUARANTINE)
    if not source.is_file() or source.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError("Quarantined recording not found")
    relative_parts = source.relative_to(QUARANTINE).parts
    if len(relative_parts) < 2:
        raise ValueError("Invalid quarantine entry")
    destination = safe_relative(Path(*relative_parts[1:]).as_posix(), RECORDINGS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-restored-{int(time.time())}{destination.suffix}")
    os.replace(source, destination)
    log(f"restored recording {item_id}")
    return {"ok": True, "message": "Recording restored"}


def restore_all() -> dict:
    items = [row["id"] for row in quarantine_items()]
    restored = 0
    for item_id in items:
        restore_one(item_id)
        restored += 1
    for base, dirs, _ in os.walk(QUARANTINE, topdown=False, followlinks=False):
        for name in dirs:
            try:
                (Path(base) / name).rmdir()
            except OSError:
                pass
    log(f"restored all quarantined recordings count={restored}")
    return {"ok": True, "message": f"{restored} recordings restored", "count": restored}


def purge_expired() -> dict:
    now = time.time()
    removed_files = 0
    if QUARANTINE.is_dir() and not QUARANTINE.is_symlink():
        for batch in QUARANTINE.iterdir():
            if not batch.is_dir() or batch.is_symlink():
                continue
            if now - batch.stat().st_mtime >= 86400:
                removed_files += sum(1 for p in batch.rglob("*") if p.is_file() and not p.is_symlink())
                shutil.rmtree(batch)
    if removed_files:
        log(f"permanently purged expired quarantine files count={removed_files}", "warning")
    return {"ok": True, "count": removed_files}


def read_first(command: list[str], fallback: str = "unknown") -> str:
    try:
        result = run(command, timeout=8)
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else fallback
    except Exception:
        return fallback


def temperature() -> str:
    try:
        milli = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
        return f"{milli / 1000:.1f} °C"
    except (OSError, ValueError):
        return read_first(["/usr/bin/vcgencmd", "measure_temp"])


def status() -> dict:
    # One systemctl call per question instead of one per property keeps polling cheap on the Pi.
    props = {}
    for line in run([
        "/usr/bin/systemctl", "show", "motioneye.service",
        "--property=ActiveState,UnitFileState,MainPID,NRestarts,ActiveEnterTimestamp",
    ], timeout=8).stdout.splitlines():
        key, _, value = line.partition("=")
        props[key] = value.strip()
    timer_names = ("cctv-health.timer", "cctv-retention.timer", "cctv-control-cleanup.timer")
    timer_states = systemctl("is-active", *timer_names).stdout.split()
    timers = {name: timer_states[i] if i < len(timer_states) else "unknown" for i, name in enumerate(timer_names)}
    dashboard = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/", timeout=3) as response:
            dashboard = response.status == 200
    except Exception:
        pass
    usage = shutil.disk_usage(RECORDINGS)
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                memory[key] = int(value.strip().split()[0]) * 1024
    except OSError:
        pass
    uptime = 0
    try:
        uptime = int(float(Path("/proc/uptime").read_text().split()[0]))
    except OSError:
        pass
    throttle = read_first(["/usr/bin/vcgencmd", "get_throttled"])
    quarantine = quarantine_items()
    return {
        "ok": True,
        "service": {
            "active": props.get("ActiveState", "unknown"),
            "enabled": props.get("UnitFileState", "unknown"),
            "main_pid": props.get("MainPID", "0"),
            "restarts": props.get("NRestarts", "0"),
            "since": props.get("ActiveEnterTimestamp", ""),
        },
        "camera": CAMERA.exists(),
        "dashboard": dashboard,
        "power": throttle,
        "temperature": temperature(),
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free},
        "memory": memory,
        "uptime": uptime,
        "timers": timers,
        "quarantine": {"count": len(quarantine), "bytes": sum(row["bytes"] for row in quarantine)},
    }


def logs() -> dict:
    result = run([
        "/usr/bin/journalctl", "--no-pager", "-n", "80", "-o", "short-iso",
        "-u", "motioneye.service", "-u", "cctv-health.service",
        "-u", "cctv-retention.service", "-u", "cctv-control.service",
        "-u", "cctv-control-helper.service",
    ], timeout=15)
    lines = result.stdout.splitlines()[-80:]
    return {"ok": True, "lines": lines}


def dispatch(request: dict) -> dict:
    action = request.get("action")
    if action == "status":
        return status()
    if action == "logs":
        return logs()
    if action == "poweroff":
        log("requested Raspberry Pi power off")
        # Reply first; the shutdown starts a moment later so the operator sees confirmation.
        threading.Timer(2.0, lambda: systemctl("poweroff", "--no-block")).start()
        return {"ok": True, "message": "Raspberry Pi is powering off; unplug and replug power to start it again"}
    if action == "quarantine-list":
        items = quarantine_items()
        return {"ok": True, "items": items, "count": len(items)}
    if action in {"quarantine", "quarantine-all", "restore", "restore-all", "purge-expired", "start", "stop", "restart", "retention"}:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOCK_PATH.open("w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            if action == "quarantine":
                return quarantine_one(str(request.get("path", "")))
            if action == "quarantine-all":
                return quarantine_all()
            if action == "restore":
                return restore_one(str(request.get("id", "")))
            if action == "restore-all":
                return restore_all()
            if action == "purge-expired":
                return purge_expired()
            if action in {"start", "stop", "restart"}:
                systemctl(action, "motioneye.service", check=True)
                log(f"requested motioneye {action}")
                return {"ok": True, "message": f"CCTV {action} command completed"}
            run(["/usr/local/sbin/cctv-retention"], timeout=90, check=True)
            log("requested retention cleanup")
            return {"ok": True, "message": "Retention cleanup completed"}
    raise ValueError("Unknown action")


def handle(connection: socket.socket) -> None:
    data = bytearray()
    while len(data) <= MAX_REQUEST:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    try:
        if len(data) > MAX_REQUEST:
            raise ValueError("Request too large")
        request = json.loads(bytes(data).split(b"\n", 1)[0])
        response = dispatch(request)
    except Exception as exc:
        response = {"ok": False, "error": str(exc)}
        log(f"action failed: {exc}", "warning")
    connection.sendall(json.dumps(response, separators=(",", ":")).encode() + b"\n")


def serve() -> None:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOCKET_PATH.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(SOCKET_PATH))
        os.chmod(SOCKET_PATH, 0o660)
        server.listen(8)
        while True:
            connection, _ = server.accept()
            with connection:
                handle(connection)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--purge-expired", action="store_true")
    args = parser.parse_args()
    if args.purge_expired:
        print(json.dumps(dispatch({"action": "purge-expired"})))
    else:
        serve()


if __name__ == "__main__":
    main()
