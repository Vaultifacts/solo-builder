"""ClaudeRunner — calls `claude -p` headlessly via subprocess."""
import json
import os
import subprocess


class ClaudeRunner:
    """Calls `claude -p` headlessly and returns (success, output_text).

    Tools:
      allowed_tools  — comma-separated default tool list (e.g. "Read,Glob,Grep")
                        "" means no tools (pure headless, fastest)
      Per-call tools override via run(..., tools="Bash,Write")
    """

    def __init__(self, timeout: int = 60, allowed_tools: str = "") -> None:
        self.timeout       = timeout
        self.allowed_tools = allowed_tools
        self.available     = self._check()

    def _check(self) -> bool:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def run(self, description: str, st_name: str, tools: str = "") -> tuple:
        """Returns (success: bool, output: str).

        tools — comma-separated list overriding self.allowed_tools for this call.
                Falls back to self.allowed_tools if empty.
        """
        if not self.available:
            return False, "claude CLI not found"
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        effective_tools = (tools or self.allowed_tools).strip()
        cmd = ["claude", "-p", description, "--output-format", "json"]
        if effective_tools:
            cmd += ["--allowedTools"] + [t.strip() for t in effective_tools.split(",") if t.strip()]

        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True,
                encoding="utf-8", timeout=self.timeout,
                env=env,
            )
            if r.returncode != 0:
                return False, (r.stderr or "non-zero exit").strip()[:200]
            data = json.loads(r.stdout)
            output = data.get("result", r.stdout).strip()
            return True, output
        except subprocess.TimeoutExpired:
            return False, f"Timed out after {self.timeout}s"
        except json.JSONDecodeError:
            out = r.stdout.strip()
            return (True, out) if out else (False, "empty response")
        except Exception as exc:
            return False, str(exc)[:200]
