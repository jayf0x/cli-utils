from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - urllib3 is bundled with requests
    Retry = None

DEFAULT_OUTPUT_DIR = Path("./out")
DEFAULT_CACHE_DIR = Path("./.caches")
DEFAULT_SUMMARY_FILENAME = "summary.json"
DEFAULT_CHUNK_SIZE = 1024 * 512
DEFAULT_RECONNECT_WAIT = 2.0
DEFAULT_AUTOPASTE_INTERVAL = 1.2
MIN_CACHE_HTML_BYTES = 512
USER_AGENT = "unarchive/1.1"
SPEED_PRESETS = {
    "gentle": 2,
    "balanced": 4,
    "fast": 8,
    "turbo": 10,
}
BOOLEAN_SELECT_OPTIONS = [("On", "on"), ("Off", "off")]
PREFETCH_MODE_OPTIONS = [("Off", "off"), ("Exact ping", "exact"), ("Fuzzy ping", "fuzzy")]
LOCAL_VENDOR_DIR = Path(__file__).with_name(".vendor")
if LOCAL_VENDOR_DIR.exists():
    sys.path.insert(0, str(LOCAL_VENDOR_DIR.resolve()))

UI_CSS = """
Screen {
    layout: vertical;
    background: $surface;
}

#main {
    layout: vertical;
    padding: 1 2;
    background: transparent;
}

#hero {
    height: auto;
    margin-bottom: 1;
    border: tall $accent;
    background: $boost;
    color: $text;
    padding: 1 2;
}

.hero-title {
    text-style: bold;
    color: $accent;
}

.hero-subtitle {
    color: $text-muted;
}

#control-deck {
    layout: vertical;
    height: auto;
    margin-bottom: 1;
}

.panel {
    margin-bottom: 1;
    border: round $surface-lighten-1;
    background: $panel;
    padding: 1;
}

.panel-title {
    margin-bottom: 1;
    text-style: bold;
    color: $accent;
}

.field-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
}

.field-main {
    width: 1fr;
    margin-right: 1;
}

.field-side {
    width: 22;
    margin-right: 1;
}

.field-wide {
    width: 28;
    margin-right: 1;
}

#actions {
    height: auto;
    margin-bottom: 1;
}

#summary {
    height: auto;
    margin-bottom: 1;
    border: round $accent;
    padding: 1;
    background: $panel;
}

#stats {
    layout: horizontal;
    margin-bottom: 1;
}

.stat-card {
    width: 1fr;
    margin-right: 1;
    border: round $surface-lighten-1;
    background: $surface-darken-1;
    padding: 1;
}

.stat-card:last-child {
    margin-right: 0;
}

.stat-title {
    color: $text-muted;
}

.stat-value {
    text-style: bold;
    color: $accent;
}

#progress {
    margin-bottom: 1;
}

Log {
    height: 1fr;
    border: round $surface-lighten-1;
    background: $surface-darken-1;
}
"""


@dataclass(slots=True)
class AppConfig:
    page_url: str = ""
    output_dir: Path = DEFAULT_OUTPUT_DIR
    cache_dir: Path = DEFAULT_CACHE_DIR
    html_file: Path | None = None
    speed: str = "balanced"
    workers: int | None = None
    retries: int = 4
    timeout: int = 30
    delay_seconds: float = 0.25
    chunk_size: int = DEFAULT_CHUNK_SIZE
    duration_tolerance_seconds: float = 3.0
    reconnect_wait_seconds: float = DEFAULT_RECONNECT_WAIT
    autopaste_enabled: bool = False
    autopaste_interval_seconds: float = DEFAULT_AUTOPASTE_INTERVAL
    prefetch_ping_mode: str = "exact"
    verify_existing: bool = True
    verify_after_download: bool = True
    strip_common_prefix: bool = True
    normalize_sort_names: bool = True
    prefix_override: str = ""
    custom_css_path: Path | None = None
    use_cache: bool = True
    force_refresh: bool = False
    allow_insecure_http: bool = False
    dry_run: bool = False
    summary_filename: str = DEFAULT_SUMMARY_FILENAME

    def resolved_workers(self) -> int:
        if self.workers is not None:
            return max(1, int(self.workers))
        return SPEED_PRESETS.get(self.speed, SPEED_PRESETS["balanced"])

    @property
    def summary_path(self) -> Path:
        return self.output_dir / self.summary_filename


@dataclass(slots=True)
class TrackPlan:
    index: int
    title: str
    source_url: str
    source_path: str
    original_relpath: str
    output_relpath: str
    output_path: Path
    legacy_output_relpath: str | None = None
    legacy_output_path: Path | None = None
    expected_size: int | None = None
    expected_duration: float | None = None
    md5: str | None = None
    sha1: str | None = None


@dataclass(slots=True)
class TrackResult:
    track_index: int
    title: str
    output_path: str
    status: str
    reason: str
    expected_size: int | None = None
    actual_size: int | None = None
    expected_duration: float | None = None
    actual_duration: float | None = None
    attempts: int = 0


@dataclass(slots=True)
class ClassifiedTrack:
    plan: TrackPlan
    status: str
    reason: str
    source_path: Path | None = None
    actual_size: int | None = None
    actual_duration: float | None = None

    def to_result(self) -> TrackResult:
        return TrackResult(
            track_index=self.plan.index,
            title=self.plan.title,
            output_path=str(self.plan.output_path),
            status=self.status,
            reason=self.reason,
            expected_size=self.plan.expected_size,
            actual_size=self.actual_size,
            expected_duration=self.plan.expected_duration,
            actual_duration=self.actual_duration,
        )


@dataclass(slots=True)
class DownloadEvent:
    kind: str
    message: str = ""
    track_index: int | None = None
    title: str = ""
    status: str = ""
    total_tracks: int | None = None
    completed_tracks: int | None = None
    bytes_downloaded: int | None = None
    bytes_total: int | None = None


@dataclass(slots=True)
class RunSummary:
    page_url: str
    output_dir: str
    summary_path: str
    dry_run: bool
    workers: int
    counts: dict[str, int]
    results: list[TrackResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_url": self.page_url,
            "output_dir": self.output_dir,
            "summary_path": self.summary_path,
            "dry_run": self.dry_run,
            "workers": self.workers,
            "counts": self.counts,
            "results": [asdict(result) for result in self.results],
        }


ProgressCallback = Callable[[DownloadEvent], None]


class DownloadError(RuntimeError):
    pass


class CancelledDownload(DownloadError):
    pass


class SessionRegistry:
    def __init__(self) -> None:
        self._local = threading.local()
        self._lock = threading.Lock()
        self._sessions: list[requests.Session] = []

    def get(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = build_http_session()
            self._local.session = session
            with self._lock:
                self._sessions.append(session)
        return session

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions)
            self._sessions.clear()
        for session in sessions:
            try:
                session.close()
            except Exception:
                pass


def emit(callback: ProgressCallback | None, kind: str, **kwargs) -> None:
    if callback is None:
        return
    callback(DownloadEvent(kind=kind, **kwargs))


def set_abort_if_needed(stop_event: threading.Event) -> None:
    if stop_event.is_set():
        raise CancelledDownload("Cancelled.")


def build_http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    if Retry is not None:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "HEAD"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return session


