# AIChatLog Plugin for Claude Code

Python plugin that captures Claude Code conversations and syncs them to your knowledge base.

## Build & Test

```bash
# Install (editable)
pip install -e .
aichatlog status

# Syntax check
python3 -c "import ast; ast.parse(open('.claude-plugin/scripts/aichatlog.py').read())"
```

## Key Conventions

- **Zero external deps** in aichatlog.py — stdlib only
- Section headers: `# ── Section Name ──` with dashes
- Function prefixes: `cmd_`, `db_`, `cfg_`, `parse_`, `format_`, `sync_`, `ingest_`
- Tool results: detected via `toolUseResult` JSONL field, merged into preceding assistant message with `<!-- tool_result -->` markers
- Config: `~/.config/aichatlog/config.json`
- Database: `~/.config/aichatlog/aichatlog.db` (SQLite, WAL mode, schema v3)
- i18n: `STRINGS` dict with en/zh-CN/zh-TW, access via `t(key)`
- `aichatlog.py` and `core.py` must stay in sync. `core.py` adds `cmd_install()` / `cmd_uninstall()`
- Timestamps: stored as UTC ISO8601 with millisecond precision

## Output Adapters

All inherit from `OutputAdapter` with `write_note(path, content)` and `test_connection()`:
- **FNSAdapter** — POST to Fast Note Sync API
- **LocalAdapter** — Write .md files locally
- **GitAdapter** — Write + git commit/push
- **ServerAdapter** — POST ConversationObject to aichatlog-server (v2 sync protocol)

## ConversationObject Protocol

Transport format between plugin and server. Defined in [aichatlog-protocol](https://github.com/aichatlog/aichatlog-protocol).
- **v1**: Full payload, messages always included
- **v2**: Conditional sync — `check` (metadata only), `delta` (new messages only), `full`
