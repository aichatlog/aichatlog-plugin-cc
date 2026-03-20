---
allowed-tools: Bash(python3:*)
description: Open the CC Obsidian Sync web management dashboard
---

## Your task

Run the following command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/aichatlog.py web --no-browser
```

Present the output to the user. You MUST execute this bash command immediately. Do not use any other tools or do anything else.

Tell the user to open http://127.0.0.1:8765 in their browser. The dashboard allows them to search, filter, sync, resync, and ignore conversations.