def normalize_page_url(url: str, allow_insecure_http: bool) -> tuple[str, str]:
    cleaned = url.strip()
    if not cleaned:
        raise DownloadError("A page URL is required.")
    parts = urllib.parse.urlsplit(cleaned)
    if parts.scheme not in {"https", "http"}:
        raise DownloadError("Only http/https URLs are supported.")
    if parts.scheme == "http" and not allow_insecure_http:
        raise DownloadError("Refusing insecure http URL without --allow-http.")
    if not parts.netloc:
        raise DownloadError("Invalid URL: missing host.")
    normalized = urllib.parse.urlunsplit(parts)
    base_url = f"{parts.scheme}://{parts.netloc}"
    return normalized, base_url


def normalize_relpath(value: str) -> str:
    decoded = urllib.parse.unquote(str(value)).replace("\\", "/").strip()
    parts: list[str] = []
    for part in decoded.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise DownloadError(f"Unsafe path component in {value!r}")
        parts.append(part)
    if not parts:
        raise DownloadError(f"Unable to build a safe relative path from {value!r}")
    return "/".join(parts)


def natural_sort_key(value: str) -> tuple:
    tokens = re.split(r"(\d+)", value.lower())
    key: list[object] = []
    for token in tokens:
        if token.isdigit():
            key.append(int(token))
        else:
            key.append(token)
    return tuple(key)


def normalize_sortable_relpath(relpath: str) -> str:
    path = PurePosixPath(relpath)
    stem = path.stem
    match = re.match(r"^(?P<prefix>\d+(?:\.\d+)*)\.(?:\s*(?P<rest>.*))?$", stem)
    if not match:
        return relpath
    prefix = match.group("prefix")
    rest = match.group("rest") or ""
    normalized_prefix = ".".join(segment.zfill(2) for segment in prefix.split("."))
    filename = f"{normalized_prefix}. {rest.strip()}{path.suffix}" if rest else f"{normalized_prefix}{path.suffix}"
    if str(path.parent) == ".":
        return filename
    return str(path.parent / filename)


def cache_path_for(url: str, cache_dir: Path) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


def read_html_from_disk(html_file: Path) -> str:
    if not html_file.exists():
        raise DownloadError(f"HTML file does not exist: {html_file}")
    html = html_file.read_text(encoding="utf-8")
    if len(html) < MIN_CACHE_HTML_BYTES:
        raise DownloadError(f"HTML file looks too small to be valid: {html_file}")
    return html


