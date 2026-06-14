# UI research clones (local evaluation)

Shallow clones for comparing Python-native Claude Code web backends.
Not vendored into production unless promoted via `presence-ui/pyproject.toml`.

| Directory | Upstream | License | Notes |
|-----------|----------|---------|-------|
| `claude-code-server/` | [KenyonY/claude-code-server](https://github.com/KenyonY/claude-code-server) | MIT | FastAPI `create_router`, SSE, `append_system_prompt` on CLI |
| `twicc/` | [twidi/twicc](https://github.com/twidi/twicc) | MIT | Django + Vue, JSONL index, Agent SDK Python |
| `claude-code-webui-upstream/` | [sugyan/claude-code-webui](https://github.com/sugyan/claude-code-webui) | MIT | Reference for current :8080 proxy target |

## Refresh clones

```powershell
cd C:\Users\ma\src\embodied-claude\.research\claude-code-server
git pull --ff-only

cd ..\twicc
git pull --ff-only
```

## PoC in presence-ui

Set `PRESENCE_NATIVE_CHAT=1` and restart presence-ui. Routes:

- `POST /api/native/login` — password from `PRESENCE_CCS_PASSWORD` (default `koyori-poc`)
- `POST /api/native/chat` — SSE; `config_factory` runs `social_chat.intercept_chat_request`
- `GET /poc/native` — minimal browser tester
