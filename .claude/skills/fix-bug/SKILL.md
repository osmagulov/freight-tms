---
name: fix-bug
description: Investigate and fix a bug. Use when user reports an error, unexpected behavior, or asks to debug something.
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - Bash
---

Fix the bug described in $ARGUMENTS.

## Process

1. **Reproduce**: Understand the bug — what's expected vs what happens
2. **Locate**: Search the codebase for the relevant code
   - Use error messages, stack traces, file names as clues
   - Trace the data flow from input to the point of failure
3. **Root cause**: Find WHY it breaks, not just WHERE
4. **Fix**: Make the minimal change to fix the root cause
5. **Verify**: Run tests or describe how to verify the fix
6. **Side effects**: Check if the fix could break anything else

## Rules
- Fix the ROOT CAUSE, not the symptom
- Make the SMALLEST possible change
- Don't refactor surrounding code — stay focused on the bug
- If the fix is risky, explain the trade-offs
- If you can't reproduce or find the bug, say so — don't guess
