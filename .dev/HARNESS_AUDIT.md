# 하네스 진단 & 로드맵

Agentic Engineering 5 Pillar / Harness Engineering 6축 기준으로 이 리포의 현재 상태를 진단한 문서.

> 이 파일은 **하네스 자신의 기록**이다. 제품 문서(`docs/`)가 아니므로 `.dev/`에 둔다 — `/harness`가 `docs/`를 읽을 때 과거 진단("P0 가드가 동작하지 않는다" 등)을 현재 사실로 오인하지 않게 하기 위함. 사용법은 루트 `HARNESS.md`.

**1차 진단**: 2026-08-16 · 커밋 `da676bc` → 아래 "요약"부터의 본문. 고쳐진 항목도 이력으로 그대로 둔다.
**2차 진단**: 2026-08-19 · 1차 수정 8커밋 후 → 바로 아래 "2차 진단" 섹션.
**전제 (수정됨 2026-08-19)**: 이 리포는 **clone해서 그 안에 제품을 만드는 템플릿**이다. 루트 `CLAUDE.md`·`docs/`는 제품의 것이고, `scripts/`·`.claude/`는 프레임워크 자신의 것이다. 진단 당시 전제("제품 코드는 여기 들어오지 않는다")는 사용자 확인으로 폐기했고, 그에 따라 로드맵 2(`templates/` 분리)는 다른 방식으로 해소했다.

범례: ● 충족 · ◐ 부분 · ✗ 없음

---

## 이행 현황 (2026-08-19, 브랜치 `feat/harness-audit`)

| # | 작업 | 상태 | 커밋 | 비고 |
|---|------|------|------|------|
| 3 | hook 복구 + permissions | ✓ | `fix(hooks)` | `.claude/hooks/{dangerous-cmd-guard,stop-verify}.sh` + `scripts/test_hooks.py`. 추가 발견: 기존 가드는 `exit 1`이라 env var가 있었어도 차단 불가(차단은 exit 2 / deny JSON). Stop hook은 `package.json` 없으면 skip, 실패 시 exit 2 |
| 4 | 컨텍스트 선택 주입 | ✓ | `feat(executor): inject only…` | 항상 CLAUDE.md + GOLDEN_RULES, 그 외는 step `docs` 선언분만 |
| 6 | 구조화 이벤트 로그 | ✓ | `feat(executor): structured event log` | `.dev/runs/{phase}/events.jsonl`, `step{N}-output.json`에 `parsed`(cost/turns/duration) |
| 1 | AC 독립 실행 게이트 | ✓ | `feat(executor): independent AC gate` | step `ac` 배열을 executor가 직접 실행해 판정. 세션 신고와 불일치 시 `verdict_mismatch` 기록. `ac`는 호출 전 step dict에서 읽어 세션 조작에 면역 |
| 5 | friction codify | ✓ | `feat(executor): codify manual recovery` | `--retry N` / `--status` / `--dry-run`. `--reset`은 순차 모델에서 `--retry`와 동일해 만들지 않음 |
| 8 | GOLDEN_RULES + 상호참조 | ✓ | `docs: GOLDEN_RULES + …` | GOLDEN_RULES ← execute.py 주입 / review.md 기준 / retro.md 승격. harness.md → /review → /retro 연결. ADR → `decisions/` 분할. 배너 4종 |
| 2 | `templates/` 분리 | **대체** | 위 `docs:` 커밋 | 사용 모델이 "clone = 제품 리포"이므로 분리 대신: 플레이스홀더 배너 + `scripts/CLAUDE.md`(프레임워크 자체 규칙, 폴더 레벨) + Stop hook 조건 실행으로 P0-2·Pillar 4 오염을 해소 |
| 7 | worktree 격리 + `--dry-run` | **부분** | `feat(executor): codify…` | `--dry-run`만. worktree는 "phases/ 선커밋·npm install 재실행" 제약이 사용 흐름에 영향을 주므로 phase 1회 실전 후 결정하기로 보류 |
| 5-1 | git remote 재배선 | ✓ | — | origin → `Cody-LEEJ/cody-harnesspr`, upstream → `jha0313/harness_framework`. push는 사용자가 |

여전히 비어 있는 것 (의도적): 독립 리뷰 세션(`--review`, 모델 분리), worktree, LogQL Layer 2, MCP, 시각 검증. "지금 하지 말 것" 표 참조.