def fetch_page_html(
    page_url: str,
    config: AppConfig,
    callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> str:
    if stop_event is None:
        stop_event = threading.Event()
    set_abort_if_needed(stop_event)
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_path_for(page_url, config.cache_dir)

    if config.use_cache and not config.force_refresh and cache_path.exists():
        cached = cache_path.read_text(encoding="utf-8")
        if len(cached) >= MIN_CACHE_HTML_BYTES:
            emit(callback, "info", message=f"Using cached HTML: {cache_path}")
            return cached
        emit(callback, "warning", message=f"Ignoring tiny cached HTML: {cache_path}")

    emit(callback, "info", message=f"Fetching page HTML: {page_url}")
    with build_http_session() as session:
        response = session.get(page_url, timeout=config.timeout)
        response.raise_for_status()
        html = response.text
    if len(html) < MIN_CACHE_HTML_BYTES:
        raise DownloadError("Fetched HTML looks incomplete.")
    if config.use_cache:
        cache_path.write_text(html, encoding="utf-8")
        emit(callback, "info", message=f"Cached HTML at {cache_path}")
    return html


def extract_canonical_url(html_text: str) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    canonical = soup.select_one("link[rel='canonical']")
    href = canonical.get("href") if canonical else None
    return href.strip() if href else None


def parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def parse_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def source_path_to_relpath(source_path: str) -> str:
    decoded = urllib.parse.unquote(source_path).lstrip("/")
    parts = decoded.split("/")
    if len(parts) >= 3 and parts[0] == "download":
        return normalize_relpath("/".join(parts[2:]))
    return normalize_relpath(decoded)


def detect_common_directory(relpaths: list[str]) -> str:
    if not relpaths:
        return ""
    directories = [str(PurePosixPath(path).parent) for path in relpaths]
    if any(directory == "." for directory in directories):
        return ""
    common = posixpath.commonpath(directories)
    if common in {"", "."}:
        return ""
    return normalize_relpath(common)


def apply_prefix_rules(original_relpath: str, common_prefix: str, config: AppConfig) -> str:
    relpath = original_relpath
    override = config.prefix_override.strip()
    if override:
        normalized_override = normalize_relpath(override)
        if relpath == normalized_override:
            relpath = PurePosixPath(relpath).name
        elif relpath.startswith(normalized_override + "/"):
            relpath = relpath[len(normalized_override) + 1 :]
    if config.strip_common_prefix and common_prefix:
        if relpath == common_prefix:
            relpath = PurePosixPath(relpath).name
        elif relpath.startswith(common_prefix + "/"):
            relpath = relpath[len(common_prefix) + 1 :]
    if config.normalize_sort_names:
        relpath = normalize_sortable_relpath(relpath)
    return normalize_relpath(relpath)


def resolve_output_path(output_dir: Path, relative_path: str) -> Path:
    target = output_dir.joinpath(*PurePosixPath(relative_path).parts)
    resolved_output_dir = output_dir.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_output_dir != resolved_target and resolved_output_dir not in resolved_target.parents:
        raise DownloadError(f"Unsafe output path escaped output dir: {relative_path}")
    return target


def parse_tracks_from_html(
    html_text: str,
    base_url: str,
    config: AppConfig,
    callback: ProgressCallback | None = None,
) -> list[TrackPlan]:
    soup = BeautifulSoup(html_text, "html.parser")
    player = soup.select_one("play-av")
    if player is None:
        raise DownloadError("Could not find the playlist player element.")
    playlist_raw = player.get("playlist")
    if not playlist_raw:
        raise DownloadError("Could not find the embedded playlist JSON.")
    try:
        playlist = json.loads(playlist_raw)
    except json.JSONDecodeError as exc:
        raise DownloadError(f"Failed to decode playlist JSON: {exc}") from exc

    metadata_input = soup.select_one("input.js-ia-metadata")
    file_lookup: dict[str, dict] = {}
    if metadata_input and metadata_input.get("value"):
        try:
            metadata = json.loads(metadata_input.get("value"))
        except json.JSONDecodeError:
            metadata = {}
        for file_entry in metadata.get("files", []):
            name = file_entry.get("name")
            if isinstance(name, str) and name.lower().endswith(".mp3"):
                file_lookup[normalize_relpath(name)] = file_entry

    original_relpaths: list[str] = []
    raw_tracks: list[tuple[dict, str]] = []
    for item in playlist:
        sources = item.get("sources") or []
        source_entry = sources[0] if sources else None
        source_path = source_entry.get("file") if isinstance(source_entry, dict) else None
        if not source_path:
            raise DownloadError("Playlist entry is missing an audio source URL.")
        original_relpath = normalize_relpath(item.get("orig") or source_path_to_relpath(source_path))
        original_relpaths.append(original_relpath)
        raw_tracks.append((item, original_relpath))

    common_prefix = detect_common_directory(original_relpaths)
    output_relpaths = [apply_prefix_rules(path, common_prefix, config) for path in original_relpaths]
    legacy_config = AppConfig(**{**asdict(config), "normalize_sort_names": False})
    legacy_relpaths = [apply_prefix_rules(path, common_prefix, legacy_config) for path in original_relpaths]
    if len(set(output_relpaths)) != len(output_relpaths):
        emit(callback, "warning", message="Path normalization caused collisions, using original names instead.")
        output_relpaths = [normalize_relpath(path) for path in original_relpaths]
        legacy_relpaths = list(output_relpaths)

    plans: list[TrackPlan] = []
    for index, ((item, original_relpath), output_relpath, legacy_relpath) in enumerate(
        zip(raw_tracks, output_relpaths, legacy_relpaths), start=1
    ):
        source_path = (item.get("sources") or [{}])[0].get("file")
        source_url = urllib.parse.urljoin(base_url, source_path)
        file_meta = file_lookup.get(original_relpath, {})
        title = str(item.get("title") or PurePosixPath(output_relpath).stem)
        plans.append(
            TrackPlan(
                index=index,
                title=title,
                source_url=source_url,
                source_path=source_path,
                original_relpath=original_relpath,
                output_relpath=output_relpath,
                output_path=resolve_output_path(config.output_dir, output_relpath),
                legacy_output_relpath=legacy_relpath if legacy_relpath != output_relpath else None,
                legacy_output_path=resolve_output_path(config.output_dir, legacy_relpath) if legacy_relpath != output_relpath else None,
                expected_size=parse_int(file_meta.get("size")),
                expected_duration=parse_float(item.get("duration")) or parse_float(file_meta.get("length")),
                md5=file_meta.get("md5"),
                sha1=file_meta.get("sha1"),
            )
        )

    plans.sort(key=lambda item: natural_sort_key(item.output_relpath))
    emit(callback, "planned", message=f"Planned {len(plans)} tracks.", total_tracks=len(plans))
    return plans


def probe_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    process = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0 or not process.stdout.strip():
        return None
    try:
        payload = json.loads(process.stdout)
        return parse_float(payload.get("format", {}).get("duration"))
    except json.JSONDecodeError:
        return None


def verify_existing_file(track: TrackPlan, config: AppConfig) -> tuple[bool, str, int | None, float | None]:
    path = track.output_path
    if not path.exists():
        return False, "missing", None, None
    if not path.is_file():
        return False, "not a file", None, None
    actual_size = path.stat().st_size
    actual_duration: float | None = None
    if track.expected_size is not None and actual_size != track.expected_size:
        actual_duration = probe_duration_seconds(path)
        if track.expected_duration is not None and actual_duration is not None:
            return False, f"size mismatch ({actual_size} != {track.expected_size}), duration {actual_duration:.2f}s", actual_size, actual_duration
        return False, f"size mismatch ({actual_size} != {track.expected_size})", actual_size, actual_duration
    if track.expected_duration is not None:
        actual_duration = probe_duration_seconds(path)
        if actual_duration is not None:
            delta = abs(actual_duration - track.expected_duration)
            if delta > config.duration_tolerance_seconds:
                return False, f"duration mismatch ({actual_duration:.2f}s != {track.expected_duration:.2f}s)", actual_size, actual_duration
    return True, "verified", actual_size, actual_duration


def verify_downloaded_part(
    part_path: Path,
    track: TrackPlan,
    config: AppConfig,
    response_size: int | None,
) -> tuple[bool, str, int | None, float | None]:
    actual_size = part_path.stat().st_size if part_path.exists() else None
    expected_size = track.expected_size or response_size
    if expected_size is not None and actual_size is not None and actual_size != expected_size:
        return False, f"downloaded size mismatch ({actual_size} != {expected_size})", actual_size, None
    actual_duration: float | None = None
    if config.verify_after_download and track.expected_duration is not None:
        actual_duration = probe_duration_seconds(part_path)
        if actual_duration is not None:
            delta = abs(actual_duration - track.expected_duration)
            if delta > config.duration_tolerance_seconds:
                return False, f"downloaded duration mismatch ({actual_duration:.2f}s != {track.expected_duration:.2f}s)", actual_size, actual_duration
    return True, "download verified", actual_size, actual_duration


def classify_track(track: TrackPlan, config: AppConfig) -> ClassifiedTrack:
    source_path = track.output_path if track.output_path.exists() else None
    if source_path is None and track.legacy_output_path and track.legacy_output_path.exists():
        source_path = track.legacy_output_path
    if source_path is None:
        return ClassifiedTrack(plan=track, status="pending-download", reason="file missing", source_path=None)

    original_target = track.output_path
    if source_path != original_target:
        track.output_path = source_path

    if not config.verify_existing:
        actual_size = source_path.stat().st_size
        track.output_path = original_target
        return ClassifiedTrack(
            plan=track,
            status="skipped",
            reason="exists and verification disabled",
            source_path=source_path,
            actual_size=actual_size,
        )
    ok, reason, actual_size, actual_duration = verify_existing_file(track, config)
    track.output_path = original_target
    if ok:
        return ClassifiedTrack(
            plan=track,
            status="skipped",
            reason=reason,
            source_path=source_path,
            actual_size=actual_size,
            actual_duration=actual_duration,
        )
    return ClassifiedTrack(
        plan=track,
        status="pending-redownload",
        reason=f"existing file invalid: {reason}",
        source_path=source_path,
        actual_size=actual_size,
        actual_duration=actual_duration,
    )


def classify_tracks(
    tracks: list[TrackPlan],
    config: AppConfig,
    callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> list[ClassifiedTrack]:
    if stop_event is None:
        stop_event = threading.Event()
    total = len(tracks)
    classified: list[ClassifiedTrack] = []
    for idx, track in enumerate(tracks, start=1):
        set_abort_if_needed(stop_event)
        item = classify_track(track, config)
        classified.append(item)
        emit(
            callback,
            "scan-progress",
            completed_tracks=idx,
            total_tracks=total,
            message=f"Scanned {idx}/{total}",
        )
    counts = Counter(item.status for item in classified)
    emit(
        callback,
        "scan-summary",
        message=(
            f"Scan complete. Skip {counts.get('skipped', 0)}, "
            f"download {counts.get('pending-download', 0)}, "
            f"redownload {counts.get('pending-redownload', 0)}."
        ),
        total_tracks=total,
        completed_tracks=total,
    )
    return classified


def migrate_sorted_name_if_needed(classified: ClassifiedTrack, config: AppConfig, callback: ProgressCallback | None = None) -> None:
    source_path = classified.source_path
    target_path = classified.plan.output_path
    if source_path is None or source_path == target_path:
        return
    if config.dry_run:
        classified.reason = f"{classified.reason}; would rename {source_path.name} -> {target_path.name}"
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()
    source_path.replace(target_path)
    classified.source_path = target_path
    classified.reason = f"{classified.reason}; renamed to sorted filename"
    emit(callback, "info", message=f"Renamed {source_path.name} -> {target_path.name}")


def download_track(
    classified: ClassifiedTrack,
    config: AppConfig,
    sessions: SessionRegistry,
    stop_event: threading.Event,
    callback: ProgressCallback | None = None,
) -> TrackResult:
    track = classified.plan
    set_abort_if_needed(stop_event)
    track.output_path.parent.mkdir(parents=True, exist_ok=True)
    redownload = classified.status == "pending-redownload"
    old_source_path = classified.source_path if classified.source_path and classified.source_path != track.output_path else None
    if config.dry_run:
        planned_status = "would-redownload" if redownload else "would-download"
        emit(callback, "track-finished", track_index=track.index, title=track.title, status=planned_status, message=classified.reason)
        return TrackResult(
            track_index=track.index,
            title=track.title,
            output_path=str(track.output_path),
            status=planned_status,
            reason=classified.reason,
            expected_size=track.expected_size,
            expected_duration=track.expected_duration,
        )

    session = sessions.get()
    attempts = 0
    part_path = track.output_path.with_name(track.output_path.name + ".part")
    if part_path.exists():
        part_path.unlink()

    for attempt in range(1, config.retries + 1):
        attempts = attempt
        set_abort_if_needed(stop_event)
        try:
            if part_path.exists():
                part_path.unlink()
            emit(
                callback,
                "track-started",
                track_index=track.index,
                title=track.title,
                status="redownloading" if redownload else "downloading",
                message=classified.reason,
            )
            bytes_written = 0
            last_progress_emit = 0.0
            with session.get(track.source_url, timeout=config.timeout, stream=True) as response:
                response.raise_for_status()
                header_size = parse_int(response.headers.get("Content-Length"))
                with part_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=config.chunk_size):
                        set_abort_if_needed(stop_event)
                        if not chunk:
                            continue
                        handle.write(chunk)
                        bytes_written += len(chunk)
                        now = time.monotonic()
                        if now - last_progress_emit >= 0.2:
                            emit(
                                callback,
                                "track-progress",
                                track_index=track.index,
                                title=track.title,
                                status="downloading",
                                bytes_downloaded=bytes_written,
                                bytes_total=track.expected_size or header_size,
                            )
                            last_progress_emit = now
            ok, reason, actual_size, actual_duration = verify_downloaded_part(part_path, track, config, header_size)
            if not ok:
                raise DownloadError(reason)
            part_path.replace(track.output_path)
            if old_source_path and old_source_path.exists():
                old_source_path.unlink()
            if config.delay_seconds > 0:
                time.sleep(config.delay_seconds)
            status = "redownloaded" if redownload else "downloaded"
            emit(callback, "track-finished", track_index=track.index, title=track.title, status=status, message=reason)
            return TrackResult(
                track_index=track.index,
                title=track.title,
                output_path=str(track.output_path),
                status=status,
                reason=reason,
                expected_size=track.expected_size,
                actual_size=actual_size,
                expected_duration=track.expected_duration,
                actual_duration=actual_duration,
                attempts=attempts,
            )
        except CancelledDownload:
            if part_path.exists():
                part_path.unlink()
            raise
        except Exception as exc:
            if part_path.exists():
                part_path.unlink()
            if attempt >= config.retries:
                message = f"{exc}"
                emit(callback, "track-finished", track_index=track.index, title=track.title, status="failed", message=message)
                return TrackResult(
                    track_index=track.index,
                    title=track.title,
                    output_path=str(track.output_path),
                    status="failed",
                    reason=message,
                    expected_size=track.expected_size,
                    expected_duration=track.expected_duration,
                    attempts=attempts,
                )
            emit(callback, "warning", message=f"Retrying #{track.index:02d} after error: {exc}")
            time.sleep(max(config.reconnect_wait_seconds, min(6.0, float(attempt))))
    raise AssertionError("unreachable")


def prepare_job(
    config: AppConfig,
    callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> tuple[str, list[TrackPlan]]:
    if stop_event is None:
        stop_event = threading.Event()
    if config.html_file:
        html_text = read_html_from_disk(config.html_file)
        page_url = config.page_url or extract_canonical_url(html_text)
        if not page_url:
            raise DownloadError("HTML file did not contain a canonical URL and no --url was provided.")
        normalized_url, base_url = normalize_page_url(page_url, config.allow_insecure_http)
    else:
        normalized_url, base_url = normalize_page_url(config.page_url, config.allow_insecure_http)
        html_text = fetch_page_html(normalized_url, config, callback=callback, stop_event=stop_event)
    tracks = parse_tracks_from_html(html_text, base_url, config, callback=callback)
    return normalized_url, tracks


def run_downloads(
    config: AppConfig,
    callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> RunSummary:
    if stop_event is None:
        stop_event = threading.Event()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    page_url, tracks = prepare_job(config, callback=callback, stop_event=stop_event)
    workers = config.resolved_workers()
    classified = classify_tracks(tracks, config, callback=callback, stop_event=stop_event)
    for item in classified:
        if item.status == "skipped":
            migrate_sorted_name_if_needed(item, config, callback=callback)
    queued = [item for item in classified if item.status in {"pending-download", "pending-redownload"}]
    results: list[TrackResult] = [item.to_result() for item in classified if item.status == "skipped"]
    counts: Counter[str] = Counter(result.status for result in results)
    sessions = SessionRegistry()
    completed = len(results)
    total_work = len(queued)

    emit(
        callback,
        "info",
        message=(
            f"Scan done. {len(results)} skipped, {sum(item.status == 'pending-redownload' for item in queued)} redownloads, "
            f"{sum(item.status == 'pending-download' for item in queued)} fresh downloads."
        ),
        total_tracks=len(tracks),
        completed_tracks=len(tracks),
    )

    try:
        if total_work == 0:
            emit(callback, "overall-progress", completed_tracks=0, total_tracks=0, message="Nothing to download.")
        else:
            emit(callback, "overall-progress", completed_tracks=0, total_tracks=total_work, message=f"0/{total_work} completed")
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(download_track, item, config, sessions, stop_event, callback) for item in queued]
                try:
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        results.append(result)
                        counts[result.status] += 1
                        completed += 1
                        emit(
                            callback,
                            "overall-progress",
                            completed_tracks=completed - len([r for r in results if r.status == "skipped"]),
                            total_tracks=total_work,
                            message=f"{completed - counts.get('skipped', 0)}/{total_work} completed",
                        )
                except BaseException:
                    stop_event.set()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
    finally:
        sessions.close_all()

    results.sort(key=lambda item: natural_sort_key(Path(item.output_path).name))
    summary = RunSummary(
        page_url=page_url,
        output_dir=str(config.output_dir),
        summary_path=str(config.summary_path),
        dry_run=config.dry_run,
        workers=workers,
        counts=dict(counts),
        results=results,
    )
    config.summary_path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    emit(callback, "summary", message=f"Summary written to {config.summary_path}", total_tracks=total_work, completed_tracks=completed)
    return summary


class ConsoleReporter:
    def __call__(self, event: DownloadEvent) -> None:
        if event.kind == "track-progress":
            return
        if event.kind in {"overall-progress", "scan-progress"}:
            print(f"[PROGRESS] {event.message}")
            return
        if event.kind == "track-started":
            print(f"[START] #{event.track_index:02d} {event.title}")
            return
        if event.kind == "track-finished":
            print(f"[{event.status.upper()}] #{event.track_index:02d} {event.title} - {event.message}")
            return
        if event.message:
            print(f"[{event.kind.upper()}] {event.message}")


def parse_path_input(value: str, default: Path) -> Path:
    text = value.strip()
    if not text:
        return default
    return Path(text).expanduser()


def bool_to_select(value: bool) -> str:
    return "on" if value else "off"


def select_to_bool(value: object) -> bool:
    return str(value) == "on"


def speed_help_text(speed: str, workers: int | None) -> str:
    if workers is not None:
        return f"Manual override: {workers} worker(s)"
    return f"{speed.capitalize()} preset: {SPEED_PRESETS.get(speed, 0)} worker(s)"


def read_system_clipboard() -> str:
    if sys.platform == "darwin":
        process = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
        return process.stdout.strip() if process.returncode == 0 else ""
    return ""


def looks_like_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_prefetch_candidates(url: str, mode: str) -> list[str]:
    cleaned = url.strip()
    if not looks_like_url(cleaned):
        return []
    if mode == "off":
        return []
    if mode == "exact":
        return [cleaned]

    parsed = urllib.parse.urlsplit(cleaned)
    host = parsed.netloc
    trimmed_query = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))
    toggled_scheme = urllib.parse.urlunsplit(
        ("https" if parsed.scheme == "http" else "http", parsed.netloc, parsed.path, parsed.query, parsed.fragment)
    )
    candidates = [cleaned, trimmed_query, toggled_scheme]
    if host.startswith("www."):
        candidates.append(urllib.parse.urlunsplit((parsed.scheme, host[4:], parsed.path, parsed.query, parsed.fragment)))
    else:
        candidates.append(urllib.parse.urlunsplit((parsed.scheme, f"www.{host}", parsed.path, parsed.query, parsed.fragment)))

    seen: list[str] = []
    for item in candidates:
        normalized = item.rstrip("/") or item
        if normalized not in seen and looks_like_url(normalized):
            seen.append(normalized)
    return seen[:3]


