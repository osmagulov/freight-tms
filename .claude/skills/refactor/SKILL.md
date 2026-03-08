---
name: refactor
description: Refactor code to improve readability, reduce complexity, or modernize patterns. Use when user asks to refactor, clean up, simplify, or modernize code.
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - Bash
---

Refactor the code in $ARGUMENTS.

## Process

1. **Read and understand** the code first — never change what you don't understand
2. **Identify problems**: complexity, duplication, poor naming, outdated patterns
3. **Plan changes** before making them — explain what you'll do and why
4. **Make minimal changes** — only refactor what's needed, don't over-engineer
5. **Preserve behavior** — the code should work exactly the same after refactoring
6. **Verify** — if tests exist, run them after refactoring

## Refactoring Techniques
- Extract function (break large functions into smaller ones)
- Rename for clarity (variables, functions, classes)
- Remove dead code
- Simplify conditionals (early returns, guard clauses)
- Replace magic numbers with named constants
- Reduce nesting depth
- Use modern language features where appropriate

## Rules
- Do NOT add features — refactoring is about structure, not functionality
- Do NOT change public APIs unless explicitly asked
- Do NOT add comments to code you didn't change
- Keep the diff as small as possible
