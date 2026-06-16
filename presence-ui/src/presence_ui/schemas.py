"""API response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    sender: Literal["ma", "koyori"]
    message: str
    timestamp: str
    message_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    person_id: str = "ma"
    session_id: str = Field(min_length=1, max_length=64)


class ChatSendResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    koyori_message: ChatMessage | None = None
    silent: bool = False
    plan_move: str | None = None


class RoomSession(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: list[RoomSession]


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    person_id: str = "ma"


class CreateSessionResponse(BaseModel):
    session: RoomSession


class DeleteSessionResponse(BaseModel):
    session_id: str
    deleted_message_count: int
    was_imported: bool = False


class ActivateSessionRequest(BaseModel):
    person_id: str = "ma"
    client_id: str = "koyori-room"


class ActiveSessionResponse(BaseModel):
    client_id: str
    person_id: str
    session_id: str
    activated_at: str


class ProjectSummary(BaseModel):
    project_id: str
    label: str
    project_dir: str
    project_path: str
    jsonl_count: int = 0
    modified_at: str


class ProjectListResponse(BaseModel):
    claude_home: str
    projects: list[ProjectSummary]


class HistorySummary(BaseModel):
    history_id: str
    title: str
    kind: Literal["jsonl", "room"] = "jsonl"
    session_id: str
    room_session_id: str
    jsonl_path: str | None = None
    message_count: int = 0
    modified_at: str
    has_room: bool = False
    active: bool = False


class HistoryListResponse(BaseModel):
    project_id: str
    project_path: str
    project_dir: str
    histories: list[HistorySummary]


class JoinSessionRequest(BaseModel):
    person_id: str = "ma"
    client_id: str = "koyori-room"
    session_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=128)
    history_id: str | None = Field(default=None, max_length=64)
    sync_jsonl: bool = True
    force_resync: bool = False


class JoinSessionResponse(BaseModel):
    session_id: str
    title: str
    client_id: str
    person_id: str
    activated_at: str
    imported_count: int = 0
    created_room: bool = False
    message_count: int = 0


class WorkspaceJsonlFile(BaseModel):
    session_file_id: str
    path: str
    filename: str
    modified_at: str
    title: str
    message_count: int = 0
    project_path: str
    project_dir: str
    source: str = "claude-code"
    linked_session_id: str | None = None


class WorkspaceJsonlListResponse(BaseModel):
    project_path: str
    project_dirs: list[dict[str, str]] = Field(default_factory=list)
    claude_home: str
    files: list[WorkspaceJsonlFile]


class ImportWorkspaceRequest(BaseModel):
    project_path: str | None = None
    session_file_id: str | None = Field(default=None, max_length=64)
    jsonl_path: str | None = None
    use_latest: bool = False
    title: str | None = Field(default=None, max_length=80)
    person_id: str = "ma"
    force: bool = False


class ImportWorkspaceResponse(BaseModel):
    session: RoomSession
    imported_count: int
    already_imported: bool = False
    source_jsonl: str


class DesireItem(BaseModel):
    id: str
    level: float
    discomfort: float | None = None


class ActiveArc(BaseModel):
    title: str
    status: str
    importance: float
    summary: str


class RecentExperience(BaseModel):
    experience_id: str
    ts: str
    kind: str
    summary: str
    importance: int


class SocialStateView(BaseModel):
    timestamp: str
    presence: str
    activity: str
    availability: str
    interaction_phase: str
    energy: str
    interrupt_cost: float
    affect_label: str
    summary: str


class TemperatureView(BaseModel):
    celsius: float | None
    feeling: str
    source: str | None = None


class ReminderCardItem(BaseModel):
    commitment_id: str
    due_at: str | None = None
    title: str | None = None
    speak_line: str | None = None
    delivery: Literal["say", "nudge_only"] = "say"


class CancelReminderRequest(BaseModel):
    commitment_id: str
    source_text: str = ""


class PatchReminderSpeakLineRequest(BaseModel):
    commitment_id: str
    speak_line: str = Field(min_length=1, max_length=240)
    source_text: str = ""


class CancelReminderResponse(BaseModel):
    ok: bool = True
    commitment_id: str


class PatchReminderSpeakLineResponse(BaseModel):
    ok: bool = True
    commitment_id: str
    speak_line: str


class KoyoriStatusResponse(BaseModel):
    updated_at: str
    desires: list[DesireItem]
    dominant_desire: str | None = None
    active_arcs: list[ActiveArc]
    recent_experiences: list[RecentExperience]
    social_state: SocialStateView | None = None
    temperature: TemperatureView
    reminders: list[ReminderCardItem] = Field(default_factory=list)


class CameraSnapshotResponse(BaseModel):
    timestamp: str
    image_base64: str | None = None
    image_url: str | None = None
    width: int | None = None
    height: int | None = None
    camera_preset: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    details: dict[str, Any] = Field(default_factory=dict)


class NativeSessionSummary(BaseModel):
    session_id: str
    title: str
    preview: str = ""
    updated_at: str
    message_count: int = 0


class NativeSessionListResponse(BaseModel):
    sessions: list[NativeSessionSummary]


class NativeSessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class NativeHiddenSessionsRequest(BaseModel):
    session_ids: list[str] = Field(default_factory=list, max_length=100)


class NativeHideSessionResponse(BaseModel):
    ok: bool = True
    session_id: str
    hidden_count: int = 0


class OutboundPendingItem(BaseModel):
    nudge_id: str
    ts: str
    text: str
    speak: bool = False
    channels: list[str] = Field(default_factory=list)
    desire: str | None = None


class OutboundPendingResponse(BaseModel):
    items: list[OutboundPendingItem] = Field(default_factory=list)
    server_ts: str


class OutboundAckRequest(BaseModel):
    nudge_id: str = Field(min_length=1, max_length=64)
    client_id: str = Field(min_length=1, max_length=64)
    channels: list[str] = Field(default_factory=list, max_length=8)


class OutboundAckResponse(BaseModel):
    ok: bool
    nudge_id: str


class TtsSurfaceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class TtsSurfaceResponse(BaseModel):
    ok: bool = True
    token: str = ""
    audio_url: str = ""
    content_type: str = ""


class RoomSayResponse(BaseModel):
    ok: bool = True
    detail: str = "routed to kiosk"
    say_id: str = ""
    sse_listeners: int = 0
    queued: bool = True


class RoomSayPendingItem(BaseModel):
    say_id: str
    ts: str
    text: str
    source: str = "say"
    audio_url: str | None = None


class RoomSayPendingResponse(BaseModel):
    items: list[RoomSayPendingItem] = Field(default_factory=list)
    server_ts: str = ""


class RoomSayAckRequest(BaseModel):
    say_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)


class RoomSayAckResponse(BaseModel):
    ok: bool = True
    say_id: str = ""


class ClaudePermissionPresetItem(BaseModel):
    id: str
    rule: str
    label: str
    enabled: bool


class ClaudePermissionsResponse(BaseModel):
    presets: list[ClaudePermissionPresetItem] = Field(default_factory=list)
    preserved_rules: list[str] = Field(default_factory=list)
    settings_path: str
    editable: bool = False


class ClaudePermissionsSaveRequest(BaseModel):
    enabled_ids: list[str] = Field(default_factory=list, max_length=32)


class ClaudePermissionsSaveResponse(BaseModel):
    ok: bool = True
    presets: list[ClaudePermissionPresetItem] = Field(default_factory=list)
    preserved_rules: list[str] = Field(default_factory=list)
    note: str = "次のメッセージから反映（新しい会話推奨）"
