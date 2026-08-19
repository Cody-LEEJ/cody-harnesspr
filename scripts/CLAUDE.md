# scripts/ — 하네스 실행기

이 폴더는 **프레임워크 자신**의 코드다. 루트 `CLAUDE.md`·`docs/`는 이 리포를 clone해서 만드는 *제품*의 규칙이며 이 폴더에는 적용되지 않는다 (npm 명령어 등).

## 규칙
- Python 3.9+ 표준 라이브러리만. 외부 패키지 추가 금지.
- 테스트: `python3 -m pytest scripts/ -q` — 동작을 바꾸면 테스트를 먼저 바꾼다.
- `execute.py`는 사람용 출력은 `print`, 기계용 기록은 `_emit()`(`.dev/runs/{phase}/events.jsonl`)로 분리한다.
- step 판정은 executor가 한다 (`ac` 독립 실행). 세션 자기 신고를 판정 근거로 되돌리지 마라.
- hook 스크립트(`.claude/hooks/`)는 stdin JSON 규약을 따른다. 테스트는 `test_hooks.py`.
