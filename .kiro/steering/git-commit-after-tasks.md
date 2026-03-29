---
inclusion: always
---

# Git Commits After Major Tasks

After completing each major task (top-level numbered task in tasks.md), run a `git add -A` and `git commit` with a concise message describing what was implemented.

Use this commit message format:
```
feat: <short description of the completed task>
```

Examples:
- `feat: implement data models and migrations`
- `feat: add Django admin registrations and generate_tokens action`
- `feat: add templates and responsive UI`

Do this automatically without asking the user — they have already requested this behaviour.
