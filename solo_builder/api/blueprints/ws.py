"""WebSocket support — real-time push for dashboard clients.

The broadcaster thread watches state/step.txt every 0.5 s and pushes
{"type": "change", "step": N} to all connected clients when the step
counter changes.  Clients fall back to polling on disconnect.

The actual /ws route is registered in app.py via:
    from flask_sock import Sock
    sock = Sock(app)
    sock.route("/ws")(handle_ws)
"""
import json
import threading
import time
from pathlib import Path

# Thread-safe set of active WebSocket connections.
_clients: set = set()
_clients_lock = threading.Lock()

# Resolved lazily so tests don't need a full app context.
_step_path: Path | None = None


def _get_step_path() -> Path:
    global _step_path
    if _step_path is None:
        from .. import app as _app_module
        _step_path = _app_module.HEARTBEAT_PATH
    return _step_path


def _read_step() -> int:
    try:
        return int(_get_step_path().read_text().strip().split(",")[0])
    except Exception:
        return -1


def _broadcast(payload: str) -> None:
    dead = set()
    with _clients_lock:
        snapshot = set(_clients)
    for client in snapshot:
        try:
            client.send(payload)
        except Exception:
            dead.add(client)
    if dead:
        with _clients_lock:
            _clients.difference_update(dead)


def _broadcaster() -> None:
    """Background daemon: pushes step changes to all connected clients."""
    last_step = -1
    while True:
        time.sleep(0.5)
        step = _read_step()
        if step != last_step and step >= 0:
            last_step = step
            with _clients_lock:
                if not _clients:
                    continue
            _broadcast(json.dumps({"type": "change", "step": step}))


_broadcaster_thread = threading.Thread(
    target=_broadcaster, daemon=True, name="ws-broadcaster"
)
_broadcaster_thread.start()


def handle_ws(ws) -> None:
    """Handler for an upgraded WebSocket connection (called from app.py)."""
    with _clients_lock:
        _clients.add(ws)
    try:
        step = _read_step()
        if step >= 0:
            ws.send(json.dumps({"type": "hello", "step": step}))
        while True:
            ws.receive(timeout=30)
    except Exception:
        pass
    finally:
        with _clients_lock:
            _clients.discard(ws)


def client_count() -> int:
    """Return number of currently connected WebSocket clients."""
    with _clients_lock:
        return len(_clients)
