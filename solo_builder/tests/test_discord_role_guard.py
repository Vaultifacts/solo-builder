"""Tests for solo_builder/utils/discord_role_guard.py (TASK-346, SE-030)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from solo_builder.utils.discord_role_guard import (
    RoleConfig,
    RoleGuardResult,
    _parse_csv_set,
    check_admin_role,
    load_role_config,
)


# ---------------------------------------------------------------------------
# Helpers — mock Discord objects
# ---------------------------------------------------------------------------

def _role(role_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=role_id)


def _user(user_id: int, role_ids: list[int] | None = None) -> SimpleNamespace:
    roles = [_role(r) for r in (role_ids or [])]
    return SimpleNamespace(id=user_id, roles=roles)


def _guild(owner_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(owner_id=owner_id)


def _interaction(
    user_id: int = 100,
    role_ids: list[int] | None = None,
    guild_owner_id: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        user=_user(user_id, role_ids),
        guild=_guild(guild_owner_id),
    )


def _config(admin_role_id: int | None = 999,
            destructive_commands: frozenset[str] | None = None) -> RoleConfig:
    return RoleConfig(
        admin_role_id=admin_role_id,
        destructive_commands=destructive_commands or frozenset({"reset", "heal"}),
    )


# ---------------------------------------------------------------------------
# _parse_csv_set
# ---------------------------------------------------------------------------

class TestParseCsvSet(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(_parse_csv_set("a,b,c"), frozenset({"a", "b", "c"}))

    def test_strips_whitespace(self):
        self.assertEqual(_parse_csv_set(" a , b "), frozenset({"a", "b"}))

    def test_empty_string(self):
        self.assertEqual(_parse_csv_set(""), frozenset())


# ---------------------------------------------------------------------------
# RoleConfig
# ---------------------------------------------------------------------------

class TestRoleConfig(unittest.TestCase):

    def test_validate_no_warnings(self):
        cfg = _config(admin_role_id=12345)
        self.assertEqual(cfg.validate(), [])

    def test_validate_warns_on_non_positive_role_id(self):
        cfg = _config(admin_role_id=0)
        warnings = cfg.validate()
        self.assertTrue(any("positive" in w for w in warnings))

    def test_to_dict(self):
        cfg = _config(admin_role_id=42, destructive_commands=frozenset({"reset"}))
        d = cfg.to_dict()
        self.assertEqual(d["admin_role_id"], 42)
        self.assertEqual(d["destructive_commands"], ["reset"])

    def test_immutable(self):
        cfg = _config()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.admin_role_id = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RoleGuardResult
# ---------------------------------------------------------------------------

class TestRoleGuardResult(unittest.TestCase):

    def test_to_dict(self):
        r = RoleGuardResult(allowed=True, reason="open_mode", deny_message="")
        d = r.to_dict()
        self.assertIn("allowed", d)
        self.assertIn("reason", d)
        self.assertIn("deny_message", d)


# ---------------------------------------------------------------------------
# load_role_config
# ---------------------------------------------------------------------------

class TestLoadRoleConfig(unittest.TestCase):

    def test_defaults_when_file_missing(self):
        cfg = load_role_config(settings_path="/nonexistent/settings.json")
        self.assertIsNone(cfg.admin_role_id)

    def test_admin_role_id_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"DISCORD_ADMIN_ROLE_ID": "12345"}), encoding="utf-8")
            cfg = load_role_config(settings_path=p)
        self.assertEqual(cfg.admin_role_id, 12345)

    def test_empty_role_id_means_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"DISCORD_ADMIN_ROLE_ID": ""}), encoding="utf-8")
            cfg = load_role_config(settings_path=p)
        self.assertIsNone(cfg.admin_role_id)

    def test_destructive_commands_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"DISCORD_DESTRUCTIVE_COMMANDS": "reset,heal"}), encoding="utf-8")
            cfg = load_role_config(settings_path=p)
        self.assertEqual(cfg.destructive_commands, frozenset({"reset", "heal"}))

    def test_default_destructive_commands_non_empty(self):
        cfg = load_role_config(settings_path="/nonexistent/settings.json")
        self.assertGreater(len(cfg.destructive_commands), 0)
        self.assertIn("reset", cfg.destructive_commands)

    def test_invalid_role_id_treated_as_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"DISCORD_ADMIN_ROLE_ID": "not-a-number"}), encoding="utf-8")
            cfg = load_role_config(settings_path=p)
        self.assertIsNone(cfg.admin_role_id)


# ---------------------------------------------------------------------------
# check_admin_role
# ---------------------------------------------------------------------------

class TestCheckAdminRole(unittest.TestCase):

    def test_open_mode_always_allowed(self):
        cfg = _config(admin_role_id=None)
        ix = _interaction()
        result = check_admin_role(ix, cfg)
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "open_mode")

    def test_non_destructive_command_always_allowed(self):
        cfg = _config(admin_role_id=999, destructive_commands=frozenset({"reset"}))
        ix = _interaction(role_ids=[])  # no admin role
        result = check_admin_role(ix, cfg, command_name="status")
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "non_destructive_command")

    def test_user_with_admin_role_allowed(self):
        cfg = _config(admin_role_id=999)
        ix = _interaction(role_ids=[999])
        result = check_admin_role(ix, cfg, command_name="reset")
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "has_admin_role")

    def test_user_without_admin_role_denied(self):
        cfg = _config(admin_role_id=999)
        ix = _interaction(role_ids=[111, 222])  # does not include 999
        result = check_admin_role(ix, cfg, command_name="reset")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "missing_admin_role")
        self.assertIn("999", result.deny_message)

    def test_guild_owner_always_allowed(self):
        cfg = _config(admin_role_id=999)
        ix = _interaction(user_id=42, role_ids=[], guild_owner_id=42)
        result = check_admin_role(ix, cfg, command_name="reset")
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "guild_owner")

    def test_no_user_returns_denied(self):
        cfg = _config(admin_role_id=999)
        ix = SimpleNamespace(user=None, guild=_guild())
        result = check_admin_role(ix, cfg, command_name="reset")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "no_user")

    def test_command_name_none_checks_all(self):
        """If command_name is None, skip the name check and apply role guard."""
        cfg = _config(admin_role_id=999)
        ix = _interaction(role_ids=[])  # no admin role
        result = check_admin_role(ix, cfg, command_name=None)
        self.assertFalse(result.allowed)

    def test_deny_message_non_empty_when_denied(self):
        cfg = _config(admin_role_id=999)
        ix = _interaction(role_ids=[])
        result = check_admin_role(ix, cfg, command_name="reset")
        self.assertFalse(result.allowed)
        self.assertTrue(result.deny_message)

    def test_deny_message_empty_when_allowed(self):
        cfg = _config(admin_role_id=None)
        ix = _interaction()
        result = check_admin_role(ix, cfg)
        self.assertTrue(result.allowed)
        self.assertEqual(result.deny_message, "")

    def test_user_with_multiple_roles_including_admin(self):
        cfg = _config(admin_role_id=999)
        ix = _interaction(role_ids=[100, 200, 999, 300])
        result = check_admin_role(ix, cfg, command_name="heal")
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()