---

## 2차 진단 (2026-08-19, 1차 수정 후 재검토)

리포 전체(~2,400줄)를 다시 읽고 5 Pillar + 6축에 대조했다.

한 줄: **1차 로드맵 8개 중 7개가 코드·테스트로 이행됐고, 남은 갭은 대부분 의도적 보류다. 보류가 아닌데 빠진 것 4개와, 1차 수정이 만든 새 오염 1개를 찾았다. 실행기(`execute.py`) 자체의 결함은 없다.**

범례: ● 충족 · ◐ 부분 · ✗ 없음 · ⏸ 의도적 보류(사용자 결정)

| 축 | 1차 | 2차 | 남은 것 |
|---|---|---|---|
| Pillar 1 Context | ◐ | ● | `.dev/lessons.md`를 계획 단계가 안 읽음 (N-2) |
| Pillar 2 Validation | ◐ | ◐ | Layer 1 ●, self-correction ●. 독립 리뷰/모델 분리 ⏸, LogQL ⏸, 시각 ⏸ |
| Pillar 3 Tooling | ◐ | ● | `/review`·`/retro`가 수동 호출 — `--review` ⏸와 묶임 |
| Pillar 4 Codebases | ✗ | ◐ | 스택 오염 해소 ●, 로깅 ●, Golden Rules ●. 새 오염: 이 문서가 `docs/`에 있었음 (N-1) |
| Pillar 5 Compound | ◐ | ◐ | 그래프 간선 2개 누락 (N-2, N-3). origin 미push |
| §2 구조 | ◐ | ◐ | 권한 경계: deny만 있고 allow 없음 (N-4) |
| §3 맥락 | ✗ | ● | paths 조건부 로딩 없음 (N-5) |
| §4 계획 | ● | ● | — |
| §5 실행 | ◐ | ● | Ralph ●. Auto Research ✗ (필요 없음) |
| §6 검증 | ✗ | ◐ | 안전장치: gate ● dry-run ● worktree ⏸ |
| §7 개선 | ✗ | ● | retro + 승격 + 제거 제안 전부 있음. 실전 0회라 미검증 |

### 1차 수정 중 확인된 것

- AC 독립 게이트: `execute.py` `_execute_single_step` — `ac`를 호출 전 step dict에서 읽어 세션의 index.json 조작에 면역. 불일치 시 `verdict_mismatch` 이벤트. `TestVerdict` 7건.
- 선택 주입: `ALWAYS_DOCS` + `step.docs`. `TestLoadGuardrails` 8건.
- hook: stdin+jq, deny JSON. `test_hooks.py`에서 차단/허용 모두 검증.
- 그래프 간선: execute.py→GOLDEN_RULES, review→GOLDEN_RULES, retro→lessons→GOLDEN_RULES, harness→review→retro.

### 새로 발견한 것 (전부 2차에서 수정)

| # | 발견 | 왜 문제인가 | 수정 |
|---|------|-----------|------|
| N-1 | 이 감사문서가 `docs/`에 있었다 | clone 모델에서 `docs/`는 제품의 것. `/harness` A절이 읽으면 "P0 가드 무효" 같은 **고쳐진 과거**를 현재로 오인. Pillar 4 오염 + Pillar 1 거짓 신호 | `.dev/HARNESS_AUDIT.md`로 이동 |
| N-2 | `/retro`가 쓴 `lessons.md`를 아무도 안 읽음 | lessons → 다음 phase 설계로 가는 간선이 없으면 §7 "3번 반복"은 카운트만 되고 예방이 안 됨 | `harness.md` A절에 lessons.md 읽기 추가 |
| N-3 | `/review` 결과가 휘발 | "이전 리뷰에서도 같은 위반?"을 판단할 기록이 없음 | `.dev/reviews/{날짜}-{브랜치}.md`에 저장, `/retro` 입력에 추가 |
| N-4 | permissions에 deny 4개뿐 | 인터랙티브 세션에서 안전 커맨드마다 프롬프트 = friction. §2 권한 경계는 allow+deny | `settings.json` allow 7개 (npm run, npx, pytest, git status/diff/log/branch) |
| N-5 | `.claude/rules/` paths 조건부 로딩 없음 | `execute.py` 경로는 `docs` 선언으로 풀리지만 인터랙티브에서 UI 파일 만질 때 UI_GUIDE가 자동으로 안 뜸 (§3b) | `.claude/rules/ui.md` — `src/components/**`, `src/app/**/*.tsx` 건드릴 때만 로드 |

