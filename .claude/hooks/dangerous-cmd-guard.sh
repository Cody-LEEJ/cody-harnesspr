#!/bin/bash
# Dangerous Command Guard — PreToolUse[Bash]
# rm -rf, git push --force, git reset --hard, DROP TABLE 등 위험 명령어 차단.
# Claude Code hook은 입력을 stdin JSON으로 전달한다. 차단은 permissionDecision: deny JSON으로 한다.
# permission mode와 무관하게 실행되므로 execute.py(--dangerously-skip-permissions) 경로의 1차 방어선이다.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

if echo "$COMMAND" | grep -qE 'rm\s+-rf|git\s+push\s+(-f|--force)|git\s+reset\s+--hard|DROP\s+TABLE'; then
  cat << 'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "위험한 명령어가 감지되었습니다. rm -rf, git push --force, git reset --hard, DROP TABLE은 실행할 수 없습니다."
  }
}
JSON
fi

exit 0
