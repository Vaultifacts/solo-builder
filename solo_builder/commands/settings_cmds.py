"""Settings/config commands for SoloBuilderCLI."""
from utils.helper_functions import BOLD, RESET, CYAN, DIM


class SettingsCommandsMixin:
    """Mixin: settings and config display commands."""

    def _cmd_config(self) -> None:
        """config — display all runtime settings in a formatted table."""
        rc = self._runtime_cfg
        settings: dict = {
            "STALL_THRESHOLD":     str(rc["STALL_THRESHOLD"]),
            "SNAPSHOT_INTERVAL":   str(rc["SNAPSHOT_INTERVAL"]),
            "VERBOSITY":           rc["VERBOSITY"],
            "VERIFY_PROB":         str(self.executor.verify_prob),
            "AUTO_STEP_DELAY":     str(rc["AUTO_STEP_DELAY"]),
            "AUTO_SAVE_INTERVAL":  str(rc["AUTO_SAVE_INTERVAL"]),
            "CLAUDE_ALLOWED_TOOLS": rc["CLAUDE_ALLOWED_TOOLS"] or "(none)",
            "ANTHROPIC_MAX_TOKENS": str(self.executor.anthropic.max_tokens),
            "ANTHROPIC_MODEL":     self.executor.anthropic.model,
            "CLAUDE_SUBPROCESS":   "on" if self.executor.claude.available else "off",
            "REVIEW_MODE":         "on" if self.executor.review_mode else "off",
            "WEBHOOK_URL":         rc["WEBHOOK_URL"] or "(not set)",
        }
        print(f"\n  {BOLD}{CYAN}Runtime Settings{RESET}")
        print(f"  {'─' * 50}")
        for k, v in settings.items():
            print(f"  {CYAN}{k:<22}{RESET} {v}")
        print(f"  {'─' * 50}")
        print(f"  {DIM}Use: set KEY=VALUE to change{RESET}\n")