### 다음 라운드

여전히 ⏸: `--review` 독립 리뷰 세션/모델 분리, worktree, LogQL Layer 2, MCP, 시각 검증.

**1순위는 `--review`.** phase가 끝난 뒤 사람이 `/review`·`/retro`를 기억해서 쳐야 하는 것이 남은 가장 큰 수동 병목(Pillar 3)이고, 이걸 `execute.py --review`(별도 `claude -p`, 가능하면 다른 모델)로 codify하면 Pillar 2의 모델 분리(§6.1)까지 같이 풀린다. 단, **첫 phase를 한 번 실전으로 돌린 뒤** 결정한다 — worktree와 같은 이유.

---

## 요약

한 줄 진단: **이 리포에는 정체가 둘 섞여 있고(하네스 자체 = Python, 배포할 템플릿 = Next.js), 그 혼선이 5개 필러 전부에 그림자를 드리운다.** 그리고 "있다고 믿고 있지만 실제로는 동작하지 않는" 안전장치가 셋 있다.

가장 잘 되어 있는 것은 **§4 계획**(`harness.md`의 논의 단계 + step 설계 원칙 7종)과 **self-correction loop**(`execute.py`의 에러 되먹임)다.
가장 크게 비어 있는 것은 **Pillar 2의 독립 검증 게이트**다 — 판정 주체가 작업 주체와 같다.

| 축 | 상태 |
|---|---|
| Pillar 1 Context Engineering | ◐ |
| Pillar 2 Agentic Validation | ◐ (핵심 결함) |
| Pillar 3 Agentic Tooling | ◐ |
| Pillar 4 Agentic Codebases | ✗ |
| Pillar 5 Compound Engineering | ◐ |
| §2 구조 | ◐ |
| §3 맥락 | ✗ |
| §4 계획 | ● |
| §5 실행 | ◐ |
| §6 검증 | ✗ |
| §7 개선 | ✗ |

---

## 현재 자산 인벤토리

| 경로 | 줄수 | 실체 |
|------|------|------|
| `scripts/execute.py` | 418 | Ralph 루프 구현체 (`StepExecutor`). 순차 실행 · 3회 재시도 · 에러 피드백 · 가드레일 주입 · 2단계 커밋 |
| `scripts/test_execute.py` | 559 | 위의 pytest 스위트 (12개 테스트 클래스) |
| `.claude/commands/harness.md` | 152 | 탐색 → 논의 → step 설계 → 파일 생성 → 실행 워크플로우 명세 |
| `.claude/commands/review.md` | 28 | 5항목 리뷰 체크리스트 |
| `.claude/settings.json` | 26 | hook 2개 (Stop, PreToolUse[Bash]) |
| `docs/{PRD,ARCHITECTURE,ADR,UI_GUIDE}.md` | 22~77 | **전부 `{플레이스홀더}`** |
| `CLAUDE.md` | ~30 | **전부 `{플레이스홀더}`**, Next.js/TS/npm 전제 |

**없는 것**: `src/` `tests/` `.dev/` `out/` `templates/` `phases/` `package.json`
`.claude/agents/` `.claude/skills/` `.claude/hooks/` `settings.json:permissions` MCP

---

## P0 — "있다고 믿지만 동작하지 않는" 것 3종

이것들을 먼저 다뤄야 하는 이유: 이 항목들은 *비어 있는* 게 아니라 *거짓 신호를 주는* 상태다.
빈 칸은 채우면 되지만, 거짓 신호는 그 위에 쌓은 판단을 전부 오염시킨다.

### P0-1. PreToolUse 가드가 아무것도 차단하지 못한다

`.claude/settings.json:20`

```bash
if echo "$CLAUDE_TOOL_INPUT" | grep -qE 'rm\s+-rf|git\s+push\s+--force|...'; then
```

Claude Code hook은 입력을 **stdin에 JSON으로** 전달한다. `$CLAUDE_TOOL_INPUT`은 존재하지 않는
환경변수이므로 빈 문자열이 grep으로 흘러가고, 매칭 실패 → `exit 0` → **항상 통과**한다.

증거: 같은 리포의 `b196d57:scripts/hooks/dangerous-cmd-guard.sh`가 올바른 형태로 구현되어 있다.

```bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
# ... 매칭 시 {"hookSpecificOutput": {"permissionDecision": "deny", ...}} 출력
```

현재 인라인 버전은 그 구현에서 퇴화한 상태다.

> **재현 절차**: hook 커맨드를 `INPUT=$(cat); echo "$INPUT" > /tmp/hookdump.json; exit 0`으로
> 임시 교체하고 Bash 도구를 1회 실행한 뒤 `/tmp/hookdump.json`을 열어본다.
> 파일에 JSON이 들어 있으면 stdin 방식이 맞고, 현재 가드는 무효다.

### P0-2. Stop hook이 이 리포에서 매번 실패한다 — **확인됨**

`.claude/settings.json:9` → `npm run lint && npm run build && npm run test`

이 리포에 `package.json`이 없다. 실제 코드는 Python + pytest다. 실행 결과:

```
npm error code ENOENT
npm error path /Users/cody/Desktop/cody-harnesspr/package.json
npm error enoent Could not read package.json
```

프레임워크 템플릿이라면 이 hook은 *다운스트림 제품용*인데 *프레임워크 리포 자신*에 활성화되어 있다.

### P0-3. 자율 루프가 권한 경계 없이 메인 워크트리에서 돈다

세 가지가 겹친다:

| 요소 | 위치 | 문제 |
|---|---|---|
| 권한 스킵 | `execute.py:239` | `claude -p --dangerously-skip-permissions` |
| 권한 목록 부재 | `.claude/settings.json` | `permissions` 블록 자체가 없음 (allow/deny 없음) |
| 격리 부재 | `execute.py:113` `_checkout_branch()` | 브랜치만 팔 뿐 **worktree 격리 없음**. 사용자 작업 트리에서 직접 실행 |

Harness §6.4 안전장치 3종 대비: worktree ✗ / runtime gate △(P0-1로 고장) / dry-run ✗ → **실질 0개**.

---

## Pillar 1 — Context Engineering

| 항목 | 상태 | 근거 |
|------|------|------|
| second brain 골격 (PRD/ARCH/ADR/UI) | ◐ | `docs/` 4종 존재, 내용 100% 플레이스홀더 |
| CLAUDE.md = 진입점 + `@` 참조 | ✗ | 평면 파일. `@docs/...` 참조 없음 |
| ADR = 결정당 1파일 (`decisions/001-*.md`) | ✗ | 단일 `ADR.md`에 빈 슬롯 3개 |
| Folder-level CLAUDE.md / paths 조건부 로딩 | ✗ | 없음 |
| 컨텍스트 선택 주입 | ✗ | 아래 참조 |

### 핵심 문제 — 컨텍스트가 "선택"이 아니라 "전량 주입"이다

`execute.py:177-186 _load_guardrails()`는 CLAUDE.md + `docs/*.md` **전부**를 매 step 프롬프트에
무조건 concat한다.

```python
docs_dir = ROOT / "docs"
if docs_dir.is_dir():
    for doc in sorted(docs_dir.glob("*.md")):
        sections.append(f"## {doc.stem}\n\n{doc.read_text()}")
```

Harness §3의 "CLAUDE.md는 가볍게, 무거운 건 references/로 분리해 필요할 때 꺼내"의 정확한 반대다.
지금은 플레이스홀더라 가볍지만, 실제 제품에서 4개 문서가 채워지면
백엔드 step 프롬프트에도 UI_GUIDE.md 전문(77줄, Tailwind 안티패턴 표 포함)이 매번 들어간다.

게다가 `harness.md:91-99` step 템플릿에는 이미 **"읽어야 할 파일"** 섹션이 있다.
step이 필요한 문서를 스스로 선언하는 구조가 이미 존재하는데 executor가 그걸 무시하고 전량 주입한다.
중복이자 모순이다.

### 플레이스홀더의 이중성

프레임워크 템플릿에서 플레이스홀더는 버그가 아니라 자산이다. 문제는 *표시가 없다는 것*이다.
전량 주입과 결합하면 에이전트는 `{프레임워크 (예: Next.js 15)}`를 **규칙으로 받아들인다**.
채워지지 않은 문서는 컨텍스트가 아니라 노이즈다.

### 채울 작업

