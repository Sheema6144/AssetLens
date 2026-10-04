"""AI model wrappers.

All models are open-source, run on CPU, and are loaded lazily (only when first
needed) so the search server starts fast and memory stays low on 8 GB laptops.

  * CLIP (open_clip ViT-B-32, LAION-2B)  -> shared image/text embedding space.
    Lets a text query match pixels directly ("woman with a cat").
  * BLIP base captioner                   -> one-sentence description per image /
    keyframe / brochure page. Searchable as text and shown to the user.
  * all-MiniLM-L6-v2 sentence embedder    -> semantic text space for captions,
    PDF text and video transcripts.
  * faster-whisper (tiny, int8)           -> speech-to-text for videos
    (testimonials, interviews).
  * Tesseract OCR (optional)              -> scanned PDF pages without a text layer.
"""
from __future__ import annotations

import logging
import shutil
import threading
from typing import Sequence

import numpy as np
from PIL import Image

from .config import Settings

log = logging.getLogger("dam.models")


class ModelError(RuntimeError):
    """Raised when a model cannot be loaded or fails on an input."""


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


# Concepts used for CLIP zero-shot tagging. Tags are shown as chips in the UI
# and are added to the keyword index, so they also improve recall.
TAG_VOCAB = [
    "person", "woman", "man", "child", "group of people", "crowd", "family", "couple",
    "cat", "dog", "bird", "horse", "animal",
    "living room", "bedroom", "kitchen", "bathroom", "office", "meeting room", "interior design",
    "modern interior", "furniture", "sofa",
    "house", "apartment building", "residential building", "skyscraper", "city skyline", "street",
    "construction site", "crane", "construction worker", "excavator", "building under construction",
    "road", "car", "traffic", "bicycle", "airplane", "train", "boat",
    "beach", "ocean", "mountain", "forest", "park", "garden", "lake", "river", "snow", "desert",
    "sunset", "night", "aerial view",
    "food", "coffee", "restaurant", "fruit",
    "laptop", "computer", "smartphone", "document", "text", "chart", "map", "logo", "floor plan",
    "person talking to camera", "interview", "presentation", "handshake", "teamwork",
    "sports", "fitness", "yoga", "music", "concert", "wedding", "party",
    "hospital", "school", "classroom", "factory", "warehouse", "shop", "shopping",
    "swimming pool", "real estate", "villa", "hotel", "church", "bridge",
]


def decode_audio_mono16k(path: str, max_sec: int) -> np.ndarray:
    """Decode up to `max_sec` seconds of audio as 16 kHz mono float32 using PyAV.

    Written by hand (instead of faster_whisper.decode_audio) so we can stop early
    for long videos and avoid PyAV version incompatibilities.
    """
    import av

    try:
        container = av.open(path)
    except Exception:  # noqa: BLE001
        return np.zeros(0, np.float32)
    try:
        if not container.streams.audio:
            return np.zeros(0, np.float32)
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        chunks, total, limit = [], 0, max_sec * 16000
        try:
            for frame in container.decode(audio=0):
                for f in resampler.resample(frame):
                    arr = f.to_ndarray().reshape(-1)
                    chunks.append(arr)
                    total += arr.size
                if total >= limit:
                    break
        except Exception as e:  # noqa: BLE001  (damaged audio: use what we decoded)
            log.debug("audio decode stopped early for %s: %s", path, e)
        if not chunks:
            return np.zeros(0, np.float32)
        return (np.concatenate(chunks)[:limit].astype(np.float32) / 32768.0)
    finally:
        container.close()


