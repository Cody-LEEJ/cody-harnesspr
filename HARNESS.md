# HARNESS.md — 이 리포는 무엇이고, 어떻게 쓰는가

이 문서는 **사람이 읽는 입문서**다. 프레임워크 자체의 설명이며 제품 규칙이 아니다 (에이전트 프롬프트에 주입하지 않는다).
하네스가 왜 이렇게 생겼는지의 진단 기록은 [`.dev/HARNESS_AUDIT.md`](.dev/HARNESS_AUDIT.md).

---

## 1. 이게 뭔가 — 개발자가 아니어도 이해되는 설명

한 문장: **AI 개발자(Claude)를 고용해서 일을 시키는 "사무실"을 미리 세팅해 둔 것.**

AI는 똑똑하지만 출근 첫날의 신입과 같다. 회사 규칙도, 왜 이렇게 만들었는지도, 어디까지 건드려도 되는지도 모른다.
그래서 사람이 할 일은 코드를 쓰는 게 아니라 **사무실을 차려놓는 것**이다 — 사규, 자료실, 업무 매뉴얼, 안전장치, 그리고 작업반장.

### 사무실 구성도

| 폴더/파일 | 비유 | 실제로 하는 일 |
|---|---|---|
| `CLAUDE.md` | **사규** — 출근하면 제일 먼저 읽는 한 장 | 기술 스택, 실행 명령어, 절대 규칙, 문서 위치. AI가 매번 자동으로 읽는다 |
| `docs/` | **자료실** | 아래 5종. 제품이 "무엇을, 왜, 어떻게" 만드는지의 진실 |
| ├ `PRD.md` | 기획서 | 누구를 위해 무엇을 만드는가, 무엇은 안 만드는가 |
| ├ `ARCHITECTURE.md` | 설계도 | 폴더 구조, 데이터 흐름 — "결제 코드는 항상 여기" |
| ├ `ADR.md` + `decisions/` | 결정 회의록 | "왜 이 DB인가" 같은 결정 하나당 파일 하나. 되돌려도 지우지 않는다 |
| ├ `GOLDEN_RULES.md` | **절대 금지 목록** | 어떤 작업에서도 어기면 안 되는 3~5줄. 실행기·검수·회고가 전부 이 파일을 본다 |
| └ `UI_GUIDE.md` | 디자인 가이드 | 화면이 있을 때만. "AI가 만든 티 나는 디자인" 금지 목록 포함 |
| `.claude/commands/` | **업무 매뉴얼** | `/harness` 계획 세우기 · `/review` 검수 · `/retro` 회고. 사람이 슬래시 명령으로 부른다 |
| `.claude/rules/` | 구역별 안내판 | 특정 폴더(예: UI 파일)를 건드릴 때만 자동으로 붙는 규칙 |
| `.claude/hooks/` + `settings.json` | **안전장치** | 위험 명령(삭제·강제 push) 자동 차단, 작업 끝낼 때 테스트 강제, 허용/금지 명령 목록 |
| `scripts/execute.py` | **작업반장** | 작업 지시서를 한 장씩 AI에게 주고 → 끝나면 **반장이 직접 검사**하고 → 실패하면 에러를 보여주며 다시 시키고 → 3번 실패하면 멈추고 사람을 부른다 |
| `phases/` | 작업 지시서 묶음 | `/harness`가 만든다. task 하나 = 폴더 하나, step 하나 = 파일 하나 |
| `.dev/` | **작업 일지** | `runs/` 기계 기록(무슨 일이 언제 일어났나), `lessons.md` 회고(반복된 실수), `reviews/` 검수 결과 |

### 하루의 흐름

```
사람: 사규·자료실 채우기 (CLAUDE.md, docs/)
  │
  ▼
/harness ── AI가 자료실을 읽고, 모호한 걸 사람에게 되묻고, 작업 지시서(step)를 쪼개 제안
  │         사람이 승인하면 phases/에 지시서 생성
  ▼
execute.py ── 작업반장이 step을 한 장씩 AI에게 맡김
  │           ├ AI 작업 (hooks가 위험 명령 감시)
  │           ├ 반장이 검사 커맨드(AC)를 직접 실행 ─ 통과? ──▶ 커밋, 다음 step
  │           └ 실패 ──▶ 에러를 붙여 다시 시킴 (최대 3번) ──▶ 그래도 실패면 멈추고 사람 호출
  ▼
/review ── 전체 변경을 절대 규칙·설계도 기준으로 2차 검수
  ▼
/retro ── 반복된 실수를 lessons.md에 기록. 3번 반복되면 GOLDEN_RULES로 승격 제안
  │
  └──▶ 다음 phase의 /harness가 lessons.md를 읽고 같은 실수를 피하도록 설계
```