1. `docs/*` 각 파일 최상단에 배너: `> ⚠ TEMPLATE — 채우기 전까지 이 문서의 내용은 사실이 아니다`
2. `_load_guardrails()` → "CLAUDE.md는 항상 + step이 선언한 문서만". step index.json에 `docs: [...]` 필드 추가
3. `docs/ADR.md` → `docs/decisions/NNN-*.md` 분할, `ADR.md`는 인덱스만
4. CLAUDE.md를 200줄 이내 진입점으로 재작성, 무거운 내용은 `docs/references/`로

---

## Pillar 2 — Agentic Validation

| 항목 | 상태 | 근거 |
|------|------|------|
| Layer 1: AC를 실행 가능한 커맨드로 강제 | ◐ | `harness.md:25` 설계 원칙 5 — 규약은 있으나 실행 보장 없음 |
| self-correction loop | ● | `execute.py:299-360` 3회 재시도 + 이전 에러를 다음 프롬프트에 주입 |
| **독립 검증 게이트** | ✗ | 아래 참조 |
| Layer 2: 런타임 상태 검증 (LogQL 등) | ✗ | 구조화 로그 규약 자체가 없음 |
| 검증/구현 모델 분리 (§6.1) | ✗ | 동일 세션이 구현·검증 겸함 |
| 시각 검증 (§6.3) | ✗ | UI_GUIDE에 안티패턴 표가 있으나 검사 수단 없음 |

### 잘 되어 있는 것

`_build_preamble()`의 `retry_section`이 이전 실패 에러를 다음 시도 프롬프트에 그대로 되먹인다.

```python
retry_section = (
    f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
    f"{prev_error}\n\n---\n\n"
)
```

스펙이 말하는 self-correction loop의 정직한 구현이고, 이 리포에서 가장 잘 만들어진 부분이다.

### 핵심 문제 — 판사가 피고다

step의 통과/실패 판정 주체가 **작업을 수행한 그 Claude 세션 본인**이다.
`execute.py:312-313`은 세션이 끝난 뒤 `index.json`의 `status` 필드를 **읽기만** 한다.

```python
index = self._read_json(self._index_file)
status = next((s.get("status", "pending") for s in index["steps"] if s["step"] == step_num), "pending")
```

`_invoke_claude()`는 stdout을 `step{N}-output.json`에 덤프할 뿐 내용을 검사하지 않는다.
따라서 세션이 AC 커맨드를 **한 번도 실행하지 않고** `"completed"`라고 써도 하네스는 통과로 본다.
재시도 3회, 에러 피드백, 자동 커밋 — 이 파이프라인 전체가 **자기 신고** 위에 얹혀 있다.

Layer 1을 "충족"이라 부를 수 없는 이유가 여기다. AC를 실행 가능한 커맨드로 적게 강제하는 *규약*은
있지만, 그 커맨드가 실제로 실행되었는지 확인하는 *메커니즘*이 없다.

### 채울 작업

1. **AC 독립 실행** (로드맵 1순위): step index.json에 `ac: ["pytest -q", "ruff check"]` 배열을 선언하게 하고,
   세션 종료 후 executor가 직접 `subprocess`로 실행해 exit code로 판정한다.
   세션의 자기 신고는 보조 신호로 강등한다 (불일치 시 executor 판정 우선 + 로그 기록).
2. **독립 리뷰 세션**: AC 통과 후 별도 `claude -p`로 `/review`를 돌려 아키텍처 준수를 2차 판정.
   여기서 모델을 바꾸면(codex 등) Harness §6.1까지 동시 충족된다.
3. Layer 2 (LogQL)는 **보류**. 아래 "지금 하지 말 것" 참조.

---

## Pillar 3 — Agentic Tooling

| 항목 | 상태 | 근거 |
|------|------|------|
| Slash command | ● | `/harness`, `/review` — 커밋되어 있음 |
| CLI | ◐ | `execute.py <phase> [--push]` — 플래그 2개뿐 |
| MCP / subagent 정의 / skills | ✗ | `.claude/agents/`, `.claude/skills/` 없음 |

### 핵심 문제 — 남은 friction이 자동화되지 않고 "문서로 박제"되어 있다

`harness.md:148-151` 에러 복구 절차:

> **error 발생 시**: `phases/{task-name}/index.json`에서 해당 step의 `status`를 `"pending"`으로
> 바꾸고 `error_message`를 삭제한 뒤 재실행한다.

