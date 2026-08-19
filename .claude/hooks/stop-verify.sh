#!/bin/bash
# Stop hook — 세션 종료 전 제품 검증 커맨드 실행.
# package.json이 없으면(프레임워크 개발 중, 또는 npm 외 스택) 아무것도 하지 않는다.
# 실패 시 exit 2 → Claude가 멈추지 못하고 수정을 계속한다. stop_hook_active로 무한루프를 막는다.

INPUT=$(cat)
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active // false')" = "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ -f package.json ] || exit 0

OUT=$(npm run lint 2>&1 && npm run build 2>&1 && npm run test 2>&1) && exit 0
echo "Stop hook 검증 실패 — 아래 에러를 수정한 뒤 다시 종료하라:" >&2
echo "$OUT" | tail -40 >&2
exit 2
