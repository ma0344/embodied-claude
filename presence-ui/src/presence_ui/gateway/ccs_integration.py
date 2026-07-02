"""PoC: native Claude CLI chat router with embodied gateway enrich."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from claude_code_server import AgentConfig, ChatRequest
from fastapi import FastAPI

from presence_ui.gateway.context_limits import (
    lite_append_max_chars,
    lite_compose_max_chars,
)
from presence_ui.gateway.prompt_block_safe import truncate_prompt_text
from presence_ui.gateway.social_chat import ChatInterceptResult, intercept_chat_request

_DEFAULT_PERMISSION_MODE = "acceptEdits"
_DEFAULT_MODEL = "google/gemma-4-12b-qat"
_SILENT_APPEND = (
    "[Gateway directive — not for the user]\n"
    "Social plan selected stay_silent/defer. Reply with nothing visible to the user."
)

# Native chat uses context_limits (defaults raised for ~87k ctx ma-home).
_LITE_COMPOSE_MAX_CHARS = lite_compose_max_chars()
_LITE_APPEND_MAX_CHARS = lite_append_max_chars()

_MODEL_ENV_KEYS = (
    "CLAUDE_MODEL",
    "PRESENCE_LLM_MODEL",
    "LMSTUDIO_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
)


def embodied_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_chat_surface_dir() -> Path:
    return embodied_repo_root() / "presence-ui" / "koyori-surface"


def chat_working_dir() -> Path:
    """Native chat subprocess cwd — thin CLAUDE.md, separate from dev repo root."""
    if os.getenv("PRESENCE_CHAT_USE_REPO_ROOT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return embodied_repo_root()
    override = os.getenv("PRESENCE_CHAT_WORKING_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _default_chat_surface_dir().resolve()


def resolved_claude_model() -> str:
    """Single model id for Claude CLI + LM Studio (prefer QAT)."""
    for key in _MODEL_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value

    settings_path = embodied_repo_root() / ".claude" / "settings.local.json"
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        top = str(data.get("model") or "").strip()
        if top:
            return top
        env_block = data.get("env") or {}
        for key in _MODEL_ENV_KEYS:
            value = str(env_block.get(key) or "").strip()
            if value:
                return value

    return _DEFAULT_MODEL


def lm_studio_env_for_model(model: str) -> dict[str, str]:
    """Env vars Claude CLI reads; keeps haiku/sonnet/opus/subagent aligned."""
    return {
        "CLAUDE_MODEL": model,
        "LMSTUDIO_MODEL": model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
        "CLAUDE_CODE_SUBAGENT_MODEL": model,
    }


_CAPABILITIES_ENV_KEYS = (
    "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES",
    "ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES",
)


def lm_studio_claude_compat_env() -> dict[str, str]:
    """Kiosk defaults: keep Claude Code from sending effort/thinking to Gemma via LM Studio.

    Gemma 4 only accepts reasoning ``on``/``off``; any effort level becomes ``on`` and the
    chat template injects ``<|think|>`` before the harness system text (see ``llm.prediction.input``).

    Override: ``PRESENCE_CLAUDE_DISABLE_THINKING``, ``PRESENCE_CLAUDE_EFFORT_LEVEL``,
    ``PRESENCE_CLAUDE_SUPPORTED_CAPABILITIES`` (empty = no effort/thinking features).
    """
    disable = os.getenv("PRESENCE_CLAUDE_DISABLE_THINKING", "1").strip() or "1"
    effort = os.getenv("PRESENCE_CLAUDE_EFFORT_LEVEL", "auto").strip() or "auto"
    caps = os.getenv("PRESENCE_CLAUDE_SUPPORTED_CAPABILITIES", "").strip()
    env: dict[str, str] = {
        "CLAUDE_CODE_DISABLE_THINKING": disable,
        "CLAUDE_CODE_EFFORT_LEVEL": effort,
    }
    for key in _CAPABILITIES_ENV_KEYS:
        env[key] = caps
    return env


def ccs_password() -> str:
    return os.getenv("PRESENCE_CCS_PASSWORD", "koyori-poc")


def default_agent_config(*, working_dir: Path | None = None) -> AgentConfig:
    model = resolved_claude_model()
    base_env = lm_studio_env_for_model(model)
    extra = {
        k: v
        for k, v in os.environ.items()
        if k.startswith("ANTHROPIC_") or k.startswith("CLAUDE_")
    }
    repo = embodied_repo_root()
    merged_env = {
        **extra,
        **base_env,
        **lm_studio_claude_compat_env(),
        "EMBODIED_CLAUDE_ROOT": os.getenv("EMBODIED_CLAUDE_ROOT", str(repo)),
        "PRESENCE_PROJECT_PATH": os.getenv("PRESENCE_PROJECT_PATH", str(repo)),
    }
    merged_env.pop("CLAUDE_CODE_ALWAYS_ENABLE_EFFORT", None)

    mcp_config_path: str | None = None
    strict_mcp = False
    from presence_ui.gateway.kiosk_mcp import (
        build_strict_mcp_config_file,
        strict_mcp_config_enabled,
    )

    if strict_mcp_config_enabled():
        try:
            mcp_config_path = str(build_strict_mcp_config_file())
            strict_mcp = True
        except (OSError, ValueError, json.JSONDecodeError):
            strict_mcp = False

    return AgentConfig(
        working_dir=str(working_dir or chat_working_dir()),
        permission_mode=os.getenv("PRESENCE_CCS_PERMISSION_MODE", _DEFAULT_PERMISSION_MODE),
        password=ccs_password(),
        max_turns=int(os.getenv("PRESENCE_CCS_MAX_TURNS", "20")),
        model=model,
        env=merged_env,
        mcp_config_path=mcp_config_path,
        strict_mcp_config=strict_mcp,
    )


def _cap_append(text: str, *, max_chars: int) -> str:
    return truncate_prompt_text(text.strip(), max_chars)


def agent_config_from_intercept(
    intercept: ChatInterceptResult,
    base: AgentConfig,
) -> AgentConfig:
    """Build AgentConfig from an already-run intercept (no second compose/plan)."""
    if not intercept.forward:
        return base.model_copy(update={"append_system_prompt": _SILENT_APPEND})

    enriched = intercept.payload or {}
    append = str(enriched.get("appendSystemPrompt") or "").strip()
    append = _cap_append(append, max_chars=_LITE_APPEND_MAX_CHARS) if append else ""
    permission_mode = str(enriched.get("permissionMode") or base.permission_mode)
    return base.model_copy(
        update={
            "append_system_prompt": append or None,
            "permission_mode": permission_mode,
        },
    )


def make_ccs_config_factory(
    *,
    person_id: str,
    working_dir: Path | None = None,
) -> Callable[[ChatRequest], AgentConfig]:
    """Deprecated helper — prefer intercept once + agent_config_from_intercept in router."""

    base = default_agent_config(working_dir=working_dir)

    def factory(req: ChatRequest) -> AgentConfig:
        intercept = intercept_chat_request(
            payload={"message": req.prompt, "sessionId": req.session_id},
            person_id=person_id,
            lite=True,
        )
        return agent_config_from_intercept(intercept, base)

    return factory


def mount_claude_code_server_router(
    app: FastAPI,
    *,
    person_id: str,
    prefix: str = "/api/native",
) -> None:
    """Attach native chat PoC routes (SSE; memory list bypasses Claude CLI)."""
    from presence_ui.gateway.native_chat_router import create_native_chat_router

    app.include_router(
        create_native_chat_router(person_id=person_id),
        prefix=prefix,
        tags=["native-chat-poc"],
    )
