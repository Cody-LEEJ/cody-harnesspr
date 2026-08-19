> ⚠ TEMPLATE — 채우기 전까지 이 문서의 내용은 사실이 아니다. 채운 뒤 이 줄을 지워라.

# Architecture Decision Records

## 철학
{프로젝트의 핵심 가치관 (예: MVP 속도 최우선. 외부 의존성 최소화. 작동하는 최소 구현을 선택.)}

## 결정 목록

결정 하나당 `docs/decisions/NNN-slug.md` 파일 하나. 이 표는 인덱스다.

| # | 결정 | 상태 | 파일 |
|---|------|------|------|
| 000 | (템플릿) | — | `decisions/000-template.md` |

## 작성 규칙

- 번호는 3자리, 순차 증가. 파일명은 `NNN-kebab-slug.md`.
- 결정/이유/트레이드오프 세 항목은 비우지 않는다. 트레이드오프가 없다면 결정이 아니다.
- 되돌린 결정은 지우지 않고 상태를 `superseded by NNN`으로 바꾼다.
- step이 특정 결정에 의존하면 `phases/{task}/index.json`의 `docs`에 그 파일만 선언한다 (ADR 전체가 아니라).
