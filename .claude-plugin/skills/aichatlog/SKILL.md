# AIChatLog Skill

This skill manages the synchronization of Claude Code conversations to your knowledge base via configurable output adapters.

## When to use

Use this skill when the user asks about:
- Syncing conversations to their knowledge base
- Checking sync status or logs
- Configuring output adapters (local, FNS, Git, server)
- Troubleshooting sync issues

## Available commands

- `/aichatlog:web` — Open the web dashboard (the single management entry point)

All configuration, testing, sync operations, and log viewing are done through the dashboard.

## How it works

A Stop hook fires after every Claude Code session ends, calling `scripts/aichatlog.py hook` which:
1. Ingests the latest conversation JSONL into a local SQLite database
2. Formats the conversation into a markdown note (or ConversationObject for server mode)
3. Pushes via the configured output adapter (local, FNS, Git, or server)
4. Tracks sync state in the database to avoid duplicates

## Output Adapters

| Adapter | Mode | Description |
|---------|------|-------------|
| `local` | Lite | Write .md files directly to a local directory |
| `fns` | Lite | Push via Fast Note Sync REST API |
| `git` | Lite | Write .md + auto git commit (optional push) |
| `server` | Server | POST ConversationObject to aichatlog-server |

## Web Dashboard (`/aichatlog:web`)

The dashboard runs on `http://127.0.0.1:8765` and provides three tabs:

- **Conversations** — Search, filter, sort conversations. One-click sync, resync, ignore, unignore. Bulk "Sync All" button.
- **Settings** — Configure output adapter, device name, sync directory, language. Test connectivity with one click.
- **Log** — View recent sync activity log.

## Configuration

Config is stored at `~/.config/aichatlog/config.json`. Database at `~/.config/aichatlog/aichatlog.db`. Configure via the Dashboard Settings tab or `aichatlog setup` CLI.