### 누가 뭘 하나

| 사람 | AI (Claude 세션) | 기계 (`execute.py`·hooks) |
|---|---|---|
| 기획·규칙·결정을 문서로 쓴다 | 문서를 읽고 모호한 점을 **질문**한다 | 문서를 프롬프트에 자동 주입한다 (필요한 것만) |
| step 초안을 승인/수정한다 | step을 쪼개 제안한다 | — |
| — | step 작업을 수행하고 AC를 스스로 돌려본다 | **AC를 독립 실행해 판정**한다 (AI의 "다 했어요"는 믿지 않는다) |
| 3번 실패·차단 시 원인을 고친다 | 실패 에러를 보고 고친다 | 에러를 다음 시도에 되먹이고, 커밋하고, 일지를 쓴다 |
| `/review` `/retro`를 실행한다 | 검수·회고를 수행한다 | 위험 명령을 차단하고, 종료 전 테스트를 강제한다 |
| 승격 규칙을 승인한다 | GOLDEN_RULES 승격/삭제를 **제안**한다 | — |

핵심 설계 원칙 하나만 기억하면 된다: **"판사와 피고는 다른 사람이어야 한다."** AI가 작업하고, 작업반장이 검사한다.

---

## 2. 서비스를 만들 때 순서

처음부터 첫 phase 실행까지. 각 단계 끝의 *건너뛰면* 은 생략했을 때 실제로 벌어지는 일이다.

### 0. 리포 준비

```bash
git clone <이 리포> my-service && cd my-service
git remote rename origin upstream          # 프레임워크 원본
git remote add origin <내 제품 리포>        # 내 작업이 쌓일 곳
```

- 스택이 npm이 아니면 `.claude/hooks/stop-verify.sh`의 `npm run lint && npm run build && npm run test` 줄을 자기 스택 커맨드로 바꾼다. `package.json`이 없으면 이 hook은 조용히 아무것도 안 한다.
- *건너뛰면*: 종료 전 검사가 없는 채로 돌아간다 — 깨진 코드로 세션이 끝날 수 있다.

### 1. 사규와 자료실 채우기 (순서대로)

| 순서 | 파일 | 채울 것 | 분량 감각 |
|---|---|---|---|
| 1 | `CLAUDE.md` | 스택, 실행 명령어 4개, 문서 목록 | 30줄 내외, 200줄 넘기지 않는다 |
| 2 | `docs/PRD.md` | 목표 한 줄, 사용자, 핵심 기능 3개, **안 만들 것** 3개 | 20줄 |
| 3 | `docs/ARCHITECTURE.md` | 폴더 구조("X는 항상 여기"), 데이터 흐름, 상태 관리 | 30줄 |
| 4 | `docs/decisions/001-*.md` … | 첫 결정들 — 프레임워크·DB·인증 등. 결정/이유/트레이드오프 셋 다 채운다 | 결정당 10줄 |
| 5 | `docs/ADR.md` | 위 결정들의 인덱스 표 | 표만 |
| 6 | `docs/GOLDEN_RULES.md` | 절대 규칙 **3~5줄**. "X를 하지 마라. 이유: Y" 형식 | 길면 아무도 안 읽는다 |
| 7 | `docs/UI_GUIDE.md` | 화면이 있을 때만. 없으면 파일을 지운다 | — |

각 문서를 채우면 맨 위 `⚠ TEMPLATE` 배너 줄을 **지운다**. 배너가 남아 있으면 `/harness`가 "아직 안 채워졌다"고 거부한다.

- *건너뛰면*: AI가 `{프레임워크 (예: Next.js 15)}` 같은 플레이스홀더를 규칙으로 받아들이거나, 아무 근거 없이 자기 취향대로 결정한다. 이 단계의 10분이 뒤의 검수 10번을 줄인다.

### 2. 계획 — `/harness`

Claude Code에서 `/harness`를 친다. 네 단계로 진행된다.

1. **탐색** — AI가 `docs/`와 `.dev/lessons.md`를 읽는다.
2. **논의** — 모호한 점을 AI가 묻는다. **여기서 답을 아끼지 마라.** 검수 횟수는 이 단계에서 결정된다.
3. **step 설계** — AI가 step 초안을 낸다. 확인할 것:
   - step 하나 = 모듈/레이어 하나인가
   - 모든 step에 `ac`(실행 가능한 검사 커맨드)가 있는가 — `npm test`, `pytest -q` 같은 것. "동작해야 한다"는 AC가 아니다
   - `docs`에 그 step이 진짜 필요한 문서만 선언됐는가 (백엔드 step에 UI_GUIDE 금지)
