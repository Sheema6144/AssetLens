"""Turn one file into searchable AI output.

Each processor returns a dict:
    vectors  : list of {space, source, ref, label, thumb, vec}
    caption  : short human-readable description
    tags     : zero-shot CLIP tags
    body     : long text (PDF text / transcript / frame captions) for keyword search
    meta     : technical metadata (dimensions, duration, pages ...)
    warnings : non-fatal problems (e.g. captioner failed but embeddings worked)
    thumb    : main thumbnail filename (inside data/thumbs)

Fatal problems (corrupt file, unreadable codec, encrypted PDF) raise
ProcessingError; the indexer records the message and moves on.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .config import Settings
from .models import ModelError

log = logging.getLogger("dam.processors")

Image.MAX_IMAGE_PIXELS = 200_000_000  # allow big photos, still guard decompression bombs
THUMB_PX = 360
MODEL_PX = 768
CANDIDATE_PX = 640     # video frames are downscaled to this immediately
MAX_CANDIDATES = 60    # at most this many candidate frames are inspected per video


class ProcessingError(RuntimeError):
    pass


def _save_thumb(img: Image.Image, cfg: Settings, name: str) -> str:
    t = img.convert("RGB").copy()
    t.thumbnail((THUMB_PX, THUMB_PX))
    t.save(cfg.thumbs_dir / name, "JPEG", quality=82)
    return name


def _vec(space, source, vec, ref=None, label=None, thumb=None):
    return {"space": space, "source": source, "vec": vec, "ref": ref, "label": label, "thumb": thumb}


def _caption_safely(models, images, warnings) -> list[str]:
    """Captions are a bonus: if the captioner fails we keep going without them."""
    try:
        return models.caption(images)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"captioning failed: {e}")
        log.warning("captioning failed: %s", e)
        return [""] * len(images)


def _chunks(text: str, size: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):  # try to cut at a sentence / word boundary
            cut = max(text.rfind(". ", start, end), text.rfind(" ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        out.append(text[start:end].strip())
        start = end
    return [c for c in out if len(c) > 20]


# --------------------------------------------------------------------------- images
def load_image(path: Path) -> tuple[Image.Image, dict]:
    try:
        with Image.open(path) as probe:
            info = {"width": probe.width, "height": probe.height, "format": probe.format}
            probe.verify()  # detects truncated / corrupt files cheaply
        im = Image.open(path)
        im.draft("RGB", (MODEL_PX * 2, MODEL_PX * 2))  # fast JPEG downscale on decode
        im = ImageOps.exif_transpose(im)
        im.load()
    except Exception as e:  # noqa: BLE001
        raise ProcessingError(f"corrupt or unreadable image: {e}") from e
    if getattr(im, "is_animated", False):
        im.seek(0)
    im = im.convert("RGB")
    im.thumbnail((MODEL_PX, MODEL_PX))
    return im, info


def process_image(path: Path, hash_: str, models, cfg: Settings) -> dict:
    warnings: list[str] = []
    im, info = load_image(path)
    thumb = _save_thumb(im, cfg, f"{hash_}.jpg")
    img_vec = models.clip_image([im])
    caption = _caption_safely(models, [im], warnings)[0]
    tags = models.tags_for(img_vec)
    vectors = [_vec("clip", "image", img_vec[0], thumb=thumb, label=caption)]
    if caption:
        vectors.append(_vec("text", "caption", models.text_embed([caption])[0], label=caption, thumb=thumb))
    return {
        "vectors": vectors,
        "caption": caption,
        "tags": tags,
        "body": "",
        "meta": info,
        "warnings": warnings,
        "thumb": thumb,
    }


# --------------------------------------------------------------------------- videos
def _hist(frame_bgr) -> np.ndarray:
    import cv2

    hsv = cv2.cvtColor(cv2.resize(frame_bgr, (160, 90)), cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
    return cv2.normalize(h, h).flatten()


def sample_keyframes(path: Path, cfg: Settings) -> tuple[list[tuple[float, Image.Image]], dict]:
    """Pick representative frames without decoding the whole video.

    1. Look at candidate frames ~1 per second (fewer for long videos: at most 60),
       using fast seeking for long MP4/MOV and sequential grabbing otherwise;
       frames are downscaled to 640 px immediately to keep RAM low.
    2. Keep a candidate if the scene changed (colour-histogram distance) or if
       `video_frame_interval` seconds passed since the last kept frame.
    3. Skip near-black frames (fades), cap at `video_max_frames` evenly.
    """
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ProcessingError("cannot open video (corrupt file or unsupported codec)")

    def small(fr):
        # shrink immediately: keeping 4K frames in RAM would exhaust an 8 GB laptop
        h, w = fr.shape[:2]
        scale = CANDIDATE_PX / max(h, w)
        return cv2.resize(fr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else fr

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if fps <= 0 or fps > 240:
            fps = 25.0
        duration = n / fps if n > 0 else 0.0
        step_s = max(1.0, duration / MAX_CANDIDATES) if duration else 1.0
        candidates: list[tuple[float, np.ndarray]] = []

        # Short clips: decoding sequentially is as fast as seeking. Long MP4/MOV: seeking
        # skips most of the file (only decodes from the nearest keyframe).
        seekable = path.suffix.lower() in (".mp4", ".mov", ".m4v") and duration > 120
        if seekable:
            t, misses = 0.0, 0
            while t < duration and misses < 3:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, fr = cap.read()
                if ok and fr is not None:
                    candidates.append((t, small(fr)))
                    misses = 0
                else:
                    misses += 1
                t += step_s
            if len(candidates) < 2:  # seeking unsupported -> fall back to sequential
                candidates = []
                cap.release()
                cap = cv2.VideoCapture(str(path))
        if not candidates:
            # robust path for webm/mkv/avi (seeking there is unreliable): grab sequentially
            step = max(1, int(round(step_s * fps)))
            idx = 0
            while n <= 0 or idx < n:
                if not cap.grab():
                    break
                if idx % step == 0:
                    ok, fr = cap.retrieve()
                    if ok and fr is not None:
                        candidates.append((idx / fps, small(fr)))
                    if n <= 0 and len(candidates) >= MAX_CANDIDATES * 4:
                        break
                idx += 1
            if not duration and candidates:
                duration = candidates[-1][0]
    finally:
        cap.release()

    if not candidates:
        raise ProcessingError("no decodable frames (corrupt video or unsupported codec)")

    bright = [(t, f) for t, f in candidates if f.mean() > 12] or candidates
    kept: list[tuple[float, np.ndarray]] = []
    last_hist, last_t = None, -1e9
    for t, fr in bright:
        h = _hist(fr)
        changed = last_hist is None or cv2.compareHist(last_hist, h, cv2.HISTCMP_BHATTACHARYYA) > cfg.video_scene_threshold
        if changed or (t - last_t) >= cfg.video_frame_interval:
            kept.append((t, fr))
            last_hist, last_t = h, t
    if len(kept) > cfg.video_max_frames:
        sel = np.linspace(0, len(kept) - 1, cfg.video_max_frames).round().astype(int)
        kept = [kept[i] for i in sorted(set(sel))]

    frames = []
    for t, fr in kept:
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        im.thumbnail((MODEL_PX, MODEL_PX))
        frames.append((round(float(t), 1), im))
    meta = {"duration": round(duration, 1), "fps": round(fps, 2), "width": width, "height": height,
            "frames_sampled": len(frames), "candidates_checked": len(candidates)}
    return frames, meta


def process_video(path: Path, hash_: str, models, cfg: Settings) -> dict:
    warnings: list[str] = []
    frames, meta = sample_keyframes(path, cfg)
    images = [im for _, im in frames]
    thumbs = [_save_thumb(im, cfg, f"{hash_}_t{i}.jpg") for i, im in enumerate(images)]
    clip_vecs = models.clip_image(images)

    # caption a spread-out subset of keyframes (captioning is the slow part on CPU)
    cap_idx = sorted(set(np.linspace(0, len(images) - 1, min(len(images), cfg.video_max_captions)).round().astype(int)))
    caps = _caption_safely(models, [images[i] for i in cap_idx], warnings)
    cap_by_idx = dict(zip(cap_idx, caps))

    vectors = []
    for i, (t, _im) in enumerate(frames):
        vectors.append(_vec("clip", "frame", clip_vecs[i], ref=t, thumb=thumbs[i], label=cap_by_idx.get(i)))
    cap_items = [(i, c) for i, c in cap_by_idx.items() if c]
    if cap_items:
        tv = models.text_embed([c for _, c in cap_items])
        for (i, c), v in zip(cap_items, tv):
            vectors.append(_vec("text", "caption", v, ref=frames[i][0], label=c, thumb=thumbs[i]))

    transcript = ""
    try:
        transcript = models.transcribe(str(path), cfg.video_max_audio_sec)
    except ModelError as e:
        warnings.append(f"transcription unavailable: {e}")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"transcription failed: {e}")
    meta["has_speech"] = bool(transcript)
    if transcript:
        chunks = _chunks(transcript, 500)[:40]
        for c, v in zip(chunks, models.text_embed(chunks)):
            vectors.append(_vec("text", "transcript", v, label=c, thumb=thumbs[len(thumbs) // 2]))

    unique_caps = list(dict.fromkeys(c for c in caps if c))
    caption = unique_caps[len(unique_caps) // 2] if unique_caps else ""
    body = " | ".join(f"[{frames[i][0]:.0f}s] {c}" for i, c in cap_items)
    if transcript:
        body += "\nTRANSCRIPT: " + transcript
    return {
        "vectors": vectors,
        "caption": caption,
        "tags": models.tags_for(clip_vecs),
        "body": body,
        "meta": meta,
        "warnings": warnings,
        "thumb": thumbs[len(thumbs) // 2],
    }


# --------------------------------------------------------------------------- PDFs
def process_pdf(path: Path, hash_: str, models, cfg: Settings) -> dict:
    import pymupdf

    warnings: list[str] = []
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:  # noqa: BLE001
        raise ProcessingError(f"corrupt or unreadable PDF: {e}") from e
    try:
        if doc.needs_pass:
            raise ProcessingError("PDF is password-protected")
        if doc.page_count == 0:
            raise ProcessingError("PDF has no pages")

        title = (doc.metadata or {}).get("title") or ""
        page_imgs: list[tuple[int, Image.Image]] = []
        texts: list[tuple[int, str]] = []
        ocr_pages = 0
        for pno in range(min(doc.page_count, max(cfg.pdf_max_pages_text, cfg.pdf_max_page_images))):
            page = doc.load_page(pno)
            img = None
            if pno < cfg.pdf_max_page_images:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                img.thumbnail((MODEL_PX, MODEL_PX))
                page_imgs.append((pno + 1, img))
            if pno < cfg.pdf_max_pages_text:
                txt = page.get_text("text") or ""
                if len(txt.strip()) < 30 and models.ocr_available:
                    if img is None:
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    try:
                        txt = models.ocr(img)
                        ocr_pages += 1
                    except Exception as e:  # noqa: BLE001
                        warnings.append(f"OCR failed on page {pno + 1}: {e}")
                if txt.strip():
                    texts.append((pno + 1, txt))
        page_count = doc.page_count
    finally:
        doc.close()

    if not title:
        first = next((t for _, t in texts), "")
        title = next((ln.strip() for ln in first.splitlines() if len(ln.strip()) > 3), "")[:120]

    thumbs = [_save_thumb(im, cfg, f"{hash_}_p{p}.jpg") for p, im in page_imgs]
    vectors = []
    if page_imgs:
        cv = models.clip_image([im for _, im in page_imgs])
        n_cap = min(3, len(page_imgs))
        caps = _caption_safely(models, [im for _, im in page_imgs[:n_cap]], warnings) + [""] * (len(page_imgs) - n_cap)
        for (p, _), v, th, c in zip(page_imgs, cv, thumbs, caps):
            vectors.append(_vec("clip", "page", v, ref=p, thumb=th, label=c or f"page {p}"))
        cap_items = [(p, c, th) for (p, _), c, th in zip(page_imgs, caps, thumbs) if c]
        if cap_items:
            for (p, c, th), v in zip(cap_items, models.text_embed([c for _, c, _ in cap_items])):
                vectors.append(_vec("text", "caption", v, ref=p, label=c, thumb=th))
        tags = models.tags_for(cv)
    else:
        caps, tags = [], []

    # text chunks, each remembers its page so results can point to "page 4"
    chunk_items: list[tuple[int, str]] = []
    for p, t in texts:
        for c in _chunks(t, cfg.pdf_chunk_chars):
            chunk_items.append((p, c))
    chunk_items = chunk_items[:250]
    full_text = "\n".join(t for _, t in texts)
    summary = (title + ". " + re.sub(r"\s+", " ", full_text)[:600]).strip(". ")
    thumb_for = {p: th for (p, _), th in zip(page_imgs, thumbs)}
    if summary:
        vectors.append(_vec("text", "pdf_summary", models.text_embed([summary])[0], ref=1, label=summary[:300], thumb=thumbs[0] if thumbs else None))
    if chunk_items:
        for (p, c), v in zip(chunk_items, models.text_embed([c for _, c in chunk_items])):
            vectors.append(_vec("text", "pdf_text", v, ref=p, label=c[:300], thumb=thumb_for.get(p, thumbs[0] if thumbs else None)))

    if not texts:
        warnings.append("no text layer found" + ("" if models.ocr_available else " (OCR not installed)"))
    first_cap = next((c for c in caps if c), "")
    caption = (title + " — " + first_cap) if title and first_cap else (title or first_cap)
    return {
        "vectors": vectors,
        "caption": caption,
        "tags": tags,
        "body": full_text,
        "meta": {"pages": page_count, "title": title, "has_text": bool(texts), "ocr_pages": ocr_pages},
        "warnings": warnings,
        "thumb": thumbs[0] if thumbs else None,
    }


PROCESSORS = {"image": process_image, "video": process_video, "pdf": process_pdf}
