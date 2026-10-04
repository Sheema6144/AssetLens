"""Build a mixed public media dataset (images, videos, PDFs) into MEDIA_DIR.

Sources (all free to use):
  * Pixabay API  (images + videos, Pixabay Content License) - needs a free key: PIXABAY_API_KEY
  * Wikimedia Commons API (PDF documents/brochures, extra images/videos) - no key
  * Generated sample brochures composed from downloaded Pixabay photos, so that
    "residential project brochure" style queries have realistic targets
    (clearly marked as generated in the manifest / dataset summary)

Files are saved with neutral names (pixabay_img_123.jpg, commons_doc_456.pdf …)
so search can NOT cheat with filenames - it has to understand the content.
A manifest (data/dataset_manifest.csv) records source URL, licence and the
search term used, which is only used for writing the evaluation.

Usage:
    python scripts/download_dataset.py --target-gb 3
    python scripts/download_dataset.py --target-gb 0.4      # quick test sample
Re-running continues where it stopped (existing files are skipped).
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dam.config import settings  # noqa: E402

# Wikimedia requires a descriptive User-Agent with contact info, otherwise it answers 403.
UA = {"User-Agent": "AssetLensDatasetBuilder/1.0 (https://github.com/Sheema6144; student research project) python-requests"}
WIKI_SEM = threading.Semaphore(2)  # be polite to Wikimedia: max 2 parallel downloads

IMAGE_QUERIES = [
    "woman with cat", "girl holding cat", "cat", "dog playing", "dog park",
    "modern living room", "living room interior", "kitchen interior", "bedroom interior", "luxury villa",
    "construction site", "construction worker", "crane building", "apartment building", "residential house",
    "business meeting", "office teamwork", "presentation office", "city night aerial", "city skyline",
    "food table", "restaurant dinner", "beach sunset", "mountain lake", "red car street",
    "family home garden", "real estate house", "floor plan", "two cats", "people smiling portrait",
]
VIDEO_QUERIES = [
    "construction", "excavator", "crane construction", "building construction workers",
    "woman talking to camera", "man talking to camera", "interview", "testimonial", "vlog",
    "business meeting", "office", "city aerial night", "drone city", "traffic",
    "living room", "house interior", "real estate", "cooking food", "beach sunset", "ocean waves",
    "dog", "cat", "people walking street", "family",
]
PDF_QUERIES = [
    "real estate brochure", "housing brochure", "residential development", "apartment brochure",
    "property brochure", "brochure", "tourism brochure", "product catalogue", "annual report",
    "floor plan", "construction project", "housing project", "leaflet", "flyer",
]

lock = threading.Lock()


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


class Budget:
    def __init__(self, limit_bytes: float):
        self.limit, self.used = limit_bytes, 0

    def ok(self) -> bool:
        return self.used < self.limit

    def add(self, n: int):
        with lock:
            self.used += n


def download(url: str, dest: Path, budget: Budget | None, max_mb: float = 80) -> int:
    """Download one file safely. Never raises: a failed file is just skipped."""
    if dest.exists():
        n = dest.stat().st_size
        if budget:
            budget.add(n)
        return 0
    if budget and not budget.ok():
        return 0
    # unique temp name per download, so parallel threads never touch the same file
    tmp = dest.with_name(f".{dest.name}.{uuid.uuid4().hex[:8]}.part")
    limit = max_mb * 1024 * 1024
    try:
        n = 0
        is_wiki = "wikimedia.org" in url
        if is_wiki:
            WIKI_SEM.acquire()
        try:
            r = None
            for attempt in range(4):
                r = requests.get(url, headers=UA, stream=True, timeout=60)
                if r.status_code in (429, 503):  # rate limited -> wait and retry
                    r.close()
                    time.sleep(3 * (attempt + 1))
                    continue
                break
        finally:
            if is_wiki:
                time.sleep(0.3)
                WIKI_SEM.release()
        with r:
            if r.status_code >= 400:
                print(f"   ! skipped {url[:70]}: HTTP {r.status_code}")
                return 0
            size = int(r.headers.get("content-length") or 0)
            if size and size > limit:
                return 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    n += len(chunk)
                    if n > limit:
                        break
        if n > limit:
            _safe_unlink(tmp)
            return 0
        for attempt in range(5):  # Windows: antivirus / indexer may hold the file briefly
            try:
                if dest.exists():
                    _safe_unlink(tmp)
                    return 0
                os.replace(tmp, dest)
                break
            except PermissionError:
                time.sleep(0.5 * (attempt + 1))
        else:
            _safe_unlink(tmp)
            return 0
        if budget:
            budget.add(n)
        return n
    except Exception as e:  # noqa: BLE001
        _safe_unlink(tmp)
        print(f"   ! skipped {url[:70]}: {type(e).__name__}")
        return 0


def _safe_unlink(p: Path) -> None:
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def run_all(futs, label: str, budget: Budget, every: int):
    for i, f in enumerate(as_completed(futs), 1):
        try:
            f.result()
        except Exception as e:  # noqa: BLE001
            print(f"   ! {label} error: {e}")
        if i % every == 0:
            print(f"   {i}/{len(futs)} {label}, {human(budget.used)}")


# ----------------------------------------------------------------- Pixabay
def pixabay(kind: str, query: str, key: str, per_page: int, page: int = 1) -> list[dict]:
    url = "https://pixabay.com/api/" + ("videos/" if kind == "video" else "")
    params = {"key": key, "q": query, "per_page": per_page, "page": page, "safesearch": "true"}
    if kind == "image":
        params["image_type"] = "photo"
    for attempt in range(3):
        r = requests.get(url, params=params, headers=UA, timeout=30)
        if r.status_code == 429:
            time.sleep(20)
            continue
        if r.status_code == 400:
            return []
        r.raise_for_status()
        return r.json().get("hits", [])
    return []


# ----------------------------------------------------------------- Wikimedia Commons
def commons_search(query: str, mime: str, limit: int) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{query} filemime:{mime}", "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime",
    }
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
    except Exception as e:  # noqa: BLE001
        print(f"   ! commons search failed for {query}: {e}")
        return []
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("url"):
            out.append({"id": p["pageid"], "title": p.get("title", ""), "url": ii["url"], "size": ii.get("size", 0),
                        "page": f"https://commons.wikimedia.org/?curid={p['pageid']}"})
    return out


# ----------------------------------------------------------------- generated brochures
BROCHURES = [
    ("Green Meadows Residences", "residential", ["residential house", "family home garden", "modern living room", "kitchen interior"],
     "Premium 2 & 3 BHK villas and apartments for families. Gated residential community with landscaped gardens, clubhouse, swimming pool and children's play area. RERA approved housing project. Possession in 2027."),
    ("Skyline Heights Apartments", "residential", ["apartment building", "city skyline", "bedroom interior", "living room interior"],
     "High-rise residential apartments with panoramic city views. Spacious 1, 2 and 3 bedroom homes, modular kitchens, 24x7 security, power backup and covered parking. Book your dream home today."),
    ("Palm Grove Villas", "residential", ["luxury villa", "real estate house", "modern living room", "beach sunset"],
     "Independent luxury villas near the beach. Private gardens, Italian marble flooring, smart-home automation. A peaceful residential township for modern living."),
    ("Urban Nest Affordable Housing", "residential", ["apartment building", "family home garden", "kitchen interior", "floor plan"],
     "Affordable housing scheme for first-time home buyers. Compact 1 BHK and 2 BHK flats with easy EMI options, near schools, hospitals and metro station. Floor plans inside."),
    ("Riverside Township Phase II", "residential", ["residential house", "construction site", "crane building", "floor plan"],
     "Phase II of the Riverside residential township is now under construction. Plotted development and row houses with typical floor plans, amenities and construction progress updates."),
    ("Prime Business Park", "commercial", ["office teamwork", "business meeting", "city skyline", "presentation office"],
     "Grade-A commercial office spaces for IT and corporate companies. Flexible floor plates, conference centres, food court and ample parking. Lease enquiries welcome."),
    ("BuildRight Construction Services", "construction", ["construction site", "construction worker", "crane building", "apartment building"],
     "Turnkey civil construction company. Foundations, structural work, project management and safety-first execution for residential and commercial projects."),
    ("Coastal Escapes Travel Guide", "tourism", ["beach sunset", "mountain lake", "food table", "restaurant dinner"],
     "Discover beaches, mountains and local cuisine. Holiday packages, resorts and guided tours for families and couples."),
    ("Fresh Bites Restaurant Menu", "food", ["food table", "restaurant dinner", "kitchen interior", "people smiling portrait"],
     "Seasonal menu with farm-to-table dishes, desserts and beverages. Catering available for corporate events and weddings."),
    ("Happy Paws Pet Care", "pets", ["dog playing", "cat", "woman with cat", "dog park"],
     "Grooming, boarding and veterinary care for cats and dogs. Book a visit for your pet today."),
]


def make_brochures(img_dir: Path, out_dir: Path, manifest: list, by_query: dict[str, list[Path]]):
    try:
        import pymupdf
    except ImportError:
        print("   pymupdf missing - skipping generated brochures")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)
    for i, (title, category, queries, text) in enumerate(BROCHURES, 1):
        dest = out_dir / f"doc_{1000 + i}.pdf"
        imgs = [rnd.choice(by_query[q]) for q in queries if by_query.get(q)]
        if not imgs:
            continue
        if not dest.exists():
            doc = pymupdf.open()
            # cover page
            p = doc.new_page(width=595, height=842)
            p.insert_image(pymupdf.Rect(0, 0, 595, 520), filename=str(imgs[0]), keep_proportion=False)
            p.insert_textbox(pymupdf.Rect(40, 545, 555, 610), title, fontsize=28, fontname="helv")
            p.insert_textbox(pymupdf.Rect(40, 620, 555, 820), text, fontsize=13, fontname="helv")
            # inside pages: one picture + caption each
            for j, im in enumerate(imgs[1:], 2):
                p = doc.new_page(width=595, height=842)
                p.insert_image(pymupdf.Rect(40, 60, 555, 460), filename=str(im))
                p.insert_textbox(pymupdf.Rect(40, 480, 555, 800),
                                 f"{title} - highlights\n\n" + text.split(". ")[min(j - 1, len(text.split('. ')) - 1)] + ".",
                                 fontsize=14, fontname="helv")
            if i % 4 == 0:
                # "scanned" brochure: rasterise every page so there is NO text layer
                scanned = pymupdf.open()
                for pg in doc:
                    pix = pg.get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2))
                    np_ = scanned.new_page(width=pg.rect.width, height=pg.rect.height)
                    np_.insert_image(np_.rect, pixmap=pix)
                doc = scanned
            doc.save(str(dest), garbage=3, deflate=True)
        manifest.append({"file": str(dest.relative_to(img_dir.parent)), "type": "pdf", "source": "generated",
                         "query": f"{category} brochure: {title}", "url": "", "license": "generated from Pixabay images"})


# ----------------------------------------------------------------- test cases
def make_test_cases(root: Path, manifest: list):
    """Duplicates in other folders, corrupt files and unsupported formats."""
    tc = root / "misc_uploads"
    tc.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)
    candidates = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".jpg", ".mp4", ".pdf") and "misc_uploads" not in p.parts]
    for src in rnd.sample(candidates, min(8, len(candidates))):
        dst = tc / f"copy_{src.name}"
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
        manifest.append({"file": str(dst.relative_to(root.parent)), "type": "duplicate", "source": "copy", "query": src.name, "url": "", "license": ""})
    jpgs = [c for c in candidates if c.suffix == ".jpg"]
    if jpgs:
        (tc / "corrupt_photo.jpg").write_bytes(jpgs[0].read_bytes()[:3000])  # truncated
    (tc / "corrupt_video.mp4").write_bytes(os.urandom(50_000))
    (tc / "corrupt_doc.pdf").write_bytes(b"%PDF-1.4\n%garbage" + os.urandom(2000))
    (tc / "empty_file.png").write_bytes(b"")
    (tc / "notes.txt").write_text("unsupported text file")
    (tc / "spreadsheet.xlsx").write_bytes(os.urandom(1000))
    (tc / "archive.zip").write_bytes(os.urandom(1000))


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-gb", type=float, default=3.0)
    ap.add_argument("--out", default=str(settings.media_dir))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    key = os.getenv("PIXABAY_API_KEY", "").strip()
    root = Path(a.out).resolve()
    img_dir, vid_dir, doc_dir = root / "images", root / "videos", root / "documents"
    for d in (img_dir, vid_dir, doc_dir):
        d.mkdir(parents=True, exist_ok=True)
        for leftover in d.glob("*.part"):  # unfinished downloads from an interrupted run
            _safe_unlink(leftover)
        for leftover in d.glob(".*.part"):
            _safe_unlink(leftover)
    total = a.target_gb * 1024 ** 3
    b_img, b_vid, b_pdf = Budget(total * 0.18), Budget(total * 0.70), Budget(total * 0.12)
    manifest: list[dict] = []
    by_query: dict[str, list[Path]] = {}
    pool = ThreadPoolExecutor(a.workers)

    if not key:
        print("PIXABAY_API_KEY not set in .env - images/videos will come from Wikimedia Commons only.")

    # ---- images
    print(f"\n== Images (budget {human(b_img.limit)})")
    per_q = max(8, int(b_img.limit / (450 * 1024) / len(IMAGE_QUERIES)))
    futs, submitted = [], set()
    for q in IMAGE_QUERIES:
        hits = []
        if key:
            hits = [{"id": h["id"], "url": h.get("largeImageURL") or h["webformatURL"], "page": h["pageURL"], "src": "pixabay"}
                    for h in pixabay("image", q, key, min(per_q, 200))]
        if not hits:
            hits = [{"id": h["id"], "url": h["url"], "page": h["page"], "src": "commons"} for h in commons_search(q, "image/jpeg", per_q)]
        for h in hits:
            dest = img_dir / f"{h['src']}_img_{h['id']}.jpg"
            by_query.setdefault(q, []).append(dest)
            if dest in submitted:  # same photo returned for two search terms
                continue
            submitted.add(dest)
            manifest.append({"file": str(dest.relative_to(root.parent)), "type": "image", "source": h["src"], "query": q, "url": h["page"],
                             "license": "Pixabay Content License" if h["src"] == "pixabay" else "Wikimedia Commons (see page)"})
            futs.append(pool.submit(download, h["url"], dest, b_img, 25))
    run_all(futs, "images", b_img, 50)
    by_query = {q: [p for p in ps if p.exists()] for q, ps in by_query.items()}

    # ---- videos
    print(f"\n== Videos (budget {human(b_vid.limit)})")
    per_q = max(4, int(b_vid.limit / (12 * 1024 ** 2) / len(VIDEO_QUERIES)))
    futs, submitted = [], set()
    for q in VIDEO_QUERIES:
        hits = []
        if key:
            for h in pixabay("video", q, key, min(per_q, 100)):
                # 1280x720 ("small") is plenty for analysis and ~3x smaller than 1080p
                v = h["videos"].get("small") or h["videos"].get("medium") or h["videos"].get("tiny") or {}
                if v.get("url"):
                    hits.append({"id": h["id"], "url": v["url"], "page": h["pageURL"], "src": "pixabay", "ext": ".mp4"})
        if not hits:
            for h in commons_search(q, "video/webm", per_q):
                if h["size"] < 80 * 1024 ** 2:
                    hits.append({"id": h["id"], "url": h["url"], "page": h["page"], "src": "commons", "ext": ".webm"})
        for h in hits:
            dest = vid_dir / f"{h['src']}_vid_{h['id']}{h['ext']}"
            if dest in submitted:
                continue
            submitted.add(dest)
            manifest.append({"file": str(dest.relative_to(root.parent)), "type": "video", "source": h["src"], "query": q, "url": h["page"],
                             "license": "Pixabay Content License" if h["src"] == "pixabay" else "Wikimedia Commons (see page)"})
            futs.append(pool.submit(download, h["url"], dest, b_vid, 80))
    run_all(futs, "videos", b_vid, 10)

    # ---- PDFs
    print(f"\n== PDFs (budget {human(b_pdf.limit)})")
    futs, seen = [], set()
    for q in PDF_QUERIES:
        for h in commons_search(q, "application/pdf", 25):
            if h["id"] in seen or h["size"] > 40 * 1024 ** 2:
                continue
            seen.add(h["id"])
            dest = doc_dir / f"commons_doc_{h['id']}.pdf"
            manifest.append({"file": str(dest.relative_to(root.parent)), "type": "pdf", "source": "commons", "query": q, "url": h["page"],
                             "license": "Wikimedia Commons (see page)"})
            futs.append(pool.submit(download, h["url"], dest, b_pdf, 40))
    run_all(futs, "PDFs", b_pdf, 20)
    print(f"   {human(b_pdf.used)} of PDFs")
    make_brochures(img_dir, doc_dir, manifest, by_query)
    pool.shutdown()

    make_test_cases(root, manifest)

    # keep only manifest rows whose file exists
    manifest = [m for m in manifest if (root.parent / m["file"]).exists()]
    mpath = settings.data_dir / "dataset_manifest.csv"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    with open(mpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "type", "source", "query", "url", "license"])
        w.writeheader()
        w.writerows(manifest)

    files = [p for p in root.rglob("*") if p.is_file()]
    print(f"\nDone: {len(files)} files, {human(sum(p.stat().st_size for p in files))} in {root}")
    print(f"Manifest: {mpath}")


if __name__ == "__main__":
    main()