4. **파일 생성** — 승인하면 `phases/{task}/index.json` + `step{N}.md`가 만들어진다.

- *건너뛰면 (AC를 비우면)*: 작업반장이 검사할 게 없어 AI의 자기 신고로 판정한다 = 판사가 피고가 된다.

### 3. 실행 — `execute.py`

```bash
python3 scripts/execute.py {task} --dry-run   # 먼저: 어떤 문서가 주입되고 어떤 AC로 판정하는지 확인. AI/git 호출 없음
python3 scripts/execute.py {task}             # 실행
python3 scripts/execute.py {task} --push      # 실행 후 push까지
```

작업반장이 `feat-{task}` 브랜치를 만들고 step을 순서대로 돌린다. 화면에 `✓ Step N` 이 쌓이면 정상.

- *`--dry-run`을 건너뛰면*: 오타 난 문서 경로, AC 없는 step, 너무 큰 프롬프트를 실행 도중에 발견한다.

### 4. 막혔을 때

```bash
python3 scripts/execute.py {task} --status    # 어디서 멈췄는지
python3 scripts/execute.py {task} --retry N   # step N을 다시
```

| 화면 표시 | 뜻 | 할 일 |
|---|---|---|
| `✗ Step N ... failed after 3 attempts` | AI가 3번 시도했는데 AC가 계속 실패 | `error_message`(보통 AC 출력)를 읽는다. **step 설계가 원인이면** `step{N}.md`·`ac`를 고치고 `--retry N` |
| `⏸ Step N ... blocked` | API 키·인증·수동 설정처럼 사람만 할 수 있는 일 | `blocked_reason`대로 해결하고 `--retry N` |
| `! 판정 불일치` | AI는 "완료"라 했는데 AC는 실패 (또는 반대) | 작업반장 판정이 우선. 정보용 — 자주 뜨면 step 지시가 모호한 것 |

### 5. phase가 끝나면

1. `/review` — 전체 변경을 GOLDEN_RULES·ARCHITECTURE·ADR 기준으로 검수. 결과는 `.dev/reviews/`에 남는다.
2. `/retro` — `.dev/runs/{task}/events.jsonl`과 리뷰 기록에서 **반복된** 실패만 `.dev/lessons.md`에 적는다.
   - 같은 패턴이 3개 phase에서 나타나면 GOLDEN_RULES 승격을 제안한다 → 사람이 승인.
   - 반대로 3 phase 연속 한 번도 안 쓰인 규칙은 삭제를 제안한다.
3. push (`--push`를 안 썼다면 직접).

- *건너뛰면*: 같은 실수를 4번째도 한다. 하네스는 쓸수록 좋아져야 정상이고, 그 엔진이 이 두 명령이다.

### 6. 다음 phase

다시 `/harness`. 이번엔 AI가 `.dev/lessons.md`를 먼저 읽고 지난 실수를 step 주의사항·AC에 반영한다.

### 7. 주기적으로

- 안 쓰는 규칙·문서·커맨드는 지운다. **좋은 하네스는 점점 단순해진다.** 체크박스를 다 채우는 게 목표가 아니다.
- 같은 수작업을 3번 반복했으면 스크립트 플래그나 커맨드로 만든다. 같은 실수를 3번 했으면 규칙으로 박는다.

---

## 3. 알아둘 것

- **위험 명령 가드는 텍스트 패턴을 본다.** Bash 커맨드 문자열 안에 `rm -rf`, `git push --force`, `git reset --hard`, `DROP TABLE`이 *문서 내용으로라도* 들어가면 차단된다 (heredoc, 커밋 메시지 포함). 그런 내용은 Write 도구로 파일에 쓰고 `git commit -F`를 쓴다.
- `execute.py`는 `--dangerously-skip-permissions`로 AI를 돌린다. 그래서 hook이 1차 방어선이고, `settings.json`의 `deny`가 2차다. 둘 다 `.claude/`에 있으니 clone과 함께 따라간다.
- `.dev/runs/`는 git에 안 올라간다(기계 기록, 용량 큼). `.dev/lessons.md`와 `.dev/reviews/`는 올라간다(팀이 공유할 학습).
- 아직 일부러 안 만든 것: 독립 리뷰 세션(`--review`), worktree 격리, 런타임 로그 검증(LogQL), MCP, 시각 검증. 첫 phase를 실전으로 돌린 뒤 필요한 것부터 넣는다. 근거는 `.dev/HARNESS_AUDIT.md`.