def ping_candidate(url: str, timeout: int) -> tuple[bool, str]:
    try:
        with build_http_session() as session:
            response = session.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code in {405, 403}:
                response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
            ok = 200 <= response.status_code < 400
            final_url = str(response.url) if getattr(response, "url", None) else url
            return ok, f"{response.status_code} -> {final_url}"
    except Exception as exc:
        return False, str(exc)


def load_custom_css(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        resolved = path.expanduser()
        if resolved.exists():
            return "\n" + resolved.read_text(encoding="utf-8")
    except Exception:
        return ""
    return ""


def config_from_args(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        page_url=args.url or "",
        output_dir=Path(args.output_dir).expanduser(),
        cache_dir=Path(args.cache_dir).expanduser(),
        html_file=Path(args.html_file).expanduser() if args.html_file else None,
        speed=args.speed,
        workers=args.workers,
        retries=args.retries,
        timeout=args.timeout,
        delay_seconds=args.delay,
        chunk_size=args.chunk_size,
        duration_tolerance_seconds=args.duration_tolerance,
        reconnect_wait_seconds=args.reconnect_wait,
        autopaste_enabled=args.autopaste,
        autopaste_interval_seconds=args.autopaste_interval,
        prefetch_ping_mode=args.prefetch_ping_mode,
        verify_existing=args.verify_existing,
        verify_after_download=args.verify_after_download,
        strip_common_prefix=args.strip_common_prefix,
        normalize_sort_names=args.normalize_sort_names,
        prefix_override=args.prefix_override or "",
        custom_css_path=Path(args.custom_css).expanduser() if args.custom_css else None,
        use_cache=args.use_cache,
        force_refresh=args.force_refresh,
        allow_insecure_http=args.allow_http,
        dry_run=args.dry_run,
        summary_filename=args.summary_filename,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="downloader v3")
    subparsers = parser.add_subparsers(dest="command")

    def add_common_arguments(target: argparse.ArgumentParser) -> None:
        target.add_argument("--url", help="Page URL containing the embedded playlist.")
        target.add_argument("--html-file", help="Read a previously saved HTML file instead of fetching.")
        target.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Download directory.")
        target.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="HTML cache directory.")
        target.add_argument("--speed", choices=sorted(SPEED_PRESETS), default="balanced", help="Worker preset.")
        target.add_argument("--workers", type=int, help="Manual worker override.")
        target.add_argument("--retries", type=int, default=4, help="Retries per file.")
        target.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
        target.add_argument("--delay", type=float, default=0.25, help="Delay after each successful download.")
        target.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Streaming chunk size in bytes.")
        target.add_argument("--reconnect-wait", type=float, default=DEFAULT_RECONNECT_WAIT, help="Base wait between retries.")
        target.add_argument("--autopaste", action="store_true", help="Poll the system clipboard for URLs and fill the URL input.")
        target.add_argument("--autopaste-interval", type=float, default=DEFAULT_AUTOPASTE_INTERVAL, help="Clipboard poll interval in seconds.")
        target.add_argument("--prefetch-ping-mode", choices=["off", "exact", "fuzzy"], default="exact", help="Ping clipboard URLs before use.")
        target.add_argument("--duration-tolerance", type=float, default=3.0, help="Allowed duration drift in seconds.")
        target.add_argument("--prefix-override", default="", help="Manual prefix to strip from output paths.")
        target.add_argument("--custom-css", help="Optional CSS file appended to the Textual app style.")
        target.add_argument("--summary-filename", default=DEFAULT_SUMMARY_FILENAME, help="Summary JSON filename.")
        target.add_argument("--allow-http", action="store_true", help="Allow insecure http URLs.")
        target.add_argument("--dry-run", action="store_true", help="Plan actions without downloading.")
        target.add_argument("--force-refresh", action="store_true", help="Ignore cached HTML and refetch.")
        target.add_argument("--no-cache", dest="use_cache", action="store_false", help="Disable HTML caching.")
        target.add_argument("--no-verify-existing", dest="verify_existing", action="store_false", help="Skip verification of existing files.")
        target.add_argument("--no-post-verify", dest="verify_after_download", action="store_false", help="Do not probe duration after each download.")
        target.add_argument("--no-strip-common-prefix", dest="strip_common_prefix", action="store_false", help="Keep common leading directory names.")
        target.add_argument("--no-sort-names", dest="normalize_sort_names", action="store_false", help="Do not zero-pad dotted number prefixes in filenames.")
        target.set_defaults(
            use_cache=True,
            verify_existing=True,
            verify_after_download=True,
            strip_common_prefix=True,
            normalize_sort_names=True,
        )

    run_parser = subparsers.add_parser("run", help="Run without the Textual UI.")
    add_common_arguments(run_parser)
    ui_parser = subparsers.add_parser("ui", help="Launch the Textual UI.")
    add_common_arguments(ui_parser)
    return parser


