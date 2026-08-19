#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.

Usage:
    python3 scripts/execute.py <phase-dir> [--push]        # 순차 실행
    python3 scripts/execute.py <phase-dir> --status        # 진행 현황
    python3 scripts/execute.py <phase-dir> --dry-run       # 주입 문서·AC·프롬프트 크기만 출력 (claude/git 미호출)
    python3 scripts/execute.py <phase-dir> --retry N       # error/blocked step N을 pending으로 되돌리고 이어서 실행
"""

import argparse
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다."""
    frames = "◐◓◑◒"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스."""

    MAX_RETRIES = 3
    AC_TIMEOUT = 600  # AC 커맨드 1개당 최대 실행 시간(초)
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))

    def __init__(self, phase_dir_name: str, *, auto_push: bool = False):
        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._events_file = ROOT / ".dev" / "runs" / phase_dir_name / "events.jsonl"
        self._auto_push = auto_push

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])

    def run(self):
        self._print_header()
        self._check_blockers()
        self._checkout_branch()
        self._ensure_created_at()
        self._emit("phase_start", total_steps=self._total)
        self._execute_all_steps()
        self._finalize()

    STATUS_ICON = {"completed": "✓", "error": "✗", "blocked": "⏸", "pending": "·"}

    def status(self):
        """phase 진행 현황을 출력한다. git·claude 호출 없음."""
        index = self._read_json(self._index_file)
        print(f"\nPhase: {self._phase_name} ({self._phase_dir_name})"
              f"  created: {index.get('created_at', '-')}  completed: {index.get('completed_at', '-')}")
        for s in index["steps"]:
            icon = self.STATUS_ICON.get(s["status"], "?")
            ts = s.get("completed_at") or s.get("failed_at") or s.get("blocked_at") or s.get("started_at") or ""
            print(f"  {icon} {s['step']:>2}  {s['name']:<20} {s['status']:<10} {ts}")
            detail = s.get("error_message") or s.get("blocked_reason") or s.get("summary")
            if detail:
                print(f"         {detail[:120]}")
        print()

    def retry(self, step_num: int):
        """error/blocked 상태의 step을 pending으로 되돌린다. 이어서 run()이 그 step부터 실행한다."""
        index = self._read_json(self._index_file)
        step = next((s for s in index["steps"] if s["step"] == step_num), None)
        if step is None:
            print(f"ERROR: step {step_num} not found")
            sys.exit(1)
        if step["status"] not in ("error", "blocked"):
            print(f"ERROR: step {step_num} is '{step['status']}' — error/blocked 상태만 --retry 할 수 있다")
            sys.exit(1)
        prev = step["status"]
        step["status"] = "pending"
        for k in ("error_message", "blocked_reason", "failed_at", "blocked_at"):
            step.pop(k, None)
        self._write_json(self._index_file, index)
        self._update_top_index("pending")
        self._emit("step_reset", step=step_num, from_status=prev)
        print(f"  ↺ Step {step_num} ({step['name']}): {prev} → pending")

    def dry_run(self):
        """claude·git 호출 없이, pending step마다 무엇이 주입되고 무엇으로 판정하는지 보여준다."""
        self._print_header()
        self._check_blockers()
        index = self._read_json(self._index_file)
        pending = [s for s in index["steps"] if s["status"] == "pending"]
        print(f"  [dry-run] 실행 예정 step: {len(pending)}개 (branch: feat-{self._phase_name})\n")
        for step in pending:
            print(f"  Step {step['step']}: {step['name']}")
            for rel in self.ALWAYS_DOCS:
                print(f"    doc {'✓' if (ROOT / rel).exists() else '✗'} {rel} (항상)")
            for rel in step.get("docs", []):
                print(f"    doc {'✓' if (ROOT / rel).exists() else '✗'} {rel}")
            ac = step.get("ac") or []
            for cmd in ac:
                print(f"    ac  {cmd}")
            if not ac:
                print("    ac  (미선언 — 세션 자기 신고로 판정)")
            step_file = self._phase_dir / f"step{step['step']}.md"
            if step_file.exists():
                guardrails = self._load_guardrails(step)
                prompt = self._build_preamble(guardrails, self._build_step_context(index), ac=ac) + step_file.read_text()
                print(f"    prompt {len(prompt):,} chars")
            else:
                print(f"    step file ✗ {step_file.name}")
            print()

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- 이벤트 로그 (.dev/runs/{phase}/events.jsonl) ---

    def _emit(self, event: str, **fields):
        """기계 판독용 JSON line 1개를 append한다. 사람용 출력은 print가 담당한다."""
        record = {"ts": self._stamp(), "phase": self._phase_name, "event": event, **fields}
        self._events_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # --- git ---

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print(f"  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        r = self._run_git("checkout", branch) if r.returncode == 0 else self._run_git("checkout", "-b", branch)

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print(f"  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"phases/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{self._phase_dir_name}/index.json"

        self._run_git("add", "-A")
        self._run_git("reset", "HEAD", "--", output_rel)
        self._run_git("reset", "HEAD", "--", index_rel)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: 코드 커밋 실패: {r.stderr.strip()}")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                print(f"  WARN: housekeeping 커밋 실패: {r.stderr.strip()}")

    # --- top-level index ---

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                ts_key = {"completed": "completed_at", "error": "failed_at", "blocked": "blocked_at"}.get(status)
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    ALWAYS_DOCS = ("CLAUDE.md", "docs/GOLDEN_RULES.md")

    def _load_guardrails(self, step: dict) -> str:
        """항상 주입: CLAUDE.md + GOLDEN_RULES. 그 외 문서는 step이 `docs`로 선언한 것만."""
        sections = []
        for rel in self.ALWAYS_DOCS:
            f = ROOT / rel
            if f.exists():
                sections.append(f"## 프로젝트 규칙 ({rel})\n\n{f.read_text()}")
        for rel in step.get("docs", []):
            f = ROOT / rel
            if not f.exists():
                print(f"  WARN: step {step.get('step')}이 선언한 문서가 없음: {rel}")
                continue
            sections.append(f"## 참고 문서: {rel}\n\n{f.read_text()}")
        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def _build_preamble(self, guardrails: str, step_context: str,
                        prev_error: Optional[str] = None, ac: Optional[list] = None) -> str:
        commit_example = self.FEAT_MSG.format(
            phase=self._phase_name, num="N", name="<step-name>"
        )
        retry_section = ""
        if prev_error:
            retry_section = (
                f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
                f"{prev_error}\n\n---\n\n"
            )
        if ac:
            ac_rule = (
                "4. 아래 AC 커맨드를 직접 실행해 통과시켜라. "
                "세션 종료 후 executor가 동일 커맨드를 독립 실행해 통과/실패를 판정한다:\n"
                + "".join(f"   - `{cmd}`\n" for cmd in ac)
            )
        else:
            ac_rule = "4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{retry_section}"
            f"## 작업 규칙\n\n"
            f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            f"3. 기존 테스트를 깨뜨리지 마라.\n"
            f"{ac_rule}"
            f"5. /phases/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            f"   - AC 통과 → \"completed\" + \"summary\" 필드에 이 step의 산출물을 한 줄로 요약\n"
            f"   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → \"error\" + \"error_message\" 기록\n"
            f"   - 사용자 개입이 필요한 경우 (API 키, 인증, 수동 설정 등) → \"blocked\" + \"blocked_reason\" 기록 후 즉시 중단\n"
            f"6. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    # --- Claude 호출 ---

    def _invoke_claude(self, step: dict, preamble: str) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            print(f"  ERROR: {step_file} not found")
            sys.exit(1)

        prompt = preamble + step_file.read_text()
        result = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json", prompt],
            cwd=self._root, capture_output=True, text=True, timeout=1800,
        )

        if result.returncode != 0:
            print(f"\n  WARN: Claude가 비정상 종료됨 (code {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")

        output = {
            "step": step_num, "name": step_name,
            "exitCode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "parsed": self._parse_claude_output(result.stdout),
        }
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self._emit("claude_done", step=step_num, exit_code=result.returncode, **(output["parsed"] or {}))
        return output

    @staticmethod
    def _parse_claude_output(stdout: str) -> Optional[dict]:
        """`claude --output-format json` 결과에서 비용/턴/시간 필드만 추출. JSON이 아니면 None."""
        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        keys = ("duration_ms", "num_turns", "total_cost_usd", "is_error", "session_id")
        return {k: data[k] for k in keys if k in data}

    # --- AC 독립 실행 ---

    def _run_ac(self, step_num: int, ac: list) -> Optional[str]:
        """AC 커맨드를 순서대로 executor가 직접 실행한다. 전부 통과하면 None, 첫 실패에서 에러 텍스트."""
        for cmd in ac:
            t0 = time.monotonic()
            try:
                r = subprocess.run(cmd, shell=True, cwd=self._root, capture_output=True, text=True,
                                   timeout=self.AC_TIMEOUT)
                code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired:
                code, out = -1, f"timeout after {self.AC_TIMEOUT}s"
            self._emit("ac_result", step=step_num, cmd=cmd, exit_code=code,
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            if code != 0:
                return f"AC 실패: `{cmd}` (exit {code})\n{out[-2000:]}"
        return None

    # --- 헤더 & 검증 ---

    def _print_header(self):
        print(f"\n{'='*60}")
        print(f"  Harness Step Executor")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        if self._auto_push:
            print(f"  Auto-push: enabled")
        print(f"{'='*60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in reversed(index["steps"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print(f"  Fix, then: python3 scripts/execute.py {self._phase_dir_name} --retry {s['step']}")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print(f"  Resolve, then: python3 scripts/execute.py {self._phase_dir_name} --retry {s['step']}")
                sys.exit(2)
            if s["status"] != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- 실행 루프 ---

    def _execute_single_step(self, step: dict) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 False."""
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        guardrails = self._load_guardrails(step)
        prev_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            preamble = self._build_preamble(guardrails, step_context, prev_error, ac=step.get("ac"))

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                self._invoke_claude(step, preamble)
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            self_status = next((s.get("status", "pending") for s in index["steps"] if s["step"] == step_num), "pending")
            ts = self._stamp()

            if self_status == "blocked":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["blocked_at"] = ts
                self._write_json(self._index_file, index)
                reason = next((s.get("blocked_reason", "") for s in index["steps"] if s["step"] == step_num), "")
                print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
                print(f"    Reason: {reason}")
                self._emit("step_blocked", step=step_num, attempt=attempt, reason=reason)
                self._update_top_index("blocked")
                sys.exit(2)

            # 판정: AC가 선언돼 있으면 executor가 직접 실행한 결과가 우선한다. 세션의 자기 신고는 보조 신호.
            # `ac`는 호출 전에 읽은 step dict에서 가져온다 — 세션이 index.json을 고쳐도 영향을 받지 않는다.
            ac = step.get("ac") or []
            ac_error = None
            if ac:
                ac_error = self._run_ac(step_num, ac)
                verdict = "completed" if ac_error is None else "failed"
                self_verdict = "completed" if self_status == "completed" else "failed"
                self._emit("verdict", step=step_num, attempt=attempt, self_status=self_status,
                           ac_pass=ac_error is None, final=verdict)
                if verdict != self_verdict:
                    print(f"  ! 판정 불일치: 세션 status={self_status}, AC={'pass' if ac_error is None else 'fail'}"
                          f" → executor 판정({verdict}) 우선")
                    self._emit("verdict_mismatch", step=step_num, attempt=attempt,
                               self_status=self_status, ac_pass=ac_error is None)
            else:
                if attempt == 1:
                    print(f"  WARN: step {step_num}에 AC 미선언 — 세션 자기 신고로 판정한다")
                verdict = "completed" if self_status == "completed" else "failed"

            if verdict == "completed":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "completed"
                        s["completed_at"] = ts
                        s.pop("error_message", None)
                        if not s.get("summary"):
                            print(f"  WARN: step {step_num} summary 없음 — 다음 step 컨텍스트에서 빠진다")
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                self._emit("step_completed", step=step_num, attempt=attempt, elapsed_s=elapsed)
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                return True

            err_msg = ac_error or next(
                (s.get("error_message", "Step did not update status") for s in index["steps"] if s["step"] == step_num),
                "Step did not update status",
            )

            if attempt < self.MAX_RETRIES:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "pending"
                        s.pop("error_message", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                self._emit("step_retry", step=step_num, attempt=attempt, error=err_msg)
                print(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "error"
                        s["error_message"] = f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}"
                        s["failed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✗ Step {step_num}: {step_name} failed after {self.MAX_RETRIES} attempts [{elapsed}s]")
                print(f"    Error: {err_msg}")
                self._emit("step_failed", step=step_num, attempt=attempt, error=err_msg)
                self._update_top_index("error")
                sys.exit(1)

        return False  # unreachable

    def _execute_all_steps(self):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                print("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._emit("step_start", step=step_num, name=pending["name"])
            self._execute_single_step(pending)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")
        self._emit("phase_completed")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'='*60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    parser.add_argument("--status", action="store_true", help="Show phase progress and exit")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run (docs, AC, prompt size) without calling claude/git")
    parser.add_argument("--retry", type=int, metavar="N", help="Reset error/blocked step N to pending, then continue")
    args = parser.parse_args()

    executor = StepExecutor(args.phase_dir, auto_push=args.push)
    if args.status:
        executor.status()
        return
    if args.retry is not None:
        executor.retry(args.retry)
    if args.dry_run:
        executor.dry_run()
        return
    executor.run()


if __name__ == "__main__":
    main()
