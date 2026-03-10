"""Discord role-based access guard for destructive slash commands (TASK-346, SE-030).

Provides check_admin_role() and the RoleGuardResult namedtuple for use
in Discord bot slash command handlers.

When DISCORD_ADMIN_ROLE_ID is set in settings.json, only guild members
who hold that role (or are the guild owner) may execute destructive commands.
When DISCORD_ADMIN_ROLE_ID is empty/unset, all members are allowed (open
mode — no change to existing behaviour).

Usage in a slash command handler:
    result = check_admin_role(interaction, load_role_config())
    if not result.allowed:
        await interaction.response.send_message(result.deny_message, ephemeral=True)
        return
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.json"


@dataclass(frozen=True)
class RoleConfig:
    """Immutable role-guard configuration."""
    admin_role_id:        int | None          # None → open (all allowed)
    destructive_commands: frozenset[str]      # command names requiring the role

    def validate(self) -> list[str]:
        warnings: list[str] = []
        if self.admin_role_id is not None and self.admin_role_id <= 0:
            warnings.append(f"admin_role_id should be a positive Discord snowflake, got {self.admin_role_id}")
        return warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "admin_role_id":        self.admin_role_id,
            "destructive_commands": sorted(self.destructive_commands),
        }


@dataclass(frozen=True)
class RoleGuardResult:
    """Outcome of a role check."""
    allowed:      bool
    reason:       str
    deny_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed":      self.allowed,
            "reason":       self.reason,
            "deny_message": self.deny_message,
        }


def _parse_csv_set(value: str) -> frozenset[str]:
    return frozenset(t.strip() for t in value.split(",") if t.strip())


def load_role_config(settings_path: str | Path | None = None) -> RoleConfig:
    """Load RoleConfig from settings.json.

    Settings keys consumed:
    - DISCORD_ADMIN_ROLE_ID  — Discord role snowflake (int string); empty → open
    - DISCORD_DESTRUCTIVE_COMMANDS — comma-separated command names
    """
    if settings_path is None:
        settings_path = _SETTINGS_PATH
    settings_path = Path(settings_path)

    cfg: dict[str, Any] = {}
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    raw_role_id = str(cfg.get("DISCORD_ADMIN_ROLE_ID", "")).strip()
    admin_role_id: int | None = None
    if raw_role_id:
        try:
            admin_role_id = int(raw_role_id)
        except ValueError:
            admin_role_id = None

    raw_cmds = str(cfg.get(
        "DISCORD_DESTRUCTIVE_COMMANDS",
        "reset,heal,undo,add_task,add_branch,prioritize_branch,depends,undepends",
    ))
    destructive_commands = _parse_csv_set(raw_cmds)

    return RoleConfig(
        admin_role_id=admin_role_id,
        destructive_commands=destructive_commands,
    )


def check_admin_role(
    interaction: Any,
    config: RoleConfig,
    command_name: str | None = None,
) -> RoleGuardResult:
    """Check whether *interaction* passes the admin role guard.

    Parameters
    ----------
    interaction
        A Discord Interaction object (or any object with .user / .guild attributes).
        Accepts mock objects for testing.
    config
        RoleConfig loaded by load_role_config().
    command_name
        Optional command name; if provided and not in config.destructive_commands,
        the guard returns allowed=True immediately (non-destructive command).

    Returns
    -------
    RoleGuardResult with allowed=True when the check passes.
    """
    # If admin_role_id is not configured → open mode
    if config.admin_role_id is None:
        return RoleGuardResult(
            allowed=True,
            reason="open_mode",
            deny_message="",
        )

    # If command not in destructive list → no guard needed
    if command_name is not None and command_name not in config.destructive_commands:
        return RoleGuardResult(
            allowed=True,
            reason="non_destructive_command",
            deny_message="",
        )

    user   = getattr(interaction, "user", None)
    guild  = getattr(interaction, "guild", None)

    if user is None:
        return RoleGuardResult(
            allowed=False,
            reason="no_user",
            deny_message="❌ Could not identify the user for this interaction.",
        )

    # Guild owner always allowed
    if guild is not None:
        owner_id = getattr(guild, "owner_id", None)
        if owner_id is not None and getattr(user, "id", None) == owner_id:
            return RoleGuardResult(allowed=True, reason="guild_owner", deny_message="")

    # Check roles
    member_roles = getattr(user, "roles", [])
    role_ids = {getattr(r, "id", None) for r in member_roles}
    if config.admin_role_id in role_ids:
        return RoleGuardResult(allowed=True, reason="has_admin_role", deny_message="")

    return RoleGuardResult(
        allowed=False,
        reason="missing_admin_role",
        deny_message=(
            f"❌ This command requires the admin role (ID {config.admin_role_id}). "
            "Please ask a server admin to run this command."
        ),
    )
