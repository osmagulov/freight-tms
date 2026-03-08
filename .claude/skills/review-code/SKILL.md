---
name: review-code
description: Review code for bugs, security issues, and improvements. Use when the user asks to review, audit, or check code quality.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

Review the code in $ARGUMENTS (file path, directory, or current selection).

## Review Checklist

### 1. Bugs & Logic Errors
- Off-by-one errors, null/undefined access, race conditions
- Missing error handling, unhandled edge cases

### 2. Security (OWASP Top 10)
- SQL injection, XSS, command injection
- Hardcoded secrets, insecure auth, missing input validation
- Exposed API keys or tokens

### 3. Performance
- N+1 queries, unnecessary re-renders, memory leaks
- Missing pagination, unbounded loops

### 4. Code Quality
- Dead code, duplicated logic, overly complex functions
- Unclear naming, missing types

## Output Format

For each finding:
```
[SEVERITY] file:line — Description
  Suggestion: how to fix
```

Severity levels: CRITICAL > WARNING > INFO

End with a summary: total findings by severity, overall assessment.
