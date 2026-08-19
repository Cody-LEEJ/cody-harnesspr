> ⚠ TEMPLATE — 채우기 전까지 이 문서의 내용은 사실이 아니다. 채운 뒤 이 줄을 지워라.

# 프로젝트: {프로젝트명}

## 기술 스택
- {프레임워크 (예: Next.js 15)}
- {언어 (예: TypeScript strict mode)}
- {스타일링 (예: Tailwind CSS)}

## 아키텍처 규칙
- 절대 규칙은 `docs/GOLDEN_RULES.md`에 있다 (execute.py와 /review가 자동으로 읽는다)
- {일반 규칙 (예: 컴포넌트는 components/ 폴더에, 타입은 types/ 폴더에 분리)}

## 문서
- `docs/PRD.md` — 무엇을 왜 만드는가
- `docs/ARCHITECTURE.md` — 디렉토리 구조와 데이터 흐름
- `docs/ADR.md` — 기술 결정 인덱스 (개별 결정은 `docs/decisions/`)
- `docs/UI_GUIDE.md` — UI 규칙 (UI step에서만 필요)
- `HARNESS.md` — 하네스 사용법. 프레임워크 문서이며 제품 규칙이 아니다 (step `docs`에 넣지 않는다)

step별로 필요한 문서만 `phases/{task}/index.json`의 `docs` 필드에 선언한다. 전부 넣지 않는다.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 명령어
npm run dev      # 개발 서버
npm run build    # 프로덕션 빌드
npm run lint     # ESLint
npm run test     # 테스트
