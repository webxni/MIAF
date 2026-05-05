# skills

Local installable skills (Phase 9). Each skill lives in its own subdirectory:

```
skills/<skill_name>/
  SKILL.yaml
  README.md
  handler.py
```

Built-in skills may default to enabled. Third-party skills are disabled by default and require explicit enable. Skills cannot access secrets or execute shell commands.

Empty in Phase 0.
