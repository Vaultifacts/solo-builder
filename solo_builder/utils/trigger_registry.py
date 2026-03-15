"""
utils/trigger_registry.py
Centralized trigger file registry for IPC between CLI, API, and Discord bot.

Supports trigger types:
  - JSON: {"payload": ...}, consumed atomically with optional quarantine on malformed
  - Presence: file existence = signal, no payload
  - Text: arbitrary text content
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class TriggerDef:
    """Trigger definition: logical name, filesystem path, and format."""
    name: str
    filename: str
    format: str  # "json", "presence", "text"
    handler_key: Optional[str] = None  # Optional key for dispatch


class TriggerRegistry:
    """
    Centralized registry for trigger file definitions and consumption.

    Provides atomic read/write/delete operations and pre-registered defaults
    for all trigger types used by Solo Builder.
    """

    def __init__(self):
        """Initialize registry with no triggers; use register() to add them."""
        self._triggers: Dict[str, TriggerDef] = {}

    def register(self, name: str, filename: str, format_type: str,
                 handler_key: Optional[str] = None) -> None:
        """
        Register a trigger type.

        Args:
            name: Logical trigger name (e.g., "run", "verify")
            filename: Filename relative to state/ dir (e.g., "run_trigger")
            format_type: "json", "presence", or "text"
            handler_key: Optional dispatch key (defaults to name)

        Raises:
            ValueError: If format_type is not recognized
        """
        if format_type not in ("json", "presence", "text"):
            raise ValueError(f"Unknown format_type: {format_type}")
        hk = handler_key or name
        self._triggers[name] = TriggerDef(
            name=name,
            filename=filename,
            format=format_type,
            handler_key=hk,
        )

    def check_all(self, state_dir: str) -> Dict[str, Any]:
        """
        Check all registered triggers without consuming them.

        Returns dict: {trigger_name: parsed_data or True (for presence/text)}
        """
        fired = {}
        for name, defn in self._triggers.items():
            path = os.path.join(state_dir, defn.filename)
            if os.path.exists(path):
                if defn.format == "json":
                    try:
                        with open(path, encoding="utf-8") as f:
                            fired[name] = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        fired[name] = None
                else:  # presence or text
                    fired[name] = True
        return fired

    def consume(self, state_dir: str, name: str,
                quarantine: bool = True) -> Optional[Union[Dict, List, bool]]:
        """
        Read, parse, and atomically delete a trigger file.

        Args:
            state_dir: Path to state/ directory
            name: Logical trigger name
            quarantine: If True, rename malformed JSON to .bad instead of deleting

        Returns:
            - For JSON: parsed dict/list, or None if missing/malformed
            - For presence/text: True if file existed and was deleted, False otherwise
        """
        if name not in self._triggers:
            raise KeyError(f"Unknown trigger: {name}")

        defn = self._triggers[name]
        path = os.path.join(state_dir, defn.filename)

        if defn.format == "json":
            return self._consume_json(path, quarantine)
        else:  # presence or text
            return self._consume_flag(path)

    def write(self, state_dir: str, name: str,
              data: Optional[Union[Dict, List, str]] = None) -> None:
        """
        Write a trigger file.

        Args:
            state_dir: Path to state/ directory
            name: Logical trigger name
            data: Payload (dict/list for JSON, str for text, None for presence)

        Raises:
            KeyError: If trigger not registered
            ValueError: If format/data mismatch
        """
        if name not in self._triggers:
            raise KeyError(f"Unknown trigger: {name}")

        defn = self._triggers[name]
        path = os.path.join(state_dir, defn.filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if defn.format == "json":
            if data is None:
                data = {}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        elif defn.format == "text":
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(data) if data is not None else "")
        else:  # presence
            with open(path, "w", encoding="utf-8") as f:
                f.write("1")

    def exists(self, state_dir: str, name: str) -> bool:
        """Check if a trigger file exists without consuming it."""
        if name not in self._triggers:
            raise KeyError(f"Unknown trigger: {name}")
        path = os.path.join(state_dir, self._triggers[name].filename)
        return os.path.exists(path)

    def get_trigger_path(self, state_dir: str, name: str) -> str:
        """Get absolute path for a trigger by name."""
        if name not in self._triggers:
            raise KeyError(f"Unknown trigger: {name}")
        return os.path.join(state_dir, self._triggers[name].filename)

    def get_all_trigger_paths(self, state_dir: str) -> Dict[str, str]:
        """Get all trigger paths keyed by logical name."""
        return {
            name: os.path.join(state_dir, defn.filename)
            for name, defn in self._triggers.items()
        }

    def cleanup_stale(self, state_dir: str,
                      exclude: Optional[List[str]] = None) -> int:
        """
        Remove stale trigger files from a previous run.

        Args:
            state_dir: Path to state/ directory
            exclude: Logical trigger names to skip

        Returns: Number of files removed
        """
        os.makedirs(state_dir, exist_ok=True)
        skip = set(exclude or [])
        removed = 0
        for name, defn in self._triggers.items():
            if name in skip:
                continue
            path = os.path.join(state_dir, defn.filename)
            try:
                os.remove(path)
                removed += 1
            except FileNotFoundError:
                pass
        return removed

    # ── Static helpers (compatible with cloud branch) ─────────────────────────

    @staticmethod
    def _consume_json(path: str, quarantine: bool = True) \
            -> Optional[Union[Dict, List]]:
        """Read, parse, and atomically delete a JSON trigger file."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            data = json.loads(raw)
            os.remove(path)
            return data
        except (json.JSONDecodeError, ValueError):
            # Malformed JSON — quarantine or delete
            if quarantine:
                bad_path = path + ".bad"
                try:
                    os.replace(path, bad_path)
                except OSError:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return None
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    @staticmethod
    def _consume_flag(path: str) -> bool:
        """Check for and consume a presence-type trigger."""
        if not os.path.exists(path):
            return False
        try:
            os.remove(path)
        except OSError:
            pass
        return True


# ── Default singleton instance with pre-registered triggers ────────────────────

_DEFAULT_REGISTRY = None


def get_default_registry() -> TriggerRegistry:
    """
    Get the default TriggerRegistry with all standard triggers pre-registered.

    Returns the singleton instance, creating it on first call.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is not None:
        return _DEFAULT_REGISTRY

    reg = TriggerRegistry()

    # Presence triggers (flag-type, no JSON payload)
    reg.register("run", "run_trigger", "presence")
    reg.register("stop", "stop_trigger", "presence")
    reg.register("pause", "pause_trigger", "presence")
    reg.register("reset", "reset_trigger", "presence")
    reg.register("snapshot", "snapshot_trigger", "presence")
    reg.register("undo", "undo_trigger", "presence")

    # JSON triggers (structured payload)
    reg.register("verify", "verify_trigger.json", "json")
    reg.register("describe", "describe_trigger.json", "json")
    reg.register("tools", "tools_trigger.json", "json")
    reg.register("set", "set_trigger.json", "json")
    reg.register("rename", "rename_trigger.json", "json")
    reg.register("heal", "heal_trigger.json", "json")
    reg.register("add_task", "add_task_trigger.json", "json")
    reg.register("add_branch", "add_branch_trigger.json", "json")
    reg.register("prioritize_branch", "prioritize_branch_trigger.json", "json")
    reg.register("depends", "depends_trigger.json", "json")
    reg.register("undepends", "undepends_trigger.json", "json")

    _DEFAULT_REGISTRY = reg
    return reg
