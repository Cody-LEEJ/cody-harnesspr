phase 하나가 끝난 뒤(완료든 실패든) 회고를 기록하라. 목적은 **같은 실수를 세 번 하지 않는 것**이다.

## 입력

1. `phases/{task}/index.json` — 각 step의 status, error_message, blocked_reason, summary
2. `.dev/runs/{task}/events.jsonl` — executor가 남긴 기계 기록. 특히:
   - `step_retry` / `step_failed` 의 `error` — 무엇이 실패했는지
   - `verdict_mismatch` — 세션이 통과라고 했지만 AC가 실패한 경우 (또는 그 반대)
   - `ac_result` 의 `exit_code` — 어떤 AC 커맨드가 자주 깨지는지
   - `claude_done` 의 `num_turns`, `total_cost_usd` — 비정상적으로 비싼 step
3. `.dev/reviews/*.md` — `/review`가 남긴 결과 표. 어떤 Golden Rule·아키텍처 위반이 반복되는지
4. `.dev/lessons.md` — 이전 phase들의 기록

## 할 일

1. 위 입력에서 **반복 가능한 패턴**만 추린다. 일회성 오타는 적지 않는다.
2. `.dev/lessons.md`에 phase 단위로 추가한다. 형식:

   ```
   ## {YYYY-MM-DD} {task}
   - [패턴] {무엇이 반복됐는가 — step 번호, 횟수}
     → [대응] {다음에 step 설계/프롬프트/AC를 어떻게 바꾸면 막히는가}
   ```

3. lessons.md 전체를 훑어 **같은 패턴이 3개 이상의 phase에서 나타났으면** `docs/GOLDEN_RULES.md`의 "반복 실수에서 승격된 규칙"에 올릴 문장을 제안한다. 형식: "X를 하지 마라. 이유: Y". 사용자 승인 후에 GOLDEN_RULES.md를 수정한다.
4. 반대로, GOLDEN_RULES 중 이번 phase에서 한 번도 관련이 없었고 3개 phase 연속 그런 규칙이 있으면 제거를 제안한다. 좋은 하네스는 점점 단순해진다.

## 하지 말 것

- events.jsonl을 통째로 요약하지 마라. 패턴만.
- 사용자 승인 없이 GOLDEN_RULES.md를 고치지 마라.
