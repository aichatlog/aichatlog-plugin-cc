# AIChatLog — Claude Code Plugin

English | [简体中文](README.zh-CN.md)

Auto-sync Claude Code conversations to your knowledge base. Hooks into Claude Code's Stop event, parses JSONL conversation logs, deduplicates by session, and syncs via configurable output adapters.

## Install

### pip (recommended)

> **Note:** Use `pip3` on macOS. The system `pip` may point to Python 2 which is no longer supported.

```bash
pip3 install git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code
```

If you see a warning that the script is not on PATH:

```text
WARNING: The script aichatlog is installed in '/Users/you/Library/Python/3.x/bin' which is not on PATH.
```

Add it to your shell profile:

```bash
# For zsh (default on macOS)
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Or use the full path directly
python3 -m aichatlog.core install
```

Then register the Claude Code hook:

```bash
aichatlog install
```

Restart Claude Code to activate.

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
pip3 install --upgrade git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code

# Uninstall
aichatlog uninstall   # remove hook
pip3 uninstall aichatlog-plugin
```
