"""Central configuration. Values come from environment variables / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional
    pass


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v not in (None, "") else default


def _float(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v) if v not in (None, "") else default


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".ogv"}
PDF_EXTS = {".pdf"}


def kind_for_ext(ext: str) -> str | None:
    ext = ext.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in PDF_EXTS:
        return "pdf"
    return None


@dataclass
class Settings:
    # Folders
    media_dir: Path = field(default_factory=lambda: Path(os.getenv("MEDIA_DIR", "./media")).resolve())
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "./data")).resolve())

    # Models (all open-source, downloaded once from Hugging Face on first run)
    clip_model: str = os.getenv("CLIP_MODEL", "ViT-B-32")
    clip_pretrained: str = os.getenv("CLIP_PRETRAINED", "laion2b_s34b_b79k")
    text_model: str = os.getenv("TEXT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    caption_model: str = os.getenv("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
    whisper_model: str = os.getenv("WHISPER_MODEL", "tiny")

    caption_beams: int = _int("CAPTION_BEAMS", 3)
    enable_captions: bool = _bool("ENABLE_CAPTIONS", True)
    enable_transcription: bool = _bool("ENABLE_TRANSCRIPTION", True)
    enable_ocr: bool = _bool("ENABLE_OCR", True)  # only used if Tesseract is installed

    # Video sampling
    video_frame_interval: float = _float("VIDEO_FRAME_INTERVAL", 4.0)  # seconds between forced keyframes
    video_max_frames: int = _int("VIDEO_MAX_FRAMES", 16)
    video_max_captions: int = _int("VIDEO_MAX_CAPTIONS", 6)
    video_scene_threshold: float = _float("VIDEO_SCENE_THRESHOLD", 0.35)
    video_max_audio_sec: int = _int("VIDEO_MAX_AUDIO_SEC", 180)

    # PDF
    pdf_max_pages_text: int = _int("PDF_MAX_PAGES_TEXT", 60)
    pdf_max_page_images: int = _int("PDF_MAX_PAGE_IMAGES", 6)
    pdf_chunk_chars: int = _int("PDF_CHUNK_CHARS", 900)

    # Indexing / reliability
    max_attempts: int = _int("MAX_ATTEMPTS", 3)
    max_file_mb: int = _int("MAX_FILE_MB", 2048)
    torch_threads: int = _int("TORCH_THREADS", 0)  # 0 = torch default

    # Search
    default_top_k: int = _int("TOP_K", 24)

    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int("PORT", 8000)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dam.sqlite3"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    def model_signature(self) -> str:
        """Changes when the AI pipeline changes -> assets get re-processed."""
        parts = [
            "v1",
            self.clip_model,
            self.clip_pretrained,
            self.text_model,
            self.caption_model if self.enable_captions else "nocap",
            self.whisper_model if self.enable_transcription else "noasr",
        ]
        return "|".join(parts)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
