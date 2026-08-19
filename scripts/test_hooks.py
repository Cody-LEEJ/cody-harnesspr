"""
.claude/hooks/*.sh 동작 검증.
Claude Code hook 규약: stdin JSON 입력, 차단은 permissionDecision: deny JSON 또는 exit 2.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
GUARD = HOOKS / "dangerous-cmd-guard.sh"
STOP = HOOKS / "stop-verify.sh"


def run_hook(script: Path, payload: dict, env: dict = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(script)], input=json.dumps(payload), capture_output=True, text=True,
        env={**os.environ, **(env or {})}, timeout=30,
    )


class TestDangerousCmdGuard:
    @pytest.mark.parametrize("cmd", [
        "rm -rf /tmp/x",
        "cd foo && rm  -rf build",
        "git push --force origin main",
        "git push -f origin main",
        "git reset --hard HEAD~1",
        "psql -c 'DROP TABLE users'",
    ])
    def test_denies_dangerous(self, cmd):
        r = run_hook(GUARD, {"tool_input": {"command": cmd}})
        assert r.returncode == 0
        out = json.loads(r.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.parametrize("cmd", ["ls -la", "git push origin main", "rm file.txt", "pytest -q"])
    def test_allows_safe(self, cmd):
        r = run_hook(GUARD, {"tool_input": {"command": cmd}})
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_empty_input(self):
        r = run_hook(GUARD, {})
        assert r.returncode == 0
        assert r.stdout.strip() == ""


class TestStopVerify:
    def test_skips_when_stop_hook_active(self, tmp_path):
        r = run_hook(STOP, {"stop_hook_active": True}, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
        assert r.returncode == 0

    def test_skips_without_package_json(self, tmp_path):
        r = run_hook(STOP, {}, {"CLAUDE_PROJECT_DIR": str(tmp_path)})
        assert r.returncode == 0
        assert r.stderr == ""
