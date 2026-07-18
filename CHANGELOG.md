# Changelog

## 0.3.1 (2026-07-18)

### Fixed
- ASCII banner now responsive — hides on narrow terminals (< 120 cols)
- Status bar footer commands now visible with bright white text and green border
- Input border color changed from default blue to green (#00cc66)
- Input area separated from status bar with green top-border

## 0.3.0 (2026-07-18)

### Added
- `ceche update` command — checks PyPI, prompts before upgrading

## 0.2.0 (2026-07-18)

### Changed
- textual moved to core dependencies — `ceche start` works out of box
- Green (#00cc66) primary theme, orange (#ff8800) headers, white banner

## 0.1.0 (2026-07-18)

Full rewrite with enterprise-grade architecture.

### Added
- 16-module appraisal engine with hexagonal architecture
- AI backbone: 7 layers (vault, tools, prompts, orchestrator, AI, observability, multi-model)
- CLI: 49 commands across 18 groups
- Bulk appraisal with concurrent processing
- Terminal UI (ceche start) with sidebar, module table, command palette
- HTTP API server (FastAPI) with web dashboard
- Portfolio management system
- Appraisal history with SQLite persistence
- Config system with TOML file cascade
- Rate limiter for external API calls
- CSV and JSON Lines output formats
- Filter, sort, and pagination on all commands
- AI key management with encrypted vault
- Cache management

### Changed
- CLI commands flattened to human-friendly names (ceche check, ceche keys, ceche stats, etc.)
- Output schema unified across all commands with version, generated_at, summary
- Dependencies: typer/rich/wordfreq moved to core (no [all] flag needed)
- Wayback adapter uses HTTPS

### Fixed
- M6 wordfreq lazy import fallback
- TUI command palette wired with real actions
- Module status shows real values (SUCCESS/SKIPPED) instead of "None"
- Domain input validation per RFC 1035
- Error logging in engine._safe() and auto-logging
