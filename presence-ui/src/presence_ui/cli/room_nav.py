"""Browse projects → histories → join (CLI steering wheel for shared session pointer)."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx

from presence_ui.schemas import JoinSessionRequest
from presence_ui.services.navigation import join_session, list_project_histories, list_projects
from presence_ui.services.sessions import list_sessions


def _api_base() -> str:
    return os.environ.get("PRESENCE_UI_URL", "http://127.0.0.1:8090").rstrip("/")


def _fetch_json(path: str) -> dict[str, Any]:
    url = f"{_api_base()}{path}"
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.json()


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_api_base()}{path}"
    response = httpx.post(url, json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def cmd_projects(*, limit: int, as_json: bool) -> int:
    if _use_http():
        data = _fetch_json(f"/api/v1/projects?limit={limit}")
    else:
        data = list_projects(limit=limit).model_dump(mode="json")
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    for index, project in enumerate(data.get("projects", []), start=1):
        print(
            f"{index:2}. {project['label']}  "
            f"({project['jsonl_count']} histories)  id={project['project_id']}"
        )
    return 0


def cmd_histories(*, project_id: str, limit: int, as_json: bool) -> int:
    if _use_http():
        data = _fetch_json(
            f"/api/v1/projects/{project_id}/histories?limit={limit}",
        )
    else:
        data = list_project_histories(project_id=project_id, limit=limit).model_dump(mode="json")
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"Project: {data.get('project_path', project_id)}")
    for index, history in enumerate(data.get("histories", []), start=1):
        room_flag = "部屋あり" if history.get("has_room") else "未取込"
        print(
            f"{index:2}. {history['title']}  "
            f"({history.get('message_count', 0)}件, {room_flag})  "
            f"room={history['room_session_id']}"
        )
    return 0


def cmd_rooms(*, limit: int, as_json: bool) -> int:
    if _use_http():
        data = _fetch_json("/api/v1/sessions?person_id=ma")
        sessions = data.get("sessions", [])
    else:
        sessions = [s.model_dump(mode="json") for s in list_sessions(limit=limit).sessions]
    if as_json:
        print(json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2))
        return 0
    for index, session in enumerate(sessions[:limit], start=1):
        print(
            f"{index:2}. {session['title']}  "
            f"({session.get('message_count', 0)}件)  id={session['session_id']}"
        )
    return 0


def cmd_join(
    *,
    session_id: str | None,
    project_id: str | None,
    history_id: str | None,
    client_id: str,
    sync_jsonl: bool,
    force_resync: bool,
    as_json: bool,
) -> int:
    payload = JoinSessionRequest(
        session_id=session_id,
        project_id=project_id,
        history_id=history_id,
        client_id=client_id,
        sync_jsonl=sync_jsonl,
        force_resync=force_resync,
    )
    if _use_http():
        data = _post_json("/api/v1/navigation/join", payload.model_dump(mode="json"))
    else:
        data = join_session(payload=payload).model_dump(mode="json")

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Joined: {data['title']}")
        print(f"session_id={data['session_id']}")
        if data.get("imported_count"):
            print(f"synced {data['imported_count']} new messages from JSONL")
        print("Talk naturally — this CLI session is pinned to the room.")
    return 0


def _pick(prompt: str, count: int) -> int | None:
    if count <= 0:
        return None
    while True:
        raw = input(prompt).strip()
        if raw.lower() in {"q", "quit", "exit"}:
            return None
        if not raw.isdigit():
            print("番号を入力してください。")
            continue
        choice = int(raw)
        if 1 <= choice <= count:
            return choice
        print(f"1〜{count} の番号を選んでください。")


def cmd_browse(*, client_id: str) -> int:
    projects_data = (
        _fetch_json("/api/v1/projects?limit=40")
        if _use_http()
        else list_projects(limit=40).model_dump(mode="json")
    )
    projects = projects_data.get("projects", [])
    if not projects:
        print("プロジェクトが見つかりません。~/.claude/projects/ を確認してください。")
        return 1

    print("=== プロジェクト ===")
    for index, project in enumerate(projects, start=1):
        print(f"{index:2}. {project['label']} ({project['jsonl_count']} histories)")
    choice = _pick("プロジェクト番号> ", len(projects))
    if choice is None:
        return 0
    project = projects[choice - 1]
    project_id = project["project_id"]

    if _use_http():
        histories_data = _fetch_json(f"/api/v1/projects/{project_id}/histories?limit=50")
    else:
        histories_data = list_project_histories(
            project_id=project_id,
            limit=50,
        ).model_dump(mode="json")
    histories = histories_data.get("histories", [])
    if not histories:
        print("このプロジェクトに履歴がありません。")
        return 1

    print("\n=== 履歴 / 部屋 ===")
    for index, history in enumerate(histories, start=1):
        flag = "部屋あり" if history.get("has_room") else "未取込"
        print(f"{index:2}. {history['title']} ({history.get('message_count', 0)}件, {flag})")
    choice = _pick("履歴番号> ", len(histories))
    if choice is None:
        return 0
    history = histories[choice - 1]

    payload = JoinSessionRequest(
        project_id=project_id,
        history_id=history["history_id"],
        client_id=client_id,
        sync_jsonl=True,
    )
    if _use_http():
        result = _post_json("/api/v1/navigation/join", payload.model_dump(mode="json"))
    else:
        result = join_session(payload=payload).model_dump(mode="json")

    print(f"\n部屋に入りました: {result['title']}")
    print(f"session_id={result['session_id']}")
    print("このまま自然に話しかけてください。")
    return 0


def _use_http() -> bool:
    return os.environ.get("ROOM_NAV_HTTP", "").lower() in {"1", "true", "yes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Koyori's Room navigation — projects → histories → join",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Call presence-ui HTTP API instead of direct DB access",
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("ROOM_CLIENT_ID", "koyori-room"),
        help="Client id for session activation (default: koyori-room)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    sub = parser.add_subparsers(dest="command")

    projects = sub.add_parser("projects", help="List Claude Code projects")
    projects.add_argument("--limit", type=int, default=40)

    histories = sub.add_parser("histories", help="List histories for a project")
    histories.add_argument("project_id", help="Encoded project id from `projects`")
    histories.add_argument("--limit", type=int, default=50)

    rooms = sub.add_parser("rooms", help="List all rooms (Web UI session list)")
    rooms.add_argument("--limit", type=int, default=40)

    join = sub.add_parser("join", help="Join a room by session_id or project+history")
    join.add_argument("--session-id", default=None)
    join.add_argument("--project-id", default=None)
    join.add_argument("--history-id", default=None)
    join.add_argument("--no-sync", action="store_true", help="Skip JSONL sync on join")
    join.add_argument("--force-resync", action="store_true")

    sub.add_parser("browse", help="Interactive: projects → histories → join")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.http:
        os.environ["ROOM_NAV_HTTP"] = "1"

    command = args.command or "browse"
    if command == "projects":
        return cmd_projects(limit=args.limit, as_json=args.json)
    if command == "histories":
        return cmd_histories(project_id=args.project_id, limit=args.limit, as_json=args.json)
    if command == "rooms":
        return cmd_rooms(limit=args.limit, as_json=args.json)
    if command == "join":
        if not args.session_id and not (args.project_id and args.history_id):
            parser.error("join requires --session-id or both --project-id and --history-id")
        return cmd_join(
            session_id=args.session_id,
            project_id=args.project_id,
            history_id=args.history_id,
            client_id=args.client_id,
            sync_jsonl=not args.no_sync,
            force_resync=args.force_resync,
            as_json=args.json,
        )
    if command == "browse":
        return cmd_browse(client_id=args.client_id)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
