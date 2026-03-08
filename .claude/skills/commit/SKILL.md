---
name: commit
description: Create a git commit with a well-written message based on staged/unstaged changes
disable-model-invocation: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

Create a git commit for the current changes.

## Steps

1. Run `git status` to see all changes (staged and unstaged)
2. Run `git diff` and `git diff --staged` to understand what changed
3. Run `git log --oneline -5` to match the project's commit message style
4. Stage relevant files (prefer specific files over `git add .`)
5. Never stage `.env`, credentials, or secret files
6. Write a concise commit message:
   - First line: imperative mood, under 72 chars, describes the "why"
   - Body (if needed): explain context
   - End with: `Co-Authored-By: Claude <noreply@anthropic.com>`
7. Create the commit
8. Run `git status` to verify success

## Rules
- NEVER amend existing commits unless explicitly asked
- NEVER force push
- NEVER skip pre-commit hooks
- If a hook fails, fix the issue and create a NEW commit
