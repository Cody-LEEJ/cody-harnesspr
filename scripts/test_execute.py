"""
execute.py 리팩터링 안전망 테스트.
리팩터링 전후 동작이 동일한지 검증한다.
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import execute as ex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_project(tmp_path):
    """phases/, CLAUDE.md, docs/ 를 갖춘 임시 프로젝트 구조."""
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()

    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Rules\n- rule one\n- rule two")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "arch.md").write_text("# Architecture\nSome content")
    (docs_dir / "guide.md").write_text("# Guide\nAnother doc")

    return tmp_path


@pytest.fixture
def phase_dir(tmp_project):
    """step 3개를 가진 phase 디렉토리."""
    d = tmp_project / "phases" / "0-mvp"
    d.mkdir()

    index = {
        "project": "TestProject",
        "phase": "mvp",
        "steps": [
            {"step": 0, "name": "setup", "status": "completed", "summary": "프로젝트 초기화 완료"},
            {"step": 1, "name": "core", "status": "completed", "summary": "핵심 로직 구현"},
            {"step": 2, "name": "ui", "status": "pending"},
        ],
    }
    (d / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    (d / "step2.md").write_text("# Step 2: UI\n\nUI를 구현하세요.")

    return d


@pytest.fixture
def top_index(tmp_project):
    """phases/index.json (top-level)."""
    top = {
        "phases": [
            {"dir": "0-mvp", "status": "pending"},
            {"dir": "1-polish", "status": "pending"},
        ]
    }
    p = tmp_project / "phases" / "index.json"
    p.write_text(json.dumps(top, indent=2))
    return p


@pytest.fixture
def executor(tmp_project, phase_dir):
    """테스트용 StepExecutor 인스턴스. git 호출은 별도 mock 필요."""
    with patch.object(ex, "ROOT", tmp_project):
        inst = ex.StepExecutor("0-mvp")
    # 내부 경로를 tmp_project 기준으로 재설정
    inst._root = str(tmp_project)
    inst._phases_dir = tmp_project / "phases"
    inst._phase_dir = phase_dir
    inst._phase_dir_name = "0-mvp"
    inst._index_file = phase_dir / "index.json"
    inst._top_index_file = tmp_project / "phases" / "index.json"
    inst._events_file = tmp_project / ".dev" / "runs" / "0-mvp" / "events.jsonl"
    return inst


# ---------------------------------------------------------------------------
# _stamp (= 이전 now_iso)
# ---------------------------------------------------------------------------

class TestStamp:
    def test_returns_kst_timestamp(self, executor):
        result = executor._stamp()
        assert "+0900" in result

    def test_format_is_iso(self, executor):
        result = executor._stamp()
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%S%z")
        assert dt.tzinfo is not None

    def test_is_current_time(self, executor):
        before = datetime.now(ex.StepExecutor.TZ).replace(microsecond=0)
        result = executor._stamp()
        after = datetime.now(ex.StepExecutor.TZ).replace(microsecond=0) + timedelta(seconds=1)
        parsed = datetime.strptime(result, "%Y-%m-%dT%H:%M:%S%z")
        assert before <= parsed <= after


# ---------------------------------------------------------------------------
# _read_json / _write_json
# ---------------------------------------------------------------------------

class TestJsonHelpers:
    def test_roundtrip(self, tmp_path):
        data = {"key": "값", "nested": [1, 2, 3]}
        p = tmp_path / "test.json"
        ex.StepExecutor._write_json(p, data)
        loaded = ex.StepExecutor._read_json(p)
        assert loaded == data

    def test_save_ensures_ascii_false(self, tmp_path):
        p = tmp_path / "test.json"
        ex.StepExecutor._write_json(p, {"한글": "테스트"})
        raw = p.read_text()
        assert "한글" in raw
        assert "\\u" not in raw

    def test_save_indented(self, tmp_path):
        p = tmp_path / "test.json"
        ex.StepExecutor._write_json(p, {"a": 1})
        raw = p.read_text()
        assert "\n" in raw

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ex.StepExecutor._read_json(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# _load_guardrails
# ---------------------------------------------------------------------------

class TestLoadGuardrails:
    """항상: CLAUDE.md + docs/GOLDEN_RULES.md. 그 외는 step이 `docs`로 선언한 것만."""

    def test_claude_md_only_when_no_docs_declared(self, executor, tmp_project):
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2})
        assert "# Rules" in result
        assert "rule one" in result
        assert "# Architecture" not in result
        assert "# Guide" not in result

    def test_loads_only_declared_docs(self, executor, tmp_project):
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2, "docs": ["docs/arch.md"]})
        assert "# Architecture" in result
        assert "## 참고 문서: docs/arch.md" in result
        assert "# Guide" not in result

    def test_golden_rules_always_loaded(self, executor, tmp_project):
        (tmp_project / "docs" / "GOLDEN_RULES.md").write_text("# Golden\n- never X")
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2})
        assert "never X" in result
        assert "docs/GOLDEN_RULES.md" in result

    def test_declared_order_preserved(self, executor, tmp_project):
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2, "docs": ["docs/guide.md", "docs/arch.md"]})
        assert result.index("# Guide") < result.index("# Architecture")

    def test_missing_declared_doc_warns_and_skips(self, executor, tmp_project, capsys):
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2, "docs": ["docs/nope.md", "docs/arch.md"]})
        assert "WARN" in capsys.readouterr().out
        assert "nope" not in result
        assert "# Architecture" in result

    def test_sections_separated_by_divider(self, executor, tmp_project):
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2, "docs": ["docs/arch.md"]})
        assert "---" in result

    def test_no_claude_md(self, executor, tmp_project):
        (tmp_project / "CLAUDE.md").unlink()
        with patch.object(ex, "ROOT", tmp_project):
            result = executor._load_guardrails({"step": 2, "docs": ["docs/arch.md"]})
        assert "CLAUDE.md" not in result
        assert "Architecture" in result

    def test_empty_project(self, tmp_path):
        with patch.object(ex, "ROOT", tmp_path):
            inst = ex.StepExecutor.__new__(ex.StepExecutor)
            result = inst._load_guardrails({"step": 0})
        assert result == ""


# ---------------------------------------------------------------------------
# _build_step_context
# ---------------------------------------------------------------------------

class TestBuildStepContext:
    def test_includes_completed_with_summary(self, phase_dir):
        index = json.loads((phase_dir / "index.json").read_text())
        result = ex.StepExecutor._build_step_context(index)
        assert "Step 0 (setup): 프로젝트 초기화 완료" in result
        assert "Step 1 (core): 핵심 로직 구현" in result

    def test_excludes_pending(self, phase_dir):
        index = json.loads((phase_dir / "index.json").read_text())
        result = ex.StepExecutor._build_step_context(index)
        assert "ui" not in result

    def test_excludes_completed_without_summary(self, phase_dir):
        index = json.loads((phase_dir / "index.json").read_text())
        del index["steps"][0]["summary"]
        result = ex.StepExecutor._build_step_context(index)
        assert "setup" not in result
        assert "core" in result

    def test_empty_when_no_completed(self):
        index = {"steps": [{"step": 0, "name": "a", "status": "pending"}]}
        result = ex.StepExecutor._build_step_context(index)
        assert result == ""

    def test_has_header(self, phase_dir):
        index = json.loads((phase_dir / "index.json").read_text())
        result = ex.StepExecutor._build_step_context(index)
        assert result.startswith("## 이전 Step 산출물")


# ---------------------------------------------------------------------------
# _build_preamble
# ---------------------------------------------------------------------------

class TestBuildPreamble:
    def test_includes_project_name(self, executor):
        result = executor._build_preamble("", "")
        assert "TestProject" in result

    def test_includes_guardrails(self, executor):
        result = executor._build_preamble("GUARD_CONTENT", "")
        assert "GUARD_CONTENT" in result

    def test_includes_step_context(self, executor):
        ctx = "## 이전 Step 산출물\n\n- Step 0: done"
        result = executor._build_preamble("", ctx)
        assert "이전 Step 산출물" in result

    def test_includes_commit_example(self, executor):
        result = executor._build_preamble("", "")
        assert "feat(mvp):" in result

    def test_includes_rules(self, executor):
        result = executor._build_preamble("", "")
        assert "작업 규칙" in result
        assert "AC" in result

    def test_no_retry_section_by_default(self, executor):
        result = executor._build_preamble("", "")
        assert "이전 시도 실패" not in result

    def test_retry_section_with_prev_error(self, executor):
        result = executor._build_preamble("", "", prev_error="타입 에러 발생")
        assert "이전 시도 실패" in result
        assert "타입 에러 발생" in result

    def test_includes_max_retries(self, executor):
        result = executor._build_preamble("", "")
        assert str(ex.StepExecutor.MAX_RETRIES) in result

    def test_includes_index_path(self, executor):
        result = executor._build_preamble("", "")
        assert "/phases/0-mvp/index.json" in result

    def test_ac_commands_listed_when_declared(self, executor):
        result = executor._build_preamble("", "", ac=["npm run build", "npm test"])
        assert "- `npm run build`" in result
        assert "- `npm test`" in result
        assert "독립 실행" in result

    def test_generic_ac_rule_when_not_declared(self, executor):
        result = executor._build_preamble("", "")
        assert "AC(Acceptance Criteria) 검증을 직접 실행하라" in result
        assert "독립 실행" not in result


# ---------------------------------------------------------------------------
# _update_top_index
# ---------------------------------------------------------------------------

class TestUpdateTopIndex:
    def test_completed(self, executor, top_index):
        executor._top_index_file = top_index
        executor._update_top_index("completed")
        data = json.loads(top_index.read_text())
        mvp = next(p for p in data["phases"] if p["dir"] == "0-mvp")
        assert mvp["status"] == "completed"
        assert "completed_at" in mvp

    def test_error(self, executor, top_index):
        executor._top_index_file = top_index
        executor._update_top_index("error")
        data = json.loads(top_index.read_text())
        mvp = next(p for p in data["phases"] if p["dir"] == "0-mvp")
        assert mvp["status"] == "error"
        assert "failed_at" in mvp

    def test_blocked(self, executor, top_index):
        executor._top_index_file = top_index
        executor._update_top_index("blocked")
        data = json.loads(top_index.read_text())
        mvp = next(p for p in data["phases"] if p["dir"] == "0-mvp")
        assert mvp["status"] == "blocked"
        assert "blocked_at" in mvp

    def test_other_phases_unchanged(self, executor, top_index):
        executor._top_index_file = top_index
        executor._update_top_index("completed")
        data = json.loads(top_index.read_text())
        polish = next(p for p in data["phases"] if p["dir"] == "1-polish")
        assert polish["status"] == "pending"

    def test_nonexistent_dir_is_noop(self, executor, top_index):
        executor._top_index_file = top_index
        executor._phase_dir_name = "no-such-dir"
        original = json.loads(top_index.read_text())
        executor._update_top_index("completed")
        after = json.loads(top_index.read_text())
        for p_before, p_after in zip(original["phases"], after["phases"]):
            assert p_before["status"] == p_after["status"]

    def test_no_top_index_file(self, executor, tmp_path):
        executor._top_index_file = tmp_path / "nonexistent.json"
        executor._update_top_index("completed")  # should not raise


# ---------------------------------------------------------------------------
# _checkout_branch (mocked)
# ---------------------------------------------------------------------------

class TestCheckoutBranch:
    def _mock_git(self, executor, responses):
        call_idx = {"i": 0}
        def fake_git(*args):
            idx = call_idx["i"]
            call_idx["i"] += 1
            if idx < len(responses):
                return responses[idx]
            return MagicMock(returncode=0, stdout="", stderr="")
        executor._run_git = fake_git

    def test_already_on_branch(self, executor):
        self._mock_git(executor, [
            MagicMock(returncode=0, stdout="feat-mvp\n", stderr=""),
        ])
        executor._checkout_branch()  # should return without checkout

    def test_branch_exists_checkout(self, executor):
        self._mock_git(executor, [
            MagicMock(returncode=0, stdout="main\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ])
        executor._checkout_branch()

    def test_branch_not_exists_create(self, executor):
        self._mock_git(executor, [
            MagicMock(returncode=0, stdout="main\n", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="not found"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ])
        executor._checkout_branch()

    def test_checkout_fails_exits(self, executor):
        self._mock_git(executor, [
            MagicMock(returncode=0, stdout="main\n", stderr=""),
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="dirty tree"),
        ])
        with pytest.raises(SystemExit) as exc_info:
            executor._checkout_branch()
        assert exc_info.value.code == 1

    def test_no_git_exits(self, executor):
        self._mock_git(executor, [
            MagicMock(returncode=1, stdout="", stderr="not a git repo"),
        ])
        with pytest.raises(SystemExit) as exc_info:
            executor._checkout_branch()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _commit_step (mocked)
# ---------------------------------------------------------------------------

class TestCommitStep:
    def test_two_phase_commit(self, executor):
        calls = []
        def fake_git(*args):
            calls.append(args)
            if args[:2] == ("diff", "--cached"):
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="", stderr="")
        executor._run_git = fake_git

        executor._commit_step(2, "ui")

        commit_calls = [c for c in calls if c[0] == "commit"]
        assert len(commit_calls) == 2
        assert "feat(mvp):" in commit_calls[0][2]
        assert "chore(mvp):" in commit_calls[1][2]

    def test_no_code_changes_skips_feat_commit(self, executor):
        call_count = {"diff": 0}
        calls = []
        def fake_git(*args):
            calls.append(args)
            if args[:2] == ("diff", "--cached"):
                call_count["diff"] += 1
                if call_count["diff"] == 1:
                    return MagicMock(returncode=0)
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="", stderr="")
        executor._run_git = fake_git

        executor._commit_step(2, "ui")

        commit_msgs = [c[2] for c in calls if c[0] == "commit"]
        assert len(commit_msgs) == 1
        assert "chore" in commit_msgs[0]


# ---------------------------------------------------------------------------
# _invoke_claude (mocked)
# ---------------------------------------------------------------------------

class TestInvokeClaude:
    def test_invokes_claude_with_correct_args(self, executor):
        mock_result = MagicMock(returncode=0, stdout='{"result": "ok"}', stderr="")
        step = {"step": 2, "name": "ui"}
        preamble = "PREAMBLE\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            output = executor._invoke_claude(step, preamble)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--output-format" in cmd
        assert "PREAMBLE" in cmd[-1]
        assert "UI를 구현하세요" in cmd[-1]

    def test_saves_output_json(self, executor):
        mock_result = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        step = {"step": 2, "name": "ui"}

        with patch("subprocess.run", return_value=mock_result):
            executor._invoke_claude(step, "preamble")

        output_file = executor._phase_dir / "step2-output.json"
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["step"] == 2
        assert data["name"] == "ui"
        assert data["exitCode"] == 0

    def test_nonexistent_step_file_exits(self, executor):
        step = {"step": 99, "name": "nonexistent"}
        with pytest.raises(SystemExit) as exc_info:
            executor._invoke_claude(step, "preamble")
        assert exc_info.value.code == 1

    def test_timeout_is_1800(self, executor):
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        step = {"step": 2, "name": "ui"}

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            executor._invoke_claude(step, "preamble")

        assert mock_run.call_args[1]["timeout"] == 1800


    def test_saves_parsed_fields_from_json_stdout(self, executor):
        stdout = json.dumps({"type": "result", "duration_ms": 1234, "num_turns": 5,
                             "total_cost_usd": 0.12, "is_error": False, "session_id": "abc",
                             "result": "done"})
        mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            output = executor._invoke_claude({"step": 2, "name": "ui"}, "p")
        assert output["parsed"] == {"duration_ms": 1234, "num_turns": 5, "total_cost_usd": 0.12,
                                    "is_error": False, "session_id": "abc"}
        assert output["stdout"] == stdout  # 원문 유지

    def test_parsed_is_none_for_non_json(self, executor):
        mock_result = MagicMock(returncode=1, stdout="not json at all", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            output = executor._invoke_claude({"step": 2, "name": "ui"}, "p")
        assert output["parsed"] is None

    def test_emits_claude_done_event(self, executor):
        mock_result = MagicMock(returncode=0, stdout='{"num_turns": 3}', stderr="")
        with patch("subprocess.run", return_value=mock_result):
            executor._invoke_claude({"step": 2, "name": "ui"}, "p")
        events = [json.loads(l) for l in executor._events_file.read_text().splitlines()]
        assert events[-1]["event"] == "claude_done"
        assert events[-1]["step"] == 2
        assert events[-1]["num_turns"] == 3


# ---------------------------------------------------------------------------
# _emit / _parse_claude_output
# ---------------------------------------------------------------------------

class TestEmit:
    def test_appends_valid_json_lines(self, executor):
        executor._emit("a", step=1)
        executor._emit("b", step=2, error="x")
        lines = executor._events_file.read_text().splitlines()
        assert len(lines) == 2
        a, b = (json.loads(l) for l in lines)
        assert a["event"] == "a" and a["step"] == 1 and a["phase"] == "mvp" and "ts" in a
        assert b["event"] == "b" and b["error"] == "x"

    def test_creates_parent_dirs(self, executor):
        assert not executor._events_file.parent.exists()
        executor._emit("x")
        assert executor._events_file.exists()

    def test_korean_not_escaped(self, executor):
        executor._emit("x", error="한글")
        assert "한글" in executor._events_file.read_text()


class TestParseClaudeOutput:
    def test_extracts_known_keys_only(self):
        out = ex.StepExecutor._parse_claude_output('{"duration_ms": 1, "result": "long text", "extra": 1}')
        assert out == {"duration_ms": 1}

    def test_non_json_returns_none(self):
        assert ex.StepExecutor._parse_claude_output("oops") is None

    def test_json_array_returns_none(self):
        assert ex.StepExecutor._parse_claude_output("[1,2]") is None


# ---------------------------------------------------------------------------
# _run_ac — executor가 AC를 직접 실행
# ---------------------------------------------------------------------------

class TestRunAc:
    def test_all_pass_returns_none(self, executor):
        assert executor._run_ac(2, ["true", "echo ok"]) is None

    def test_first_failure_returns_error_with_cmd(self, executor):
        err = executor._run_ac(2, ["true", "echo boom >&2; exit 3", "true"])
        assert err is not None
        assert "exit 3" in err
        assert "boom" in err
        assert "echo boom" in err

    def test_stops_at_first_failure(self, executor, tmp_project):
        marker = tmp_project / "ran"
        executor._run_ac(2, ["false", f"touch {marker}"])
        assert not marker.exists()

    def test_runs_in_root(self, executor, tmp_project):
        assert executor._run_ac(2, ["test -f CLAUDE.md"]) is None

    def test_emits_ac_result_per_command(self, executor):
        executor._run_ac(2, ["true", "false"])
        events = [json.loads(l) for l in executor._events_file.read_text().splitlines()]
        ac = [e for e in events if e["event"] == "ac_result"]
        assert [e["exit_code"] for e in ac] == [0, 1]
        assert ac[0]["cmd"] == "true"

    def test_timeout_is_failure(self, executor):
        executor.AC_TIMEOUT = 1
        err = executor._run_ac(2, ["sleep 5"])
        assert err is not None and "timeout" in err


# ---------------------------------------------------------------------------
# _execute_single_step 판정 — AC 결과가 세션 자기 신고보다 우선
# ---------------------------------------------------------------------------

class TestVerdict:
    """_invoke_claude를 '세션이 index.json에 status를 쓰는' 가짜로 바꿔 판정 로직만 검증."""

    def _fake_session(self, executor, status, **extra):
        calls = []
        def fake_invoke(step, preamble):
            calls.append(preamble)
            idx = executor._read_json(executor._index_file)
            for s in idx["steps"]:
                if s["step"] == step["step"]:
                    s["status"] = status
                    s.update(extra)
            executor._write_json(executor._index_file, idx)
            return {}
        executor._invoke_claude = fake_invoke
        executor._commit_step = lambda *a: None
        executor._update_top_index = lambda *a: None
        return calls

    def _status(self, executor, n=2):
        return next(s for s in executor._read_json(executor._index_file)["steps"] if s["step"] == n)

    def test_ac_pass_and_session_completed(self, executor):
        self._fake_session(executor, "completed", summary="done")
        assert executor._execute_single_step({"step": 2, "name": "ui", "ac": ["true"]}) is True
        assert self._status(executor)["status"] == "completed"

    def test_ac_pass_overrides_session_error(self, executor, capsys):
        self._fake_session(executor, "error", error_message="i gave up")
        assert executor._execute_single_step({"step": 2, "name": "ui", "ac": ["true"]}) is True
        st = self._status(executor)
        assert st["status"] == "completed"
        assert "error_message" not in st
        assert "판정 불일치" in capsys.readouterr().out

    def test_ac_fail_overrides_session_completed_and_feeds_error_back(self, executor):
        calls = self._fake_session(executor, "completed", summary="lie")
        with pytest.raises(SystemExit) as e:
            executor._execute_single_step({"step": 2, "name": "ui", "ac": ["echo nope >&2; exit 1"]})
        assert e.value.code == 1
        assert len(calls) == ex.StepExecutor.MAX_RETRIES
        # 2회차부터는 AC 출력이 prev_error로 프롬프트에 들어간다
        assert "이전 시도 실패" in calls[1] and "nope" in calls[1]
        st = self._status(executor)
        assert st["status"] == "error"
        assert "AC 실패" in st["error_message"]

    def test_no_ac_trusts_session_completed(self, executor, capsys):
        self._fake_session(executor, "completed", summary="ok")
        assert executor._execute_single_step({"step": 2, "name": "ui"}) is True
        assert "AC 미선언" in capsys.readouterr().out

    def test_no_ac_session_error_retries_then_fails(self, executor):
        calls = self._fake_session(executor, "error", error_message="boom")
        with pytest.raises(SystemExit) as e:
            executor._execute_single_step({"step": 2, "name": "ui"})
        assert e.value.code == 1
        assert len(calls) == ex.StepExecutor.MAX_RETRIES

    def test_blocked_stops_before_ac(self, executor, tmp_project):
        self._fake_session(executor, "blocked", blocked_reason="need API key")
        marker = tmp_project / "ac-ran"
        with pytest.raises(SystemExit) as e:
            executor._execute_single_step({"step": 2, "name": "ui", "ac": [f"touch {marker}"]})
        assert e.value.code == 2
        assert not marker.exists()

    def test_ac_taken_from_step_dict_not_index(self, executor):
        """세션이 index.json에서 ac를 지워도 executor는 호출 전 step dict의 ac로 판정한다."""
        def fake_invoke(step, preamble):
            idx = executor._read_json(executor._index_file)
            for s in idx["steps"]:
                if s["step"] == 2:
                    s["status"] = "completed"
                    s.pop("ac", None)
            executor._write_json(executor._index_file, idx)
        executor._invoke_claude = fake_invoke
        executor._commit_step = lambda *a: None
        executor._update_top_index = lambda *a: None
        with pytest.raises(SystemExit):
            executor._execute_single_step({"step": 2, "name": "ui", "ac": ["false"]})


# ---------------------------------------------------------------------------
# progress_indicator (= 이전 Spinner)
# ---------------------------------------------------------------------------

class TestProgressIndicator:
    def test_context_manager(self):
        import time
        with ex.progress_indicator("test") as pi:
            time.sleep(0.15)
        assert pi.elapsed >= 0.1

    def test_elapsed_increases(self):
        import time
        with ex.progress_indicator("test") as pi:
            time.sleep(0.2)
        assert pi.elapsed > 0


# ---------------------------------------------------------------------------
# main() CLI 파싱 (mocked)
# ---------------------------------------------------------------------------

class TestMainCli:
    def test_no_args_exits(self):
        with patch("sys.argv", ["execute.py"]):
            with pytest.raises(SystemExit) as exc_info:
                ex.main()
            assert exc_info.value.code == 2  # argparse exits with 2

    def test_invalid_phase_dir_exits(self):
        with patch("sys.argv", ["execute.py", "nonexistent"]):
            with patch.object(ex, "ROOT", Path("/tmp/fake_nonexistent")):
                with pytest.raises(SystemExit) as exc_info:
                    ex.main()
                assert exc_info.value.code == 1

    def test_missing_index_exits(self, tmp_project):
        (tmp_project / "phases" / "empty").mkdir()
        with patch("sys.argv", ["execute.py", "empty"]):
            with patch.object(ex, "ROOT", tmp_project):
                with pytest.raises(SystemExit) as exc_info:
                    ex.main()
                assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _check_blockers (= 이전 main() error/blocked 체크)
# ---------------------------------------------------------------------------

class TestCheckBlockers:
    def _make_executor_with_steps(self, tmp_project, steps):
        d = tmp_project / "phases" / "test-phase"
        d.mkdir(exist_ok=True)
        index = {"project": "T", "phase": "test", "steps": steps}
        (d / "index.json").write_text(json.dumps(index))

        with patch.object(ex, "ROOT", tmp_project):
            inst = ex.StepExecutor.__new__(ex.StepExecutor)
        inst._root = str(tmp_project)
        inst._phases_dir = tmp_project / "phases"
        inst._phase_dir = d
        inst._phase_dir_name = "test-phase"
        inst._index_file = d / "index.json"
        inst._top_index_file = tmp_project / "phases" / "index.json"
        inst._phase_name = "test"
        inst._total = len(steps)
        return inst

    def test_error_step_exits_1(self, tmp_project):
        steps = [
            {"step": 0, "name": "ok", "status": "completed"},
            {"step": 1, "name": "bad", "status": "error", "error_message": "fail"},
        ]
        inst = self._make_executor_with_steps(tmp_project, steps)
        with pytest.raises(SystemExit) as exc_info:
            inst._check_blockers()
        assert exc_info.value.code == 1

    def test_blocked_step_exits_2(self, tmp_project):
        steps = [
            {"step": 0, "name": "ok", "status": "completed"},
            {"step": 1, "name": "stuck", "status": "blocked", "blocked_reason": "API key"},
        ]
        inst = self._make_executor_with_steps(tmp_project, steps)
        with pytest.raises(SystemExit) as exc_info:
            inst._check_blockers()
        assert exc_info.value.code == 2
