# Contributing to AIChatLog Plugin for Claude Code

Thanks for your interest in contributing! This guide covers the Claude Code plugin specifically.

## Getting Started

```bash
git clone https://github.com/aichatlog/aichatlog-plugin-cc.git
cd aichatlog-plugin-cc
pip install -e .
aichatlog status
```

### Verify

```bash
python3 -c "import ast; ast.parse(open('.claude-plugin/scripts/aichatlog.py').read())"
```

## Code Conventions

- **Zero external deps** — stdlib only in `aichatlog.py`
- `aichatlog.py` and `core.py` must stay in sync (`core.py` = `aichatlog.py` + install/uninstall)
- Function prefixes: `cmd_`, `db_`, `cfg_`, `parse_`, `format_`, `sync_`, `ingest_`
- Section headers: `# ── Section Name ──` with dashes

## How to Contribute

### New Output Adapter

1. Add a new class inheriting from `OutputAdapter`
2. Implement `write_note(path, content)` and `test_connection()`
3. Register in the adapter factory

### New Input Plugin for Other AI Tools

See [aichatlog-protocol](https://github.com/aichatlog/aichatlog-protocol) for the ConversationObject spec. Name your repo `aichatlog-plugin-{source}`.

## Pull Request Process

1. Fork and create a feature branch
2. Make your changes
3. Run syntax check: `python3 -c "import ast; ast.parse(open('.claude-plugin/scripts/aichatlog.py').read())"`
4. Submit PR with a clear description of what and why

## Related Repos

- [aichatlog-protocol](https://github.com/aichatlog/aichatlog-protocol) — ConversationObject spec
- [aichatlog-server](https://github.com/aichatlog/aichatlog-server) — Server component
- [aichatlog-docs](https://github.com/aichatlog/aichatlog-docs) — Design documents

## License

AGPL-3.0 — see [LICENSE](LICENSE).