def create_textual_app(initial_config: AppConfig):
    try:
        from textual import on, work
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, Footer, Header, Input, Log, ProgressBar, Select, Static
    except ImportError as exc:
        raise DownloadError(
            "Textual is not installed. Install it with `python3 -m pip install textual` or use `main.py run`."
        ) from exc

    class LabeledField(Vertical):
        def __init__(self, label: str, widget, classes: str = "field-main") -> None:
            super().__init__(classes=classes)
            self._label_text = label
            self._widget = widget

        def compose(self) -> ComposeResult:
            yield Static(self._label_text, classes="field-label-mini")
            yield self._widget

    custom_css = load_custom_css(initial_config.custom_css_path)

    class MainDownloaderApp(App[None]):
        CSS = UI_CSS + """
        #main { padding: 0 1; }
        #hero { height: 3; padding: 0 1; margin-bottom: 0; border: heavy $accent; }
        .hero-title { text-style: bold; }
        .hero-subtitle { color: $text-muted; }
        #stats { height: 3; margin-bottom: 0; }
        .stat-card { padding: 0 1; border: none; background: $surface-darken-1; }
        .stat-title { width: 12; }
        #control-deck { margin-bottom: 0; }
        .panel { padding: 0 1; margin-bottom: 0; border: heavy $surface-lighten-1; }
        .panel-title { margin-bottom: 0; }
        .field-row { margin-bottom: 0; height: 4; }
        .field-main { width: 1fr; min-width: 24; margin-right: 1; }
        .field-side { width: 18; min-width: 16; margin-right: 1; }
        .field-wide { width: 24; min-width: 20; margin-right: 1; }
        .field-label-mini { height: 1; margin-bottom: 0; color: $text-muted; }
        Input, Select, Button, #workers_hint {
            height: 3;
        }
        Button {
            width: auto;
            min-width: 12;
            padding: 0 1;
        }
        #actions { height: 3; margin-bottom: 0; }
        #summary { height: 4; padding: 0 1; margin-bottom: 0; }
        #progress { margin-bottom: 0; }
        Log { border: heavy $surface-lighten-1; }
        .rainbow-focus-0, .rainbow-focus-1, .rainbow-focus-2, .rainbow-focus-3, .rainbow-focus-4, .rainbow-focus-5 {
            text-style: bold;
        }
        .rainbow-focus-0 { border: heavy #ff4d6d; }
        .rainbow-focus-1 { border: heavy #ffb703; }
        .rainbow-focus-2 { border: heavy #80ed99; }
        .rainbow-focus-3 { border: heavy #4cc9f0; }
        .rainbow-focus-4 { border: heavy #4361ee; }
        .rainbow-focus-5 { border: heavy #b5179e; }
        """ + custom_css
        BINDINGS = [
            ("ctrl+c", "request_exit", "Quit"),
            ("tab", "focus_next_control", "Next"),
            ("shift+tab", "focus_prev_control", "Prev"),
            ("j", "focus_next_control", "Next"),
            ("k", "focus_prev_control", "Prev"),
            ("down", "focus_next_control", "Next"),
            ("up", "focus_prev_control", "Prev"),
            ("ctrl+v", "paste_clipboard", "Paste"),
            ("f", "trigger_prefetch", "Prefetch"),
            ("s", "start_run", "Start"),
            ("x", "stop_run", "Stop"),
        ]
        FOCUS_CLASSES = [f"rainbow-focus-{index}" for index in range(6)]
        FOCUS_SELECTOR = "Input, Select, Button"

        def __init__(self, seed_config: AppConfig) -> None:
            super().__init__()
            self.seed_config = seed_config
            self.stop_event = threading.Event()
            self.last_clipboard_text = ""
            self.last_prefetch_key = ""
            self.autopaste_timer = None
            self.focus_timer = None
            self.focus_color_index = 0

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical(id="main"):
                with Horizontal(id="hero"):
                    yield Static("unarchive-V3 // CONTROL DECK", classes="hero-title field-side")
                    yield Static("Scan-first. Fast focus. Clipboard aware. QA visible.", classes="hero-subtitle field-main")
                with Horizontal(id="stats"):
                    with Horizontal(classes="stat-card"):
                        yield Static("Clip", classes="stat-title")
                        yield Static("idle", id="stat_clipboard", classes="stat-value")
                    with Horizontal(classes="stat-card"):
                        yield Static("Ping", classes="stat-title")
                        yield Static("off", id="stat_prefetch", classes="stat-value")
                    with Horizontal(classes="stat-card"):
                        yield Static("Queue", classes="stat-title")
                        yield Static("0", id="stat_queue", classes="stat-value")
                    with Horizontal(classes="stat-card"):
                        yield Static("Workers", classes="stat-title")
                        yield Static(speed_help_text(self.seed_config.speed, self.seed_config.workers), id="stat_workers", classes="stat-value")
                with Vertical(id="control-deck"):
                    with Vertical(classes="panel"):
                        yield Static("Intake", classes="panel-title")
                        with Horizontal(classes="field-row"):
                            yield LabeledField("Page URL", Input(value=self.seed_config.page_url, placeholder="https://...", id="url"), classes="field-main")
                            yield LabeledField("Output path", Input(value=str(self.seed_config.output_dir), placeholder="downloadzz", id="output_dir"), classes="field-main")
                            yield LabeledField("Cached HTML", Input(value=str(self.seed_config.html_file or ""), placeholder="optional", id="html_file"), classes="field-side")
                            yield LabeledField("Cache dir", Input(value=str(self.seed_config.cache_dir), placeholder=".caches", id="cache_dir"), classes="field-side")
                        with Horizontal(classes="field-row"):
                            yield LabeledField("Autopaste", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.autopaste_enabled), id="autopaste_enabled"), classes="field-side")
                            yield LabeledField("Paste every", Input(value=str(self.seed_config.autopaste_interval_seconds), placeholder="1.2", id="autopaste_interval"), classes="field-side")
                            yield LabeledField("Prefetch", Select(PREFETCH_MODE_OPTIONS, value=self.seed_config.prefetch_ping_mode, id="prefetch_ping_mode"), classes="field-side")
                            yield LabeledField("Summary file", Input(value=self.seed_config.summary_filename, placeholder=DEFAULT_SUMMARY_FILENAME, id="summary_filename"), classes="field-side")
                            yield LabeledField("Custom CSS", Input(value=str(self.seed_config.custom_css_path or ""), placeholder="optional css", id="custom_css_path"), classes="field-main")
                    with Vertical(classes="panel"):
                        yield Static("Engine", classes="panel-title")
                        with Horizontal(classes="field-row"):
                            yield LabeledField("Speed", Select([(f"{label.capitalize()} ({count})", label) for label, count in SPEED_PRESETS.items()], value=self.seed_config.speed, id="speed"), classes="field-side")
                            yield LabeledField("Workers", Input(value=str(self.seed_config.workers or ""), placeholder="override", id="workers"), classes="field-side")
                            yield LabeledField("Retries", Input(value=str(self.seed_config.retries), placeholder="4", id="retries"), classes="field-side")
                            yield LabeledField("Timeout", Input(value=str(self.seed_config.timeout), placeholder="30", id="timeout"), classes="field-side")
                            yield LabeledField("Reconnect", Input(value=str(self.seed_config.reconnect_wait_seconds), placeholder="2.0", id="reconnect_wait"), classes="field-side")
                            yield LabeledField("Delay", Input(value=str(self.seed_config.delay_seconds), placeholder="0.25", id="delay"), classes="field-side")
                        with Horizontal(classes="field-row"):
                            yield LabeledField("Chunk size", Input(value=str(self.seed_config.chunk_size), placeholder=str(DEFAULT_CHUNK_SIZE), id="chunk_size"), classes="field-side")
                            yield LabeledField("Duration tol", Input(value=str(self.seed_config.duration_tolerance_seconds), placeholder="3.0", id="duration_tolerance"), classes="field-side")
                            yield LabeledField("Prefix trim", Input(value=self.seed_config.prefix_override, placeholder="optional", id="prefix_override"), classes="field-side")
                            yield LabeledField("Use cache", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.use_cache), id="use_cache"), classes="field-side")
                            yield LabeledField("Refresh", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.force_refresh), id="force_refresh"), classes="field-side")
                            yield LabeledField("Verify", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.verify_existing), id="verify_existing"), classes="field-side")
                        with Horizontal(classes="field-row"):
                            yield LabeledField("Post verify", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.verify_after_download), id="verify_after_download"), classes="field-side")
                            yield LabeledField("Strip common", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.strip_common_prefix), id="strip_common_prefix"), classes="field-side")
                            yield LabeledField("Sort names", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.normalize_sort_names), id="normalize_sort_names"), classes="field-side")
                            yield LabeledField("Allow http", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.allow_insecure_http), id="allow_http"), classes="field-side")
                            yield LabeledField("Dry run", Select(BOOLEAN_SELECT_OPTIONS, value=bool_to_select(self.seed_config.dry_run), id="dry_run"), classes="field-side")
                            yield LabeledField("Worker hint", Static(speed_help_text(self.seed_config.speed, self.seed_config.workers), id="workers_hint"), classes="field-main")
                with Horizontal(id="actions"):
                    yield Button("Paste", id="paste_clipboard", variant="primary")
                    yield Button("Ping", id="prefetch_now", variant="primary")
                    yield Button("CWD", id="use_cwd", variant="default")
                    yield Button("Start", id="start", variant="success")
                    yield Button("Stop", id="stop", variant="warning")
                    yield Button("Quit", id="quit", variant="default")
                with Horizontal(id="summary"):
                    yield Static("Idle", id="status", classes="field-main")
                    yield Static("Ready.", id="counts", classes="field-main")
                yield ProgressBar(total=1, show_eta=False, id="progress")
                yield Log(id="log", highlight=True)
            yield Footer()

        def on_mount(self) -> None:
            self.autopaste_timer = self.set_interval(self.seed_config.autopaste_interval_seconds, self.poll_clipboard, pause=False)
            self.focus_timer = self.set_interval(0.18, self.update_focus_glow, pause=False)
            self.update_worker_hint()
            self.update_prefetch_stat("off")
            self.screen.focus_next(self.FOCUS_SELECTOR)

        def build_config_from_form(self) -> AppConfig:
            workers_text = self.query_one("#workers", Input).value.strip()
            html_file_text = self.query_one("#html_file", Input).value.strip()
            custom_css_text = self.query_one("#custom_css_path", Input).value.strip()
            return AppConfig(
                page_url=self.query_one("#url", Input).value.strip(),
                output_dir=parse_path_input(self.query_one("#output_dir", Input).value, DEFAULT_OUTPUT_DIR),
                cache_dir=parse_path_input(self.query_one("#cache_dir", Input).value, DEFAULT_CACHE_DIR),
                html_file=parse_path_input(html_file_text, Path(".")) if html_file_text else None,
                speed=str(self.query_one("#speed", Select).value or "balanced"),
                workers=int(workers_text) if workers_text else None,
                retries=int(self.query_one("#retries", Input).value.strip() or "4"),
                timeout=int(self.query_one("#timeout", Input).value.strip() or "30"),
                reconnect_wait_seconds=float(self.query_one("#reconnect_wait", Input).value.strip() or str(DEFAULT_RECONNECT_WAIT)),
                autopaste_enabled=select_to_bool(self.query_one("#autopaste_enabled", Select).value),
                autopaste_interval_seconds=float(self.query_one("#autopaste_interval", Input).value.strip() or str(DEFAULT_AUTOPASTE_INTERVAL)),
                prefetch_ping_mode=str(self.query_one("#prefetch_ping_mode", Select).value or "exact"),
                delay_seconds=float(self.query_one("#delay", Input).value.strip() or "0.25"),
                chunk_size=int(self.query_one("#chunk_size", Input).value.strip() or str(DEFAULT_CHUNK_SIZE)),
                duration_tolerance_seconds=float(self.query_one("#duration_tolerance", Input).value.strip() or "3.0"),
                verify_existing=select_to_bool(self.query_one("#verify_existing", Select).value),
                verify_after_download=select_to_bool(self.query_one("#verify_after_download", Select).value),
                strip_common_prefix=select_to_bool(self.query_one("#strip_common_prefix", Select).value),
                normalize_sort_names=select_to_bool(self.query_one("#normalize_sort_names", Select).value),
                prefix_override=self.query_one("#prefix_override", Input).value.strip(),
                custom_css_path=parse_path_input(custom_css_text, Path(".")) if custom_css_text else None,
                use_cache=select_to_bool(self.query_one("#use_cache", Select).value),
                force_refresh=select_to_bool(self.query_one("#force_refresh", Select).value),
                allow_insecure_http=select_to_bool(self.query_one("#allow_http", Select).value),
                dry_run=select_to_bool(self.query_one("#dry_run", Select).value),
                summary_filename=self.query_one("#summary_filename", Input).value.strip() or DEFAULT_SUMMARY_FILENAME,
            )

        def clear_focus_glow(self) -> None:
            for widget in self.query(self.FOCUS_SELECTOR):
                for css_class in self.FOCUS_CLASSES:
                    widget.remove_class(css_class)

        def update_focus_glow(self) -> None:
            focused = self.screen.focused
            self.clear_focus_glow()
            if focused is None:
                return
            css_class = self.FOCUS_CLASSES[self.focus_color_index % len(self.FOCUS_CLASSES)]
            focused.add_class(css_class)
            self.focus_color_index += 1

        def update_worker_hint(self) -> None:
            speed = str(self.query_one("#speed", Select).value or "balanced")
            workers_text = self.query_one("#workers", Input).value.strip()
            workers = int(workers_text) if workers_text.isdigit() else None
            hint = speed_help_text(speed, workers)
            self.query_one("#workers_hint", Static).update(hint)
            self.query_one("#stat_workers", Static).update(hint)

        def update_prefetch_stat(self, text: str) -> None:
            self.query_one("#stat_prefetch", Static).update(text)

        def update_clipboard_stat(self, text: str) -> None:
            self.query_one("#stat_clipboard", Static).update(text)

        def update_queue_stat(self, text: str) -> None:
            self.query_one("#stat_queue", Static).update(text)

        def log_line(self, text: str) -> None:
            self.query_one("#log", Log).write_line(text)

        def focus_next_widget(self) -> None:
            self.screen.focus_next(self.FOCUS_SELECTOR)
            self.update_focus_glow()

        def focus_previous_widget(self) -> None:
            self.screen.focus_previous(self.FOCUS_SELECTOR)
            self.update_focus_glow()

        def action_focus_next_control(self) -> None:
            self.focus_next_widget()

        def action_focus_prev_control(self) -> None:
            self.focus_previous_widget()

        def action_paste_clipboard(self) -> None:
            self.paste_clipboard()

        def action_trigger_prefetch(self) -> None:
            self.prefetch_now()

        def action_start_run(self) -> None:
            self.handle_start()

        def action_stop_run(self) -> None:
            self.handle_stop()

        def apply_event(self, event: DownloadEvent) -> None:
            log = self.query_one("#log", Log)
            status = self.query_one("#status", Static)
            counts = self.query_one("#counts", Static)
            progress = self.query_one("#progress", ProgressBar)
            if event.kind == "planned" and event.total_tracks is not None:
                counts.update(f"Found {event.total_tracks} tracks. Scan in progress.")
                status.update(event.message)
                self.update_queue_stat(str(event.total_tracks))
                return
            if event.kind == "scan-progress":
                progress.update(total=max(1, event.total_tracks or 1), progress=event.completed_tracks or 0)
                status.update(event.message or "Scanning")
                return
            if event.kind == "scan-summary":
                status.update(event.message)
                counts.update(event.message)
                self.update_queue_stat(event.message)
                return
            if event.kind == "overall-progress":
                progress.update(total=max(1, event.total_tracks or 1), progress=event.completed_tracks or 0)
                status.update(event.message or "Working")
                if event.total_tracks is not None:
                    self.update_queue_stat(f"{event.completed_tracks or 0}/{event.total_tracks}")
                return
            if event.kind == "track-progress":
                total = f"/{event.bytes_total}" if event.bytes_total else ""
                status.update(f"#{event.track_index:02d} {event.title} {event.bytes_downloaded or 0}{total} bytes")
                return
            if event.kind == "track-started":
                status.update(f"{event.status.capitalize()} #{event.track_index:02d} {event.title}")
                log.write_line(f"[{event.status.upper()}] #{event.track_index:02d} {event.title}")
                return
            if event.kind == "track-finished":
                status.update(f"{event.status.capitalize()} #{event.track_index:02d} {event.title}")
                log.write_line(f"[{event.status.upper()}] #{event.track_index:02d} {event.title} - {event.message}")
                return
            if event.kind == "summary":
                status.update(event.message)
                log.write_line(f"[SUMMARY] {event.message}")
                return
            if event.message:
                status.update(event.message)
                log.write_line(f"[{event.kind.upper()}] {event.message}")

        def handle_clipboard_candidate(self, value: str, source: str) -> None:
            if not looks_like_url(value):
                return
            self.query_one("#url", Input).value = value
            self.last_clipboard_text = value
            self.update_clipboard_stat("url")
            self.log_line(f"[CLIPBOARD] {source}: {value}")
            mode = str(self.query_one("#prefetch_ping_mode", Select).value or "off")
            if mode != "off":
                self.prefetch_url(value, mode)

        def poll_clipboard(self) -> None:
            try:
                enabled = select_to_bool(self.query_one("#autopaste_enabled", Select).value)
                interval = float(self.query_one("#autopaste_interval", Input).value.strip() or str(DEFAULT_AUTOPASTE_INTERVAL))
                if self.autopaste_timer is not None:
                    self.autopaste_timer.interval = max(0.5, interval)
                if not enabled:
                    self.update_clipboard_stat("off")
                    return
                clipboard_text = read_system_clipboard()
                if not clipboard_text:
                    self.update_clipboard_stat("empty")
                    return
                if clipboard_text == self.last_clipboard_text:
                    return
                self.last_clipboard_text = clipboard_text
                if looks_like_url(clipboard_text):
                    self.handle_clipboard_candidate(clipboard_text, "autopaste")
                else:
                    self.update_clipboard_stat("non-url")
            except Exception as exc:
                self.log_line(f"[AUTOPASTE] {exc}")

        @work(thread=True, exclusive=False)
        def prefetch_url(self, url: str, mode: str) -> None:
            candidates = build_prefetch_candidates(url, mode)
            prefetch_key = f"{mode}:{url}"
            if prefetch_key == self.last_prefetch_key:
                return
            self.last_prefetch_key = prefetch_key
            self.call_from_thread(self.update_prefetch_stat, f"{mode}:{len(candidates)}")
            for index, candidate in enumerate(candidates, start=1):
                ok, detail = ping_candidate(candidate, timeout=5)
                prefix = "OK" if ok else "MISS"
                self.call_from_thread(self.log_line, f"[PREFETCH {index}] {prefix} {candidate} :: {detail}")
                if ok:
                    self.call_from_thread(self.update_prefetch_stat, f"hit {index}")
                    self.call_from_thread(self.apply_event, DownloadEvent(kind="info", message=f"Prefetch hit: {candidate}"))
                    break
            else:
                self.call_from_thread(self.apply_event, DownloadEvent(kind="warning", message="Prefetch found no reachable variant."))

        @on(Select.Changed, "#speed")
        def update_speed_select(self) -> None:
            self.update_worker_hint()

        @on(Input.Changed, "#workers")
        def update_workers_input(self) -> None:
            self.update_worker_hint()

        @on(Button.Pressed, "#paste_clipboard")
        def paste_clipboard(self) -> None:
            text = read_system_clipboard()
            if not text:
                self.apply_event(DownloadEvent(kind="warning", message="Clipboard is empty."))
                return
            self.handle_clipboard_candidate(text, "manual paste")

        @on(Button.Pressed, "#prefetch_now")
        def prefetch_now(self) -> None:
            url = self.query_one("#url", Input).value.strip()
            mode = str(self.query_one("#prefetch_ping_mode", Select).value or "off")
            if not looks_like_url(url):
                self.apply_event(DownloadEvent(kind="warning", message="URL field does not contain a valid URL."))
                return
            if mode == "off":
                self.apply_event(DownloadEvent(kind="warning", message="Prefetch ping mode is off."))
                return
            self.prefetch_url(url, mode)

        @on(Button.Pressed, "#use_cwd")
        def use_current_directory(self) -> None:
            self.query_one("#output_dir", Input).value = str(Path.cwd())

        @on(Button.Pressed, "#start")
        def handle_start(self) -> None:
            self.stop_event = threading.Event()
            self.run_job()

        @on(Button.Pressed, "#stop")
        def handle_stop(self) -> None:
            self.stop_event.set()
            self.apply_event(DownloadEvent(kind="warning", message="Stop requested. Waiting for workers to exit."))

        @on(Button.Pressed, "#quit")
        def handle_quit(self) -> None:
            self.stop_event.set()
            if self.autopaste_timer is not None:
                self.autopaste_timer.pause()
            if self.focus_timer is not None:
                self.focus_timer.pause()
            self.exit()

        def action_request_exit(self) -> None:
            self.stop_event.set()
            if self.autopaste_timer is not None:
                self.autopaste_timer.pause()
            if self.focus_timer is not None:
                self.focus_timer.pause()
            self.exit()

        @work(thread=True, exclusive=True)
        def run_job(self) -> None:
            try:
                config = self.build_config_from_form()
                summary = run_downloads(config, callback=self.forward_event, stop_event=self.stop_event)
                self.call_from_thread(self.apply_event, DownloadEvent(kind="summary", message=f"Done. Counts: {summary.counts}"))
            except CancelledDownload as exc:
                self.call_from_thread(self.apply_event, DownloadEvent(kind="warning", message=str(exc)))
            except Exception as exc:
                self.call_from_thread(self.apply_event, DownloadEvent(kind="error", message=str(exc)))

        def forward_event(self, event: DownloadEvent) -> None:
            self.call_from_thread(self.apply_event, event)

    return MainDownloaderApp(initial_config)


