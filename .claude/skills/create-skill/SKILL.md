---
name: create-skill
description: Create a new Claude Code skill. Use when user asks to make, add, or generate a new slash command or skill.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebSearch
---

Create a new Claude Code skill based on $ARGUMENTS.

## Process

1. **Understand the request**: What should the skill do? When should it trigger?
2. **Choose a name**: short, lowercase, kebab-case (e.g., `deploy-app`, `generate-docs`)
3. **Create the directory and SKILL.md file**:
   - Path: `~/.claude/skills/<skill-name>/SKILL.md`
4. **Write the SKILL.md** following the structure below
5. **Verify** the file was created

## SKILL.md Template

```yaml
---
name: <skill-name>
description: <One clear sentence explaining what it does and WHEN to use it>
disable-model-invocation: true  # true = only user can invoke via /command
# user-invocable: false         # uncomment if only Claude should use it automatically
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
---

<Clear instructions for Claude on how to execute this skill>

Use $ARGUMENTS for user input. Use $0, $1, $2 for positional args.
```

## Frontmatter Options

| Field | Description |
|-------|-------------|
| `name` | Slash command name (`/name`) |
| `description` | When Claude should use this skill (critical for auto-invocation) |
| `disable-model-invocation: true` | Only user can trigger via `/command` |
| `user-invocable: false` | Only Claude triggers it automatically |
| `allowed-tools` | Tools the skill can use: Read, Edit, Write, Bash, Grep, Glob, WebSearch, WebFetch |
| `context: fork` | Run in isolated sub-agent |
| `agent` | Sub-agent type: `Explore`, `Plan`, `general-purpose` |

## Variables

| Variable | Value |
|----------|-------|
| `$ARGUMENTS` | Everything after the command |
| `$0`, `$1`, `$2` | Positional arguments |
| `${CLAUDE_SESSION_ID}` | Current session ID |

## Rules
- Keep SKILL.md under 500 lines
- Write a clear, specific `description` — Claude uses it to decide when to apply the skill
- Use additional files (examples.md, templates/) for large reference material
- Always verify the skill file exists after creating it
