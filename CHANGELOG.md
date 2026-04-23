# Changelog

All notable changes to AIChatLog Plugin for Claude Code will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.9.1] - 2026-04-24

### Fixed
- Support current Claude Code JSONL path `~/.claude/projects/<path>/*.jsonl` alongside the legacy `~/.claude/conversation-logs/` path

## [0.9.0] - 2026-03-29

### Added
- `aichatlog reparse` command — force re-parse all conversations from JSONL
- Collapsible tool call rendering in dashboard (tool_use + tool_result as `<details>` blocks)
- `<aichatlog-message>` Web Component for message rendering

### Changed
- Dashboard shared UI extracted to `aichatlog-protocol/web/` — CSS, JS, and Web Components loaded via CDN instead of inline

### Fixed
- Tool results no longer render as user messages — merged into preceding assistant message using `toolUseResult` JSONL field
- `<!-- tool_result -->` markers properly handled in dashboard rendering pipeline

## [0.8.6] - 2026-03-24

### Added
- URL routing for server dashboard
- Inline shared UI components

## [0.8.5] - 2026-03-24

### Fixed
- Harden token security in plugin and server dashboards

## [0.8.4] - 2026-03-24

### Added
- Show/hide toggle for all password inputs

### Fixed
- Masked token/key placeholder in all password inputs
- Token status hint in plugin dashboard

## [0.8.3] - 2026-03-23

### Fixed
- Plugin dashboard test button shows detailed message + latency
- Latin-1 encoding error in HTTP error handling
- test_connection now validates token, not just reachability

## [0.8.0] - 2026-03-23

### Added
- Comprehensive plugin tests
- Logo and favicon across all surfaces

### Fixed
- Key dialog DOM bug
- List markers
- Capture tool_use/thinking blocks

## [0.7.0] - 2026-03-22

### Added
- Logo and favicon across all surfaces

### Changed
- Extract shared UI components into shared modules

### Fixed
- XML tag handling to prevent message swallowing
- Table header colors for light mode

## [0.5.0] - 2026-03-20

### Added
- Initial plugin extracted from monorepo
- Claude Code conversation capture (Stop event hook)
- Local SQLite storage with FTS5 search
- Embedded plugin dashboard
- Zero external dependencies (stdlib only)
- pip installable package
