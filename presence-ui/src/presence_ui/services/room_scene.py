"""OBS-TICK-1b — per-view room scene signals (phash vs per-preset baseline, JSONL log).

視点（ONVIF preset）ごとに baseline を持ち、その時点のカメラ向きに対応する錨と比較する。
view_id: "window" / "desk" / "dining"（camera_locations.PresetLocation と一致）。
tick ルーティンは dining（部屋全景）を既定 view とする。
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

_JST = ZoneInfo("Asia/Tokyo")

# センサーの時間ノイズ潰し（1b′ 2026-07-07 まー観察）:
# ライブ画像は静止時も 1 秒毎に下位ビットが揺れる。ブラーで高周波を落とし、
# 主信号は DCT pHash（低周波）に置く。dHash は比較用に併記。
_BLUR_RADIUS = float(os.getenv("PRESENCE_ROOM_BLUR_RADIUS", "1.0"))


def _jst_now() -> str:
    """POC 信号ログ用の JST タイムスタンプ（例 2026-07-07T15:35:15+09:00）。"""
    return datetime.now(_JST).isoformat(timespec="seconds")


VIEW_IDS = ("window", "desk", "dining")
DEFAULT_TICK_VIEW = "dining"
_BASELINE_DATE = "2026-07-07"
_SIGNAL_LOG_MAX_LINES = 10_000
# 開発用フレーム保存（犬/人/ノイズの目視切り分け）。既定 OFF。
_FRAMES_MAX_PER_VIEW = int(os.getenv("PRESENCE_ROOM_FRAMES_MAX", "200"))


def room_save_frames_enabled() -> bool:
    return os.getenv("PRESENCE_ROOM_SAVE_FRAMES", "0").lower() in {"1", "true", "yes"}


def room_frames_dir(view_id: str) -> Path:
    return presence_ui_home() / "frames" / view_id

# 既定の baseline 元画像（PRESENCE_ROOM_BASELINE_IMAGE_<VIEW> で上書き可）
_DEFAULT_BASELINE_IMAGES: dict[str, str] = {
    "window": r"C:\Users\ma\Downloads\snapshot-202607071122954(window-outside).jpg",
    "desk": r"C:\Users\ma\Downloads\sapshot-202607071123042(ma-desk).jpg",
    "dining": r"C:\Users\ma\Downloads\snapshot-202607071151106(dining).jpg",
}

_VIEW_NOTES: dict[str, str] = {
    "window": "窓/外 preset1 · 手動 B0",
    "desk": "まーのデスク preset2 · 手動 B0",
    "dining": "ダイニング/部屋全景 preset3 · 手動 B0",
}


def presence_ui_home() -> Path:
    return Path(
        os.environ.get("PRESENCE_UI_HOME", str(Path.home() / ".claude" / "presence-ui")),
    ).expanduser()


def room_baselines_path() -> Path:
    override = os.getenv("PRESENCE_ROOM_BASELINES_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return presence_ui_home() / "room_baselines.json"


def room_scene_signals_path() -> Path:
    override = os.getenv("PRESENCE_ROOM_SIGNALS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return presence_ui_home() / "room_scene_signals.jsonl"


def room_scene_state_path() -> Path:
    return presence_ui_home() / "room_scene_state.json"


def baseline_source_image(view_id: str) -> Path:
    env_key = f"PRESENCE_ROOM_BASELINE_IMAGE_{view_id.upper()}"
    raw = os.getenv(env_key, _DEFAULT_BASELINE_IMAGES.get(view_id, "")).strip()
    return Path(raw).expanduser()


def obs_tick_1b_enabled() -> bool:
    return os.getenv("PRESENCE_OBS_TICK_1B", "1").lower() in {"1", "true", "yes"}


@dataclass(slots=True)
class RoomBaseline:
    baseline_id: str
    view_id: str
    set_at: str
    anchor_path: str
    anchor_phash_hex: str
    source_image: str
    notes: str = ""
    anchor_phash_dct_hex: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "view_id": self.view_id,
            "set_at": self.set_at,
            "anchor_path": self.anchor_path,
            "anchor_phash_hex": self.anchor_phash_hex,
            "anchor_phash_dct_hex": self.anchor_phash_dct_hex,
            "source_image": self.source_image,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomBaseline:
        return cls(
            baseline_id=str(data["baseline_id"]),
            view_id=str(data.get("view_id") or data.get("view") or ""),
            set_at=str(data["set_at"]),
            anchor_path=str(data["anchor_path"]),
            anchor_phash_hex=str(data["anchor_phash_hex"]),
            source_image=str(data.get("source_image") or ""),
            notes=str(data.get("notes") or ""),
            anchor_phash_dct_hex=str(data.get("anchor_phash_dct_hex") or ""),
        )


def load_image_from_bytes(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw))


def load_image_from_base64(image_base64: str) -> Image.Image:
    raw = base64.standard_b64decode(image_base64)
    return load_image_from_bytes(raw)


def _denoised_gray(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """グレースケール化 → ガウシアンブラー（高周波ノイズ除去）→ ダウンスケール。"""
    gray = image.convert("L")
    if _BLUR_RADIUS > 0:
        gray = gray.filter(ImageFilter.GaussianBlur(radius=_BLUR_RADIUS))
    return gray.resize(size, Image.Resampling.LANCZOS)


def compute_phash_hex(image: Image.Image) -> str:
    """64-bit difference hash (dHash) — ブラー後。比較用（高周波に敏感）。"""
    gray = _denoised_gray(image, (9, 8))
    pixels = list(gray.get_flattened_data())
    value = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            value = (value << 1) | (1 if left > right else 0)
    return f"{value:016x}"


def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n).reshape(-1, 1)
    x = np.arange(n).reshape(1, -1)
    m = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
    m[0] *= 1.0 / np.sqrt(2)
    return m * np.sqrt(2.0 / n)


_DCT32 = _dct_matrix(32)


def compute_dct_phash_hex(image: Image.Image) -> str:
    """64-bit DCT perceptual hash (pHash) — 低周波のみ。センサーノイズに強い。主信号。"""
    gray = _denoised_gray(image, (32, 32))
    arr = np.asarray(gray, dtype=np.float64)
    dct = _DCT32 @ arr @ _DCT32.T
    low = dct[:8, :8]
    med = float(np.median(low))
    bits = (low > med).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming_hex(a_hex: str, b_hex: str) -> int:
    a = int(a_hex, 16)
    b = int(b_hex, 16)
    return (a ^ b).bit_count()


def grayscale_mae(image_a: Image.Image, image_b: Image.Image) -> float:
    a = _denoised_gray(image_a, (32, 32))
    b = _denoised_gray(image_b, (32, 32))
    pa = list(a.get_flattened_data())
    pb = list(b.get_flattened_data())
    total = sum(abs(x - y) for x, y in zip(pa, pb, strict=True))
    return round(total / (32 * 32 * 255), 6)


def load_baselines() -> dict[str, RoomBaseline]:
    path = room_baselines_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("room baselines load failed (%s): %s", path, exc)
        return {}
    out: dict[str, RoomBaseline] = {}
    for view_id, entry in data.items():
        try:
            out[view_id] = RoomBaseline.from_dict(entry)
        except (KeyError, TypeError) as exc:
            logger.warning("room baseline entry invalid (%s): %s", view_id, exc)
    return out


def load_baseline(view_id: str) -> RoomBaseline | None:
    return load_baselines().get(view_id)


def _save_baselines(baselines: dict[str, RoomBaseline]) -> None:
    path = room_baselines_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {view_id: b.to_dict() for view_id, b in baselines.items()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> dict[str, Any]:
    path = room_scene_state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_last(view_id: str, key: str) -> str | None:
    entry = _load_state().get(view_id)
    if isinstance(entry, dict):
        value = entry.get(key)
        return str(value) if value else None
    return None


def _save_last(view_id: str, *, phash_hex: str, phash_dct_hex: str) -> None:
    path = room_scene_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    state[view_id] = {
        "last_phash_hex": phash_hex,
        "last_phash_dct_hex": phash_dct_hex,
        "last_ts": _jst_now(),
    }
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_room_baseline(view_id: str, *, force: bool = False) -> RoomBaseline | None:
    """Register B0 for one view from PRESENCE_ROOM_BASELINE_IMAGE_<VIEW> if missing/forced."""
    source = baseline_source_image(view_id)
    if not source.is_file():
        logger.warning("room baseline source missing (%s): %s", view_id, source)
        return load_baseline(view_id)

    baselines = load_baselines()
    existing = None if force else baselines.get(view_id)
    if existing and existing.source_image == str(source) and existing.anchor_phash_dct_hex:
        anchor = Path(existing.anchor_path)
        if anchor.is_file():
            return existing

    try:
        image = load_image_from_bytes(source.read_bytes())
    except OSError as exc:
        logger.warning("room baseline image read failed (%s): %s", source, exc)
        return baselines.get(view_id)

    phash_hex = compute_phash_hex(image)
    phash_dct_hex = compute_dct_phash_hex(image)
    anchor_dir = presence_ui_home() / "baselines"
    anchor_dir.mkdir(parents=True, exist_ok=True)
    baseline_id = f"{view_id}_{_BASELINE_DATE}"
    anchor_path = anchor_dir / f"{baseline_id}.jpg"
    if not anchor_path.is_file() or force:
        shutil.copy2(source, anchor_path)

    baseline = RoomBaseline(
        baseline_id=baseline_id,
        view_id=view_id,
        set_at=_jst_now(),
        anchor_path=str(anchor_path),
        anchor_phash_hex=phash_hex,
        source_image=str(source),
        notes=_VIEW_NOTES.get(view_id, ""),
        anchor_phash_dct_hex=phash_dct_hex,
    )
    baselines[view_id] = baseline
    _save_baselines(baselines)
    logger.info("room baseline registered: %s (%s)", baseline_id, anchor_path)
    return baseline


def ensure_all_baselines(*, force: bool = False) -> dict[str, RoomBaseline]:
    for view_id in VIEW_IDS:
        ensure_room_baseline(view_id, force=force)
    return load_baselines()


def _trim_signal_log(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= _SIGNAL_LOG_MAX_LINES:
        return
    trimmed = lines[-_SIGNAL_LOG_MAX_LINES :]
    path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def _prune_frames(view_dir: Path) -> None:
    try:
        frames = sorted(view_dir.glob("*.jpg"))
    except OSError:
        return
    excess = len(frames) - _FRAMES_MAX_PER_VIEW
    for path in frames[:excess]:
        try:
            path.unlink()
        except OSError:
            pass


def _save_frame(view_id: str, image_base64: str, metrics: dict[str, Any]) -> str | None:
    """開発用に tick フレームを JPG 保存。ファイル名に hamming 値を埋めて目視選別を楽に。"""
    try:
        raw = base64.standard_b64decode(image_base64)
    except (ValueError, TypeError):
        return None
    view_dir = room_frames_dir(view_id)
    view_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(_JST).strftime("%Y%m%dT%H%M%S")

    def _fmt(value: Any) -> str:
        return "x" if value is None else str(value)

    name = (
        f"{stamp}_b{_fmt(metrics.get('hamming_baseline'))}"
        f"_p{_fmt(metrics.get('hamming_prev'))}"
        f"_dctb{_fmt(metrics.get('hamming_dct_baseline'))}"
        f"_dctp{_fmt(metrics.get('hamming_dct_prev'))}.jpg"
    )
    path = view_dir / name
    try:
        path.write_bytes(raw)
    except OSError as exc:
        logger.warning("room frame save failed (%s): %s", path, exc)
        return None
    _prune_frames(view_dir)
    return str(path)


def log_room_tick_signal(
    *,
    view_id: str,
    image_base64: str,
    capture_path: str | None = None,
) -> dict[str, Any] | None:
    """Append one signal row for a view; returns metrics dict or None on failure."""
    if not obs_tick_1b_enabled():
        return None

    baseline = ensure_room_baseline(view_id)
    if baseline is None:
        logger.warning("room tick signal skipped — no baseline for view %s", view_id)
        return None

    try:
        current = load_image_from_base64(image_base64)
        anchor = load_image_from_bytes(Path(baseline.anchor_path).read_bytes())
    except (OSError, ValueError) as exc:
        logger.warning("room tick signal image load failed (%s): %s", view_id, exc)
        return None

    phash_hex = compute_phash_hex(current)
    phash_dct_hex = compute_dct_phash_hex(current)
    hamming_baseline = hamming_hex(phash_hex, baseline.anchor_phash_hex)
    hamming_dct_baseline = (
        hamming_hex(phash_dct_hex, baseline.anchor_phash_dct_hex)
        if baseline.anchor_phash_dct_hex
        else None
    )
    last_phash = _load_last(view_id, "last_phash_hex")
    last_dct = _load_last(view_id, "last_phash_dct_hex")
    hamming_prev = hamming_hex(phash_hex, last_phash) if last_phash else None
    hamming_dct_prev = hamming_hex(phash_dct_hex, last_dct) if last_dct else None
    mae_baseline = grayscale_mae(current, anchor)

    row = {
        "ts": _jst_now(),
        "view_id": view_id,
        "baseline_id": baseline.baseline_id,
        "phash_dct_hex": phash_dct_hex,
        "hamming_dct_baseline": hamming_dct_baseline,
        "hamming_dct_prev": hamming_dct_prev,
        "phash_hex": phash_hex,
        "hamming_baseline": hamming_baseline,
        "hamming_prev": hamming_prev,
        "mae_baseline": mae_baseline,
        "capture_path": capture_path,
        "encode": "signal_only",
    }

    if room_save_frames_enabled():
        saved = _save_frame(view_id, image_base64, row)
        if saved:
            row["capture_path"] = saved

    log_path = room_scene_signals_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _trim_signal_log(log_path)
    _save_last(view_id, phash_hex=phash_hex, phash_dct_hex=phash_dct_hex)
    return row