이건 **사람이 JSON을 손으로 편집하라는 지시**다. Pillar 3가 없애야 할 바로 그 병목을,
없애는 대신 매뉴얼로 적어둔 셈이다.

판단 기준은 명확하다 — **사람이 반복하는 절차가 문서에 적혀 있으면 그건 CLI 플래그가 되어야 한다.**

같은 성격의 미자동화:

- `phases/index.json`, `phases/{task}/index.json`, `step{N}.md` 생성이 전부 LLM 수작업 (`harness.md` D절)
- 진행 상황을 보려면 JSON을 직접 열어야 한다 (상태 조회 수단 없음)

### 채울 작업

1. `execute.py --retry <N>` / `--reset <N>` / `--status` — 위 매뉴얼 절차를 플래그로 codify
2. `--scaffold <task-name> --steps a,b,c` — phases 골격 생성
3. `.claude/agents/`에 검증 전용 서브에이전트 정의 (Pillar 2-2와 연결)

---

## Pillar 4 — Agentic Codebases

| 항목 | 상태 | 근거 |
|------|------|------|
| Pattern Contamination 제거 | ✗ | 아래 참조 |
| Structural Consistency | ◐ | ARCHITECTURE.md에 형태는 있으나 플레이스홀더 |
| Agent-Specific Logging | ✗ | `execute.py` 전반이 사람용 `print()` |
| Golden Rules | ✗ | 파일 없음. CLAUDE.md의 CRITICAL 3줄이 전부이며 그마저 플레이스홀더 |

### 핵심 문제 — 오염이 이미 존재한다. 그것도 하네스 레이어에

한 리포 안에서 두 스택이 경쟁한다.

| Next.js / npm 진영 | Python / pytest 진영 |
|---|---|
| `CLAUDE.md` 명령어 4종 (`npm run dev/build/lint/test`) | `scripts/execute.py` (418줄) |
| `.claude/settings.json` Stop hook | `scripts/test_execute.py` (559줄, pytest) |
| `docs/ARCHITECTURE.md` (`src/app`, `components/`) | |
| `docs/UI_GUIDE.md` (Tailwind 클래스) | |

에이전트는 `npm run test`를 **규칙으로** 받고, 실제로는 `pytest`를 돌려야 한다.
스펙이 말하는 "competing patterns"의 교과서적 사례이며 `relentless cleanup`의 첫 대상이다.

기타 오염:

- `.gitignore:9` `phases/**/phase*-output.json` — executor는 `step{N}-output.json`만 쓴다. 과거 설계의 데드 패턴
- `step{N}-output.json`은 stdout **통째 덤프**라 기계 판독이 불가능하다.
  `claude --output-format json`으로 이미 JSON을 받고 있는데(`execute.py:239`) 파싱 없이 문자열로 저장한다

### 채울 작업

1. **`templates/` 분리** (로드맵 2순위) — 배포할 제품용 자산(Next.js CLAUDE.md, docs 4종, npm Stop hook)을
   `templates/`로 옮기고, 리포 루트에는 **프레임워크 자신의 규칙**(Python/pytest/ruff)만 남긴다.
   이 하나로 P0-2와 Pillar 4 오염이 동시에 해소된다.
2. `docs/GOLDEN_RULES.md` — 프레임워크용 / 템플릿용 각각
3. `.dev/runs/{phase}/events.jsonl` — executor 이벤트를 JSON line으로 기록.
   예: `{"ts":..., "phase":..., "step":1, "event":"step_completed", "attempt":2, "elapsed_ms":..., "ac_exit_code":0}`
   Pillar 4 로깅 요구를 충족하면서 Pillar 2 Layer 2의 기반이 된다
4. `.gitignore`의 죽은 glob 제거

---

## Pillar 5 — Compound Engineering

| 항목 | 상태 | 근거 |
|------|------|------|
| Shared Skills가 커밋되어 있음 | ● | `.claude/commands/` |
| 자산이 clone으로 전파 중 | ● | 이 리포 자체가 그 증거 |
| upstream 축적 경로 | ✗ | `origin`이 원저자 리포. 개선분을 쌓을 곳이 없음 |
| 학습 축적 장치 | ✗ | `.dev/` 없음, 회고 커맨드 없음 |
| 자산 간 상호참조 그래프 | ✗ | 아래 참조 |

### 핵심 문제 — 자산들이 서로를 모른다

