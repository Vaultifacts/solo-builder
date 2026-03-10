"""Tests for tools/state_backup.py (TASK-347, ME-010 to ME-015)."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "state_backup", _TOOLS_DIR / "state_backup.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

backup        = _mod.backup
restore       = _mod.restore
list_backups  = _mod.list_backups
prune         = _mod.prune
read_manifest = _mod.read_manifest
_archive_name = _mod._archive_name
_BACKUP_FILES = _mod._BACKUP_FILES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_repo(tmp_path: Path) -> Path:
    """Create a fake repo tree with some state files."""
    # Create paths matching _BACKUP_FILES pattern
    state_dir  = tmp_path / "solo_builder" / "state"
    config_dir = tmp_path / "solo_builder" / "config"
    state_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)

    (state_dir / "solo_builder_state.json").write_text('{"dag": {}, "step": 0}')
    (state_dir / "step.txt").write_text("0,0,0,0,0")
    (tmp_path / "solo_builder" / "metrics.jsonl").write_text("")
    (config_dir / "settings.json").write_text('{"STALL_THRESHOLD": 5}')
    return tmp_path


# ---------------------------------------------------------------------------
# _archive_name
# ---------------------------------------------------------------------------

class TestArchiveName(unittest.TestCase):

    def test_starts_with_prefix(self):
        name = _archive_name()
        self.assertTrue(name.startswith("sb_backup_"))

    def test_ends_with_zip(self):
        self.assertTrue(_archive_name().endswith(".zip"))

    def test_label_included(self):
        name = _archive_name("mytest")
        self.assertIn("mytest", name)

    def test_no_label_no_underscore_suffix(self):
        name = _archive_name(None)
        # Should not end with _ before .zip
        self.assertFalse(name.endswith("_.zip"))


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

class TestBackup(unittest.TestCase):

    def test_creates_zip_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, quiet=True)
            self.assertTrue(archive.exists())
            self.assertTrue(archive.suffix == ".zip")

    def test_archive_contains_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, quiet=True)
            with zipfile.ZipFile(archive) as zf:
                self.assertIn("manifest.json", zf.namelist())

    def test_manifest_has_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, quiet=True)
            manifest = read_manifest(archive)
            for key in ("created", "included", "skipped", "label"):
                self.assertIn(key, manifest)

    def test_included_files_in_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, quiet=True)
            with zipfile.ZipFile(archive) as zf:
                names = zf.namelist()
            self.assertIn("solo_builder/state/solo_builder_state.json", names)
            self.assertIn("solo_builder/config/settings.json", names)

    def test_label_in_archive_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, label="mytest", quiet=True)
            self.assertIn("mytest", archive.name)

    def test_backup_dir_created_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = Path(tmp) / "new_backups" / "sub"
            with patch.object(_mod, "REPO_ROOT", repo):
                backup(bdir, quiet=True)
            self.assertTrue(bdir.exists())

    def test_missing_files_recorded_in_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Empty repo — no files to include
            repo = Path(tmp) / "empty_repo"
            repo.mkdir()
            bdir = Path(tmp) / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                archive = backup(bdir, quiet=True)
            manifest = read_manifest(archive)
            self.assertGreater(len(manifest["skipped"]), 0)


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------

class TestRestore(unittest.TestCase):

    def _create_archive(self, tmp: Path) -> tuple[Path, Path]:
        """Create backup archive and return (repo, archive_path)."""
        repo = _make_fake_repo(tmp / "repo")
        bdir = tmp / "backups"
        with patch.object(_mod, "REPO_ROOT", repo):
            archive = backup(bdir, quiet=True)
        return repo, archive

    def test_restores_files(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo, archive = self._create_archive(tmp)
            # Delete state file
            state_file = repo / "solo_builder" / "state" / "solo_builder_state.json"
            state_file.unlink()
            with patch.object(_mod, "REPO_ROOT", repo):
                restored = restore(archive, quiet=True)
            self.assertIn("solo_builder/state/solo_builder_state.json", restored)
            self.assertTrue(state_file.exists())

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo, archive = self._create_archive(tmp)
            state_file = repo / "solo_builder" / "state" / "solo_builder_state.json"
            state_file.unlink()
            with patch.object(_mod, "REPO_ROOT", repo):
                restore(archive, dry_run=True, quiet=True)
            self.assertFalse(state_file.exists())

    def test_restore_returns_list_of_paths(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo, archive = self._create_archive(tmp)
            with patch.object(_mod, "REPO_ROOT", repo):
                result = restore(archive, quiet=True)
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)

    def test_restore_raises_on_missing_archive(self):
        with self.assertRaises(FileNotFoundError):
            restore(Path("/nonexistent/archive.zip"), quiet=True)


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------

class TestListBackups(unittest.TestCase):

    def test_returns_empty_when_dir_missing(self):
        result = list_backups(Path("/nonexistent/backups"), quiet=True)
        self.assertEqual(result, [])

    def test_returns_archives_sorted(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _make_fake_repo(tmp / "repo")
            bdir = tmp / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                a1 = backup(bdir, label="first",  quiet=True)
                a2 = backup(bdir, label="second", quiet=True)
            archives = list_backups(bdir, quiet=True)
            self.assertEqual(len(archives), 2)
            self.assertIn(a1, archives)
            self.assertIn(a2, archives)
            self.assertEqual(archives, sorted(archives))


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------

class TestPrune(unittest.TestCase):

    def test_prune_keeps_most_recent(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _make_fake_repo(tmp / "repo")
            bdir = tmp / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                for _ in range(5):
                    backup(bdir, quiet=True)
            prune(bdir, keep=3, quiet=True)
            remaining = list_backups(bdir, quiet=True)
            self.assertEqual(len(remaining), 3)

    def test_prune_returns_deleted_list(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _make_fake_repo(tmp / "repo")
            bdir = tmp / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                for _ in range(4):
                    backup(bdir, quiet=True)
            deleted = prune(bdir, keep=2, quiet=True)
            self.assertEqual(len(deleted), 2)

    def test_prune_nothing_when_under_limit(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = _make_fake_repo(tmp / "repo")
            bdir = tmp / "backups"
            with patch.object(_mod, "REPO_ROOT", repo):
                backup(bdir, quiet=True)
            deleted = prune(bdir, keep=10, quiet=True)
            self.assertEqual(deleted, [])


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_backup_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_fake_repo(Path(tmp) / "repo")
            bdir = str(Path(tmp) / "backups")
            with patch.object(_mod, "REPO_ROOT", repo):
                rc = _mod.main(["backup", "--backup-dir", bdir, "--quiet"])
        self.assertEqual(rc, 0)

    def test_main_list_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backups")
            rc = _mod.main(["list", "--backup-dir", bdir, "--quiet"])
        self.assertEqual(rc, 0)

    def test_main_no_cmd_returns_2(self):
        rc = _mod.main([])
        self.assertEqual(rc, 2)

    def test_main_restore_missing_archive_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backups")
            rc = _mod.main(["restore", "no_such.zip", "--backup-dir", bdir, "--quiet"])
        self.assertEqual(rc, 1)

    def test_main_prune_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backups")
            rc = _mod.main(["prune", "--backup-dir", bdir, "--quiet"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