class Models:
    """Real models. Each loader is thread-safe and only runs once."""

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self._lock = threading.RLock()
        self._clip = None
        self._clip_tok = None
        self._clip_pre = None
        self._text = None
        self._cap = None
        self._asr = None
        self._tag_mat: np.ndarray | None = None
        self.ocr_available = bool(shutil.which("tesseract")) and cfg.enable_ocr

    # ---------------- loading ----------------
    def _torch(self):
        import torch

        if self.cfg.torch_threads > 0:
            torch.set_num_threads(self.cfg.torch_threads)
        return torch

    def _load_clip(self):
        with self._lock:
            if self._clip is None:
                try:
                    import open_clip

                    self._torch()
                    log.info("Loading CLIP %s/%s ...", self.cfg.clip_model, self.cfg.clip_pretrained)
                    model, _, preprocess = open_clip.create_model_and_transforms(
                        self.cfg.clip_model, pretrained=self.cfg.clip_pretrained
                    )
                    model.eval()
                    self._clip, self._clip_pre = model, preprocess
                    self._clip_tok = open_clip.get_tokenizer(self.cfg.clip_model)
                except Exception as e:  # noqa: BLE001
                    raise ModelError(f"Could not load CLIP model: {e}") from e
        return self._clip

    def _load_text(self):
        with self._lock:
            if self._text is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    log.info("Loading text embedder %s ...", self.cfg.text_model)
                    self._text = SentenceTransformer(self.cfg.text_model, device="cpu")
                except Exception as e:  # noqa: BLE001
                    raise ModelError(f"Could not load text model: {e}") from e
        return self._text

    def _load_captioner(self):
        with self._lock:
            if self._cap is None:
                try:
                    from transformers import BlipForConditionalGeneration, BlipProcessor

                    log.info("Loading captioner %s ...", self.cfg.caption_model)
                    proc = BlipProcessor.from_pretrained(self.cfg.caption_model)
                    model = BlipForConditionalGeneration.from_pretrained(self.cfg.caption_model)
                    model.eval()
                    self._cap = (proc, model)
                except Exception as e:  # noqa: BLE001
                    raise ModelError(f"Could not load caption model: {e}") from e
        return self._cap

    def _load_asr(self):
        with self._lock:
            if self._asr is None:
                try:
                    from faster_whisper import WhisperModel

                    log.info("Loading Whisper %s ...", self.cfg.whisper_model)
                    self._asr = WhisperModel(self.cfg.whisper_model, device="cpu", compute_type="int8")
                except Exception as e:  # noqa: BLE001
                    raise ModelError(f"Could not load Whisper model: {e}") from e
        return self._asr

    def warmup(self) -> None:
        """Load the required models up front so a missing model fails the job early."""
        self._load_clip()
        self._load_text()

    # ---------------- inference ----------------
    def clip_image(self, images: Sequence[Image.Image], batch: int = 16) -> np.ndarray:
        model = self._load_clip()
        torch = self._torch()
        out = []
        with torch.no_grad():
            for i in range(0, len(images), batch):
                x = torch.stack([self._clip_pre(im.convert("RGB")) for im in images[i : i + batch]])
                out.append(model.encode_image(x).float().numpy())
        return _norm(np.concatenate(out)) if out else np.zeros((0, 512), np.float32)

    def clip_text(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load_clip()
        torch = self._torch()
        with torch.no_grad():
            toks = self._clip_tok(list(texts))
            return _norm(model.encode_text(toks).float().numpy())

    def text_embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), np.float32)
        m = self._load_text()
        return _norm(m.encode(list(texts), batch_size=32, show_progress_bar=False, convert_to_numpy=True))

    def caption(self, images: Sequence[Image.Image], batch: int = 4) -> list[str]:
        if not self.cfg.enable_captions or not images:
            return [""] * len(images)
        proc, model = self._load_captioner()
        torch = self._torch()
        caps: list[str] = []
        with torch.no_grad():
            for i in range(0, len(images), batch):
                ims = [im.convert("RGB") for im in images[i : i + batch]]
                inputs = proc(images=ims, return_tensors="pt")
                ids = model.generate(**inputs, max_new_tokens=30, num_beams=self.cfg.caption_beams)
                caps.extend(proc.decode(t, skip_special_tokens=True).strip() for t in ids)
        return caps

    def transcribe(self, path: str, max_sec: int) -> str:
        if not self.cfg.enable_transcription:
            return ""
        audio = decode_audio_mono16k(path, max_sec)
        if audio.size < 16000:  # no audio track, or < 1 second
            return ""
        asr = self._load_asr()
        segments, _info = asr.transcribe(audio, vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()

    def ocr(self, image: Image.Image) -> str:
        if not self.ocr_available:
            return ""
        import pytesseract

        return pytesseract.image_to_string(image)

    def tags_for(self, img_vecs: np.ndarray, top: int = 5, min_sim: float = 0.2) -> list[str]:
        """Zero-shot CLIP tags for one asset (mean of its image vectors)."""
        if img_vecs.size == 0:
            return []
        if self._tag_mat is None:
            self._tag_mat = self.clip_text([f"a photo of {t}" for t in TAG_VOCAB])
        v = _norm(img_vecs.mean(axis=0, keepdims=True))[0]
        sims = self._tag_mat @ v
        order = np.argsort(-sims)[:top]
        return [TAG_VOCAB[i] for i in order if sims[i] >= min_sim]


class FakeModels:
    """Tiny deterministic stand-in used by the test-suite (no downloads).

    Images are embedded by their dominant colour; texts by the colour words they
    contain. That is enough to test ranking, fusion and the indexing pipeline.
    """

    COLORS = {"red": (220, 30, 30), "green": (30, 180, 30), "blue": (30, 30, 220),
              "yellow": (230, 220, 30), "black": (10, 10, 10), "white": (245, 245, 245)}

    def __init__(self, cfg: Settings | None = None, fail_captions: bool = False):
        self.cfg = cfg
        self.fail_captions = fail_captions
        self.ocr_available = False
        self.calls = {"clip_image": 0, "caption": 0, "text": 0}

    def warmup(self) -> None:
        pass

    def _color_vec(self, rgb) -> np.ndarray:
        names = list(self.COLORS)
        d = np.array([np.linalg.norm(np.array(rgb) - np.array(self.COLORS[n])) for n in names])
        v = np.exp(-d / 40.0)
        out = np.zeros(16, np.float32)
        out[: len(names)] = v
        out[-1] = 0.05
        return out

    def _word_vec(self, text: str) -> np.ndarray:
        out = np.zeros(16, np.float32)
        for i, n in enumerate(self.COLORS):
            if n in text.lower():
                out[i] = 1.0
        out[-1] = 0.05
        return out

    def clip_image(self, images):
        self.calls["clip_image"] += len(images)
        vecs = [self._color_vec(np.asarray(im.convert("RGB").resize((8, 8))).reshape(-1, 3).mean(0)) for im in images]
        return _norm(np.stack(vecs)) if vecs else np.zeros((0, 16), np.float32)

    def clip_text(self, texts):
        return _norm(np.stack([self._word_vec(t) for t in texts]))

    def text_embed(self, texts):
        self.calls["text"] += len(texts)
        if not texts:
            return np.zeros((0, 16), np.float32)
        return _norm(np.stack([self._word_vec(t) for t in texts]))

    def caption(self, images):
        self.calls["caption"] += len(images)
        if self.fail_captions:
            raise ModelError("captioner crashed (simulated)")
        caps = []
        for im in images:
            v = self._color_vec(np.asarray(im.convert("RGB").resize((8, 8))).reshape(-1, 3).mean(0))
            caps.append(f"a {list(self.COLORS)[int(np.argmax(v[:6]))]} picture")
        return caps

    def transcribe(self, path, max_sec):
        return ""

    def ocr(self, image):
        return ""

    def tags_for(self, img_vecs, top=5, min_sim=0.2):
        if img_vecs.size == 0:
            return []
        return [list(self.COLORS)[int(np.argmax(img_vecs.mean(0)[:6]))]]