def launch_textual_app(initial_config: AppConfig) -> None:
    create_textual_app(initial_config).run()


def print_summary(summary: RunSummary) -> None:
    print("")
    print("Counts:")
    for status, count in sorted(summary.counts.items()):
        print(f"  {status}: {count}")
    print(f"Summary JSON: {summary.summary_path}")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    if not raw_argv:
        raw_argv = ["ui"]
    elif raw_argv[0] not in {"run", "ui", "-h", "--help"}:
        raw_argv = ["ui", *raw_argv]
    args = parser.parse_args(raw_argv)
    command = args.command or "ui"
    config = config_from_args(args)
    stop_event = threading.Event()
    try:
        if command == "run":
            summary = run_downloads(config, callback=ConsoleReporter(), stop_event=stop_event)
            print_summary(summary)
            return 0 if not summary.counts.get("failed") else 1
        if command == "ui":
            launch_textual_app(config)
            return 0
        parser.error(f"Unknown command: {command}")
        return 2
    except KeyboardInterrupt:
        stop_event.set()
        print("Cancelled by user.")
        return 130
    except CancelledDownload:
        print("Cancelled.")
        return 130
    except DownloadError as exc:
        print(f"Error: {exc}")
        return 2
    except requests.RequestException as exc:
        print(f"Network error: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
