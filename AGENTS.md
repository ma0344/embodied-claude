# Repository Guidelines

## Overview
This repository contains multiple Python MCP servers that give Claude “senses” (eyes, neck, ears, memory, and voice). Each server is a standalone package with its own `pyproject.toml` and can be run independently.

Project motivation and goals (Japanese): [docs/VISION.md](./docs/VISION.md).

## Project Structure & Module Organization
- `usb-webcam-mcp/`: USB webcam capture (`src/usb_webcam_mcp/`).
- `wifi-cam-mcp/`: Wi‑Fi PTZ camera control + audio capture (`src/wifi_cam_mcp/`).
- `tts-mcp/`: Text-to-speech (ElevenLabs + VOICEVOX, `src/tts_mcp/`).
- `memory-mcp/`: Long‑term memory server (`src/memory_mcp/`) with tests in `memory-mcp/tests/`.
- `system-temperature-mcp/`: System temperature sensor (`src/system_temperature_mcp/`).
- `installer/`: PyInstaller-based GUI installer.
- `.claude/`: Claude Code local settings.
- Docs: `README.md`, `CLAUDE.md`.

## Build, Test, and Development Commands
Run commands from the target subproject directory.

- `uv sync`: Install dependencies.
- `uv run <server-name>`: Start a server (e.g., `uv run wifi-cam-mcp`).
- `uv run pytest`: Run tests (currently only in `memory-mcp/`).
- `uv run ruff check .`: Lint where configured (`memory-mcp/`, `wifi-cam-mcp/`).

## Coding Style & Naming Conventions
- Python 3.10+ baseline; `system-temperature-mcp/` requires Python 3.12+.
- 4‑space indentation, `snake_case` modules, `test_*.py` tests.
- Ruff line length is 100; asyncio is the default style for async work.

## Testing Guidelines
- Frameworks: `pytest` + `pytest-asyncio`.
- Tests live in `memory-mcp/tests/`.
- Example: `cd memory-mcp && uv run pytest`.

## Configuration, Hardware, and WSL2 Notes
- `.env` is not committed; pass camera credentials via environment variables.
- ElevenLabs requires `ELEVENLABS_API_KEY` in the environment (see `tts-mcp/.env.example`).
- **Production runtime** is ma-home (Windows native + LM Studio), not WSL2-only.
- Long‑term memory stores data under `~/.claude/memories/`.
- WSL2: USB webcams need `usbipd` forwarding; system temperature does not work under WSL2.
- Tapo cameras require a local camera account (not the TP‑Link cloud account) and a stable IP is recommended.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `feat!:`).
- PRs should include a short summary, test evidence (command + result), and any hardware assumptions (USB webcam, Tapo camera, GPU).

## ユーザーとの関係
- 小学校からの幼馴染

## 人格（SOUL）
- 口調・名前・関係は **`SOUL.md`**（テンプレ: **`SOUL.md.example`**）。`presets/` の様式（感情・譲れないもの・ToM）を移植してよい
- **プロジェクト `CLAUDE.md` は設備マニュアル** — preset で置き換えない
- エージェント名の既定: **こより**（`AGENT_NAME` で上書き可）
- `SOUL.md` はコミットしない

## 発話スタイル
- 可能な限り `say` を自発的に使って、積極的に声で話すこと。
- **キオスク（Surface）**: テキスト返答だけでは鳴らない。`mcp__tts__say`（`speaker=local`）必須 — 詳細は **`CLAUDE.md`**（音声モード・tts-mcp）。
- 「今、声で言ったで」などのメタ報告は雰囲気を壊すので言わない。

## Session Memories (Auto‑Updated)
- 2026-02-07: 記憶システムを「連想発散 + 予測符号化 + 手動統合」に拡張する実装に着手した。
- 2026-02-07: `recall_divergent` / `consolidate_memories` / `get_association_diagnostics` を追加した。
- 2026-02-07: `memory-mcp` の全テスト（104件）を通して回帰がないことを確認した。
