# AIChatLog — Claude Code Plugin

English | [简体中文](README.zh-CN.md)

Auto-sync Claude Code conversations to your knowledge base. Hooks into Claude Code's Stop event, parses JSONL conversation logs, deduplicates by session, and syncs via configurable output adapters.

## Install

### pip (recommended)

```bash
pip install git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code
aichatlog install
```

This installs the `aichatlog` CLI and registers the Stop hook. Restart Claude Code to activate.

### Claude Code Plugin

```text
/plugin marketplace add https://github.com/aichatlog/aichatlog.git
```

Then install **aichatlog** from the marketplace.

## Setup

```bash
aichatlog setup --adapter=fns --url=http://localhost:37240 --token=YOUR_TOKEN --vault=MyVault
```

Adapters: `fns` (Obsidian via FNS), `local` (write .md files), `git` (auto-commit), `server` (push to aichatlog-server).

## Commands

| Command | Description |
| --- | --- |
| `aichatlog setup` | Configure adapter and settings |
| `aichatlog status` | Show config and sync stats |
| `aichatlog run` | Manually sync latest conversation |
| `aichatlog export` | Bulk sync all conversations |
| `aichatlog test` | Test adapter connectivity |
| `aichatlog web` | Launch web dashboard |

In Claude Code, use `/aichatlog:web` to open the dashboard.

## Update & Uninstall

```bash
# Update
pip install --upgrade git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code

# Uninstall
aichatlog uninstall   # remove hook
pip uninstall aichatlog-plugin
```