스펙이 요구하는 건 graph다: Skill이 MCP를 호출하고, MCP가 Golden Rules를 검사하고,
Rules가 CLAUDE.md 템플릿을 가리킨다. 현재는 간선이 하나도 없다.

- `review.md`가 검사하는 대상이 GOLDEN_RULES가 아니라 "CLAUDE.md의 CRITICAL 규칙"이라는 추상 참조다
- `harness.md`가 step 완료 후 `/review`를 호출하지 않는다 — 두 커맨드가 서로를 모른다
- `execute.py`가 `/review`의 존재를 모른다

"같은 실수 3번 → Rule에 박제"(§7)를 하려면 실수가 **기록되어야** 하는데,
현재 실패 기록은 `index.json`의 `error_message` 한 줄이고 재시도 시 덮어써진다(`execute.py:344`).

### 채울 작업

1. 자기 fork를 `origin`으로, 원저자 리포를 `upstream`으로 재배선 — 개선분 축적 경로 확보
2. `.dev/lessons.md` + `/retro` 커맨드 — phase 종료 시 실패 패턴 누적
3. `review.md`가 `docs/GOLDEN_RULES.md`를 명시적으로 읽도록 재작성 — 그래프의 첫 간선

---

## Harness 6축 — 위와 겹치지 않는 부분만

| 축 | 상태 | 고유 갭 |
|---|---|---|
| §2 구조 | ◐ | `src/ tests/ .dev/ out/` 없음. **경계 3종 중 권한 경계가 통째로 부재** (P0-3) |
| §3 맥락 | ✗ | = Pillar 1 |
| §4 계획 | ● | `harness.md` B절 "논의"가 계획 단계 되묻기를 강제 — **가장 잘 충족된 축** |
| §5 실행 | ◐ | Ralph 루프 ● (`execute.py`) / Auto Research(`program.md`) ✗ |
| §6 검증 | ✗ | = Pillar 2 + 안전장치 3종 실질 0개 (P0-3) |
| §7 개선 | ✗ | = Pillar 5. 추가로 "안 쓰는 건 치우기" 위반 — UI_GUIDE.md는 Next.js 전용인데 루트 `docs/`에 있어 매 step 주입된다 |

---

## 로드맵

| # | 작업 | 해소하는 것 | 규모 |
|---|------|-----------|------|
| 1 | **AC 독립 실행 게이트** — executor가 AC를 직접 돌려 판정 | Pillar 2 핵심 / "판사=피고" | 중 |
| 2 | **`templates/` 분리** — 프레임워크 규칙 ↔ 제품 템플릿 | P0-2, Pillar 4 오염, §7 | 중 |
| 3 | **hook 복구** — stdin+jq 방식 재작성 + `permissions` 블록 추가 | P0-1, P0-3(부분), §2 권한 경계 | 소 |
| 4 | **컨텍스트 선택 주입** — step이 선언한 문서만 로드 | Pillar 1 핵심, §3 | 소 |
| 5 | **friction codify** — `--retry` / `--reset` / `--status` | Pillar 3 | 소 |
| 6 | **구조화 이벤트 로그** — `.dev/runs/*.jsonl` | Pillar 4 로깅, Pillar 2 Layer 2 기반 | 소 |
| 7 | **worktree 격리 + `--dry-run`** | P0-3, §6 안전장치 | 중 |
| 8 | **GOLDEN_RULES + 자산 상호참조** | Pillar 4, Pillar 5 그래프 | 소 |

### 지금 하지 말 것

§7 "좋은 하네스는 점점 단순해지는 것"에 따라 아래는 **의도적으로 비워둔다**.
체크박스를 다 채우는 것이 목표가 아니다.

| 항목 | 비워두는 이유 |
|---|---|
| **LogQL Layer 2** | 실행 중인 제품이 없다. 검증할 런타임 상태 자체가 존재하지 않는다. 로드맵 6번으로 기반만 깔고 대기 |
| **MCP 서버** | 현재 friction 중 MCP가 아니면 못 푸는 게 없다. CLI 플래그(5번)로 충분 |
| **시각 검증 / Browser Agent** | UI가 없다. 템플릿이 배포된 제품 쪽 과제 |
| **docs 플레이스홀더 채우기** | 프레임워크 템플릿에서는 플레이스홀더가 정상. 배너(Pillar 1-1)만 붙이면 된다 |
