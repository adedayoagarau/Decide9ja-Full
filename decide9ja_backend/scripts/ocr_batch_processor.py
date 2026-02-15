#!/usr/bin/env python3
"""
Decide9ja — OCR Batch Processor

Processes newspaper scan stubs in catalog.db by:
1. Scanning local JSON files for S3 JPEG image URLs
2. Downloading scanned newspaper page images
3. Running Tesseract OCR with preprocessing
4. Updating catalog.db with extracted text

Usage:
    python3 scripts/ocr_batch_processor.py --dry-run
    python3 scripts/ocr_batch_processor.py --source daily_times --limit 100
    python3 scripts/ocr_batch_processor.py --priority-batch
    python3 scripts/ocr_batch_processor.py --resume
"""

import argparse
import hashlib
import io
import json
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Pillow for image preprocessing
try:
    from PIL import Image, ImageEnhance, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ========== Configuration ==========

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVING_DIR = DATA_DIR / "archiving"
CATALOG_DB = DATA_DIR / "catalog.db"
OCR_CACHE_DIR = DATA_DIR / "ocr_cache"
PROGRESS_DB = DATA_DIR / "ocr_progress.db"
MIN_OCR_TEXT_LENGTH = 8

# Source priority order (high-value historical first)
PRIORITY_SOURCES = [
    ("daily_times", "Daily Times", "1941-1970 colonial/independence era"),
    ("west_african_pilot", "West African Pilot", "1937-1966 Azikiwe's nationalist paper"),
    ("pm_news", "PM News", "1994-2005 military rule to democracy"),
    ("lagos_weekly_record", "Lagos Weekly Record", "1891-1930 earliest Nigerian press"),
    ("nigerian_tribune", "Nigerian Tribune", "1949-2000 Awolowo's paper"),
    ("morning_post", "Morning Post", "1960s government newspaper"),
    ("new_nigerian", "New Nigerian", "Northern region paper"),
    ("nigerian_observer", "Nigerian Observer", "Mid-West region paper"),
    ("nigerian_standard", "Nigerian Standard", "Jos-based paper"),
    ("sunday_times", "Sunday Times", "Weekend edition of Daily Times"),
]

# S3 image URL pattern
S3_IMAGE_PATTERN = re.compile(
    r"https?://s3\.af-south-1\.amazonaws\.com/resiz\.ed/.+\.jpe?g",
    re.IGNORECASE,
)

# Skip these URLs (logos, icons, generic images)
SKIP_URL_PATTERNS = [
    "archivi.ng/_nuxt/",
    "archiving.cdn.prismic.io",
    "images.prismic.io",
    ".svg",
]


@dataclass
class ImageTarget:
    """An image to be OCR'd."""
    doc_id: str       # catalog.db document ID
    source: str       # newspaper source slug
    date: str         # publication date
    image_url: str    # S3 URL to the JPEG scan
    json_path: str    # path to the source JSON file
    local_cache: Optional[str] = None  # local cached image path


@dataclass
class OCRResult:
    """Result of an OCR processing attempt."""
    doc_id: str
    success: bool
    text: str = ""
    text_length: int = 0
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    error: Optional[str] = None


# ========== Progress Tracking ==========

def init_progress_db():
    """Initialize the progress tracking database."""
    conn = sqlite3.connect(str(PROGRESS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ocr_progress (
            doc_id TEXT PRIMARY KEY,
            source TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'pending',
            text_length INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            error TEXT,
            processed_at TEXT,
            processing_time_ms REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_progress_status 
        ON ocr_progress(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_progress_source 
        ON ocr_progress(source)
    """)
    conn.commit()
    conn.close()


def mark_progress(doc_id: str, source: str, image_url: str,
                  status: str, text_length: int = 0,
                  confidence: float = 0.0, error: str = None,
                  processing_time_ms: float = 0.0):
    """Record processing progress."""
    conn = sqlite3.connect(str(PROGRESS_DB))
    conn.execute("""
        INSERT OR REPLACE INTO ocr_progress 
        (doc_id, source, image_url, status, text_length, confidence, error, 
         processed_at, processing_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, source, image_url, status, text_length, confidence,
          error, datetime.now().isoformat(), processing_time_ms))
    conn.commit()
    conn.close()


def get_completed_ids() -> set:
    """Get IDs of already-processed documents."""
    if not PROGRESS_DB.exists():
        return set()
    conn = sqlite3.connect(str(PROGRESS_DB))
    cursor = conn.execute(
        "SELECT doc_id FROM ocr_progress WHERE status = 'success'"
    )
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids


def get_catalog_doc_ids() -> set:
    """Load valid catalog document IDs for newspaper OCR targets."""
    conn = sqlite3.connect(str(CATALOG_DB))
    cursor = conn.execute(
        "SELECT id FROM documents WHERE source_type = 'newspaper'"
    )
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids


def check_network_ready() -> Tuple[bool, str]:
    """Verify required DNS/network reachability before live OCR runs."""
    hosts = [
        "s3.af-south-1.amazonaws.com",
        "resiz.ed.s3.af-south-1.amazonaws.com",
    ]
    for host in hosts:
        try:
            socket.getaddrinfo(host, 443)
            return True, f"DNS OK: {host}"
        except OSError:
            continue
    return False, "DNS resolution failed for required S3 hosts"


# ========== Image URL Extraction ==========

def extract_image_urls_from_json(json_path: Path) -> List[str]:
    """Extract S3 newspaper scan URLs from a scraped JSON file."""
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    urls = []

    # Check images.article[] array
    images = data.get("images", {})
    article_images = images.get("article", [])
    if isinstance(article_images, list):
        for img in article_images:
            url = img.get("url", "") if isinstance(img, dict) else ""
            if _is_newspaper_scan(url):
                urls.append(url)

    # Also check searchResult
    search_img = images.get("searchResult", {})
    if isinstance(search_img, dict):
        url = search_img.get("url", "")
        if _is_newspaper_scan(url):
            urls.append(url)

    # Preserve order while removing duplicates.
    deduped = []
    seen = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def normalize_source_slug(source_slug: str) -> str:
    """Normalize source slug to match catalog doc_id naming."""
    return source_slug.strip("_")


def build_default_sources_to_scan() -> List[Tuple[str, str, str]]:
    """
    Build default source scan list with canonical deduping.
    If both `_name` and `name` exist, prefer `name`.
    """
    canonical_to_dir: Dict[str, str] = {}
    for entry in sorted(ARCHIVING_DIR.iterdir()):
        if not entry.is_dir():
            continue
        dir_name = entry.name
        canonical = normalize_source_slug(dir_name)
        chosen = canonical_to_dir.get(canonical)
        if chosen is None:
            canonical_to_dir[canonical] = dir_name
            continue
        # Prefer non-underscore directory naming for canonical scans.
        if chosen.startswith("_") and not dir_name.startswith("_"):
            canonical_to_dir[canonical] = dir_name

    return [(dir_name, canonical, "") for canonical, dir_name in sorted(canonical_to_dir.items())]


def _is_newspaper_scan(url: str) -> bool:
    """Check if a URL is a newspaper scan image (not a logo/icon)."""
    if not url:
        return False
    normalized = url.lower()
    # Must be a JPEG
    base_url = normalized.split("?", 1)[0]
    if not base_url.endswith((".jpg", ".jpeg")):
        return False
    # Must not match skip patterns
    for pattern in SKIP_URL_PATTERNS:
        if pattern in normalized:
            return False
    # Restrict to real newspaper scans in the S3 archive bucket.
    return bool(S3_IMAGE_PATTERN.match(base_url))


def scan_source_for_images(source_slug: str,
                           completed_ids: set,
                           catalog_ids: set) -> List[ImageTarget]:
    """Scan a newspaper source directory for images needing OCR."""
    source_dir = ARCHIVING_DIR / source_slug
    if not source_dir.exists():
        logger.warning(f"Source directory not found: {source_dir}")
        return []

    targets = []
    seen_doc_ids = set()
    normalized_source = normalize_source_slug(source_slug)
    # Walk JSON files
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if not fname.endswith(".json") or fname == "metadata.json":
                continue

            json_path = Path(root) / fname
            urls = extract_image_urls_from_json(json_path)
            if not urls:
                continue

            # Extract date from filename or path
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
            pub_date = date_match.group(1) if date_match else "unknown"

            # Use first scan URL (the actual newspaper page)
            image_url = urls[0]

            # Generate catalog doc_id: one source/date document.
            doc_id = f"philip_{normalized_source}_{pub_date}"

            if doc_id not in catalog_ids:
                continue
            if doc_id in completed_ids:
                continue
            if doc_id in seen_doc_ids:
                continue

            targets.append(ImageTarget(
                doc_id=doc_id,
                source=normalized_source,
                date=pub_date,
                image_url=image_url,
                json_path=str(json_path),
            ))
            seen_doc_ids.add(doc_id)

    return targets


def get_failed_targets_for_retry(completed_ids: set, catalog_ids: set) -> List[ImageTarget]:
    """Return retryable failed targets from progress DB."""
    if not PROGRESS_DB.exists():
        return []

    conn = sqlite3.connect(str(PROGRESS_DB))
    cursor = conn.execute(
        """
        SELECT doc_id, source, image_url
        FROM ocr_progress
        WHERE status IN ('ocr_failed', 'update_failed', 'download_failed', 'cache_miss')
        ORDER BY processed_at ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    targets = []
    seen = set()
    for doc_id, source, image_url in rows:
        if doc_id in seen:
            continue
        if doc_id in completed_ids:
            continue
        if doc_id not in catalog_ids:
            continue
        if not _is_newspaper_scan(image_url):
            continue

        date_match = re.search(r"(\d{4}-\d{2}-\d{2})$", doc_id or "")
        pub_date = date_match.group(1) if date_match else "unknown"
        targets.append(ImageTarget(
            doc_id=doc_id,
            source=normalize_source_slug(source),
            date=pub_date,
            image_url=image_url,
            json_path="progress_db_retry",
        ))
        seen.add(doc_id)

    return targets


# ========== Image Download ==========

def download_image(url: str, cache_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Download an image with caching."""
    # Create cache path from URL hash
    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = ".jpg"
    cache_path = cache_dir / f"{url_hash}{ext}"

    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path, None

    # Normalize URLs with spaces/special chars before request.
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:@%+,;=-_.~")
    safe_query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&:@%+,;/-_.~")
    normalized_url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment)
    )
    candidate_urls = [normalized_url]
    # Fallback from path-style to virtual-host-style S3 URL.
    if parts.netloc == "s3.af-south-1.amazonaws.com" and safe_path.startswith("/resiz.ed/"):
        vh_path = safe_path[len("/resiz.ed"):]
        virtual_host_url = urllib.parse.urlunsplit(
            (parts.scheme, "resiz.ed.s3.af-south-1.amazonaws.com", vh_path, safe_query, parts.fragment)
        )
        candidate_urls.append(virtual_host_url)

    # Retries for transient S3/network failures.
    headers_pool = [
        {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"},
        {"User-Agent": "curl/8.4.0"},
    ]
    last_error = None
    for candidate_url in candidate_urls:
        for attempt in range(4):
            try:
                headers = headers_pool[attempt % len(headers_pool)]
                req = urllib.request.Request(candidate_url, headers=headers)
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = resp.read()
                if not data:
                    raise OSError("empty body")

                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
                return cache_path, None

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}"
                # Retry only transient HTTP errors.
                if e.code not in {403, 408, 429, 500, 502, 503, 504}:
                    break
            except urllib.error.URLError as e:
                last_error = f"URLError {e.reason}"
            except OSError as e:
                last_error = f"OSError {e}"

            # Backoff 1.5s, 3s, 4.5s...
            time.sleep(1.5 * (attempt + 1))

    logger.debug(f"Download failed {normalized_url[:90]}...: {last_error}")
    return None, last_error


def get_cached_image_path(url: str, cache_dir: Path) -> Optional[Path]:
    """Return cached image path for URL hash if present."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_path = cache_dir / f"{url_hash}.jpg"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path
    return None


# ========== Image Preprocessing ==========

def preprocess_image(image_path: Path) -> Optional[Path]:
    """
    Preprocess a scanned newspaper page for better OCR.
    
    Techniques:
    - Convert to grayscale
    - Enhance contrast
    - Apply slight sharpening
    - Denoise
    """
    if not PILLOW_AVAILABLE:
        return image_path  # Skip preprocessing

    try:
        img = Image.open(image_path)

        # Convert to grayscale
        if img.mode != "L":
            img = img.convert("L")

        # Enhance contrast (old newspaper scans are often faded)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Sharpen slightly
        img = img.filter(ImageFilter.SHARPEN)

        # Save preprocessed version
        preprocessed_path = image_path.parent / f"pre_{image_path.name}"
        img.save(preprocessed_path, "JPEG", quality=95)

        return preprocessed_path

    except Exception as e:
        logger.debug(f"Preprocessing failed: {e}")
        return image_path


# ========== Tesseract OCR ==========

def run_tesseract(image_path: Path) -> Tuple[str, float]:
    """
    Run Tesseract OCR on an image.
    
    Returns (extracted_text, confidence).
    """
    def _run(psm: str) -> Tuple[str, float]:
        result = subprocess.run(
            [
                "tesseract",
                str(image_path),
                "stdout",
                "-l", "eng",
                "--psm", psm,
                "--oem", "3",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = _post_process_ocr(result.stdout.strip())
        if not text:
            return "", 0.0
        return text, _estimate_confidence(text)

    try:
        # First pass optimized for full-page newspaper scans.
        best_text, best_conf = _run("3")
        if len(best_text) >= 20:
            return best_text, best_conf

        # Fallback pass for difficult scans.
        for psm in ("6", "4", "11"):
            text, conf = _run(psm)
            if len(text) > len(best_text):
                best_text, best_conf = text, conf
            if len(best_text) >= 20:
                break
        return best_text, best_conf

    except subprocess.TimeoutExpired:
        return "", 0.0
    except FileNotFoundError:
        logger.error("Tesseract not found! Install with: brew install tesseract")
        sys.exit(1)


def _post_process_ocr(text: str) -> str:
    """Clean up common OCR artifacts in Nigerian newspaper text."""
    # Remove excess whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    # Fix common OCR errors
    replacements = {
        "rn": "m",  # Common OCR misread
        "|": "l",   # Pipe to lowercase L
        "0": "O",   # Zero to O (only in word context)
    }

    # Remove non-printable characters
    text = re.sub(r"[^\x20-\x7E\n]", "", text)

    # Clean up lines that are just punctuation/artifacts
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just symbols
        if stripped and len(re.sub(r"[^a-zA-Z]", "", stripped)) > 2:
            clean_lines.append(line)

    return "\n".join(clean_lines)


def _estimate_confidence(text: str) -> float:
    """Estimate OCR confidence based on text quality metrics."""
    if not text:
        return 0.0

    # Count recognizable English words (simple heuristic)
    words = text.split()
    if not words:
        return 0.0

    # Ratio of "normal" words (3+ chars, mostly alphabetic)
    normal_words = sum(
        1 for w in words
        if len(w) >= 3 and sum(c.isalpha() for c in w) / len(w) > 0.7
    )

    confidence = min(normal_words / max(len(words), 1), 1.0)
    return round(confidence, 2)


# ========== Catalog DB Update ==========

def update_catalog_content(doc_id: str, text: str, confidence: float, target: ImageTarget):
    """Update a document in catalog.db with OCR'd content."""
    conn = sqlite3.connect(str(CATALOG_DB))
    
    # 1. Try exact ID match
    cursor = conn.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    
    # 2. Try matching by canonical source/date fields if exact ID fails
    if not row:
        source_slug = normalize_source_slug(target.source)
        cursor = conn.execute(
            """
            SELECT id
            FROM documents
            WHERE source_type = 'newspaper'
              AND published_date = ?
              AND id LIKE ?
            LIMIT 1
            """,
            (target.date, f"philip_{source_slug}_%")
        )
        row = cursor.fetchone()

    # 3. Last resort: source metadata fuzzy match
    if not row and "_" in target.source:
        source_name = normalize_source_slug(target.source).replace("_", " ").title()
        cursor = conn.execute(
            "SELECT id FROM documents WHERE published_date = ? AND source_metadata LIKE ? LIMIT 1",
            (target.date, f"%{source_name}%")
        )
        row = cursor.fetchone()

    if not row:
        conn.close()
        return False

    actual_id = row[0]

    # Update content
    conn.execute("""
        UPDATE documents 
        SET content = ?,
            content_summary = ?,
            confidence = ?,
            processing_status = 'ocr_processed'
        WHERE id = ?
    """, (text, text[:500], confidence, actual_id))

    # Update FTS index (trigger should handle this, but be safe)
    try:
        conn.execute("""
            DELETE FROM documents_fts WHERE rowid = (
                SELECT rowid FROM documents WHERE id = ?
            )
        """, (actual_id,))
        conn.execute("""
            INSERT INTO documents_fts(rowid, title, content)
            SELECT rowid, title, ? FROM documents WHERE id = ?
        """, (text, actual_id))
    except sqlite3.Error:
        pass  # Trigger may have handled it

    conn.commit()
    conn.close()
    return True


def catalog_doc_exists(doc_id: str) -> bool:
    """Check whether a catalog document exists by ID."""
    conn = sqlite3.connect(str(CATALOG_DB))
    cursor = conn.execute("SELECT 1 FROM documents WHERE id = ? LIMIT 1", (doc_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


# ========== Main Processing ==========

def process_single_target(target: ImageTarget, dry_run: bool = False, cache_only: bool = False) -> OCRResult:
    """Process a single image target through download → preprocess → OCR → store."""
    start = time.time()

    if dry_run:
        return OCRResult(
            doc_id=target.doc_id,
            success=True,
            text="[DRY RUN]",
            text_length=0,
        )

    # 1. Download image
    cache_dir = OCR_CACHE_DIR / target.source
    if cache_only:
        image_path = get_cached_image_path(target.image_url, cache_dir)
        download_error = "cache miss" if not image_path else None
    else:
        image_path, download_error = download_image(target.image_url, cache_dir)
    if not image_path:
        status = "cache_miss" if cache_only else "download_failed"
        result = OCRResult(
            doc_id=target.doc_id,
            success=False,
            error=f"{status}: {download_error or 'unknown'}",
            processing_time_ms=(time.time() - start) * 1000,
        )
        mark_progress(target.doc_id, target.source, target.image_url,
                      status, error=result.error)
        return result

    # 2. Preprocess
    processed_path = preprocess_image(image_path)

    # 3. OCR
    text, confidence = run_tesseract(processed_path)
    if len(text) < MIN_OCR_TEXT_LENGTH and processed_path != image_path:
        # Retry on raw image when preprocessing degrades legibility.
        raw_text, raw_conf = run_tesseract(image_path)
        if len(raw_text) > len(text):
            text, confidence = raw_text, raw_conf

    # Cleanup preprocessed temp file
    if processed_path != image_path and processed_path.exists():
        try:
            processed_path.unlink()
        except OSError:
            pass

    elapsed = (time.time() - start) * 1000

    if not text or len(text) < MIN_OCR_TEXT_LENGTH:
        result = OCRResult(
            doc_id=target.doc_id,
            success=False,
            text=text,
            text_length=len(text or ""),
            error="OCR returned insufficient text",
            processing_time_ms=elapsed,
        )
        mark_progress(target.doc_id, target.source, target.image_url,
                      "ocr_failed", text_length=len(text or ""),
                      error=result.error, processing_time_ms=elapsed)
        return result

    # 4. Update catalog
    updated = update_catalog_content(target.doc_id, text, confidence, target)

    status = "success" if updated else "update_failed"
    error_msg = None if updated else "Catalog update failed (doc not found)"
    if not updated and not catalog_doc_exists(target.doc_id):
        status = "skipped_missing_doc"
        error_msg = "No matching catalog document"

    result = OCRResult(
        doc_id=target.doc_id,
        success=updated,
        text=text,
        text_length=len(text),
        confidence=confidence,
        processing_time_ms=elapsed,
        error=error_msg,
    )

    mark_progress(
        target.doc_id, target.source, target.image_url,
        status,
        text_length=len(text),
        confidence=confidence,
        error=error_msg,
        processing_time_ms=elapsed,
    )

    return result


def process_batch(targets: List[ImageTarget], dry_run: bool = False,
                  max_workers: int = 4, cache_only: bool = False) -> Dict:
    """Process a batch of image targets."""
    stats = {
        "total": len(targets),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total_chars": 0,
        "avg_confidence": 0.0,
        "start_time": datetime.now().isoformat(),
    }

    if not targets:
        print("  No targets to process.")
        return stats

    confidences = []

    # Process with Thread pool (I/O bound: downloads + Tesseract subproc)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_target, t, dry_run, cache_only): t
            for t in targets
        }

        for i, future in enumerate(as_completed(futures), 1):
            target = futures[future]
            try:
                result = future.result()
                if result.success:
                    stats["success"] += 1
                    stats["total_chars"] += result.text_length
                    if result.confidence > 0:
                        confidences.append(result.confidence)
                else:
                    stats["failed"] += 1

                # Progress logging every 10 items
                if i % 10 == 0 or i == len(targets):
                    pct = i / len(targets) * 100
                    print(f"  [{i}/{len(targets)}] {pct:.0f}% | "
                          f"✓ {stats['success']} ✗ {stats['failed']} | "
                          f"{target.source}/{target.date}")

            except Exception as e:
                stats["failed"] += 1
                logger.error(f"Error processing {target.doc_id}: {e}")

    stats["avg_confidence"] = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )
    stats["end_time"] = datetime.now().isoformat()
    return stats


# ========== CLI ==========

def main():
    parser = argparse.ArgumentParser(
        description="OCR Batch Processor for Decide9ja newspaper scans"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Scan for images without processing")
    parser.add_argument("--source", type=str, default=None,
                        help="Process specific source (e.g., daily_times)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max images to process")
    parser.add_argument("--priority-batch", action="store_true",
                        help="Process all priority sources")
    parser.add_argument("--resume", action="store_true",
                        help="Resume interrupted processing")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers")
    parser.add_argument("--list-sources", action="store_true",
                        help="List available newspaper sources")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry failed items from ocr_progress.db")
    parser.add_argument("--cache-only", action="store_true",
                        help="Use only locally cached images, never network download")

    args = parser.parse_args()

    print("=" * 60)
    print("Decide9ja OCR Batch Processor")
    print("=" * 60)
    print(f"Archiving dir: {ARCHIVING_DIR}")
    print(f"Catalog DB:    {CATALOG_DB}")
    print(f"Cache dir:     {OCR_CACHE_DIR}")
    print(f"Mode:          {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.cache_only:
        print("Fetch mode:    CACHE-ONLY")
    print()

    if not ARCHIVING_DIR.exists():
        print(f"❌ Archiving directory not found: {ARCHIVING_DIR}")
        sys.exit(1)

    if not CATALOG_DB.exists():
        print(f"❌ Catalog database not found: {CATALOG_DB}")
        sys.exit(1)

    if not args.dry_run and not args.cache_only:
        network_ok, network_msg = check_network_ready()
        print(f"Network check: {network_msg}")
        if not network_ok:
            print("❌ Cannot run LIVE OCR while DNS/network is unavailable.")
            sys.exit(2)

    # List sources mode
    if args.list_sources:
        print("Available newspaper sources:")
        print("-" * 50)
        for entry in sorted(ARCHIVING_DIR.iterdir()):
            if entry.is_dir():
                json_count = sum(1 for _ in entry.rglob("article_*.json"))
                print(f"  {entry.name:<25} {json_count:>6} article JSONs")
        return

    # Initialize progress DB
    init_progress_db()
    completed = get_completed_ids() if args.resume else set()
    catalog_ids = get_catalog_doc_ids()
    if completed:
        print(f"Resume mode: {len(completed)} already processed")
    print(f"Catalog OCR docs: {len(catalog_ids)}")

    # Determine which targets to process
    all_targets = []
    if args.retry_failed:
        print("Loading failed targets from progress DB...")
        print("-" * 50)
        all_targets = get_failed_targets_for_retry(completed, catalog_ids)
    else:
        if args.source:
            sources_to_scan = [(args.source, args.source, "User selected")]
        elif args.priority_batch:
            sources_to_scan = PRIORITY_SOURCES
        else:
            # Default: scan all sources with canonical deduping.
            sources_to_scan = build_default_sources_to_scan()

        print("Scanning for newspaper scan images...")
        print("-" * 50)
        for slug, name, desc in sources_to_scan:
            targets = scan_source_for_images(slug, completed, catalog_ids)
            if targets:
                preview = f" — {desc}" if desc else ""
                print(f"  {name:<25} {len(targets):>6} images{preview}")
                all_targets.extend(targets)

    print(f"\nTotal targets: {len(all_targets)}")

    if args.limit:
        all_targets = all_targets[:args.limit]
        print(f"Limited to: {args.limit}")

    if not all_targets:
        print("\n✓ No new images to process.")
        return

    # Process
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Processing {len(all_targets)} images...")
    print("-" * 50)

    stats = process_batch(
        all_targets,
        dry_run=args.dry_run,
        max_workers=args.workers,
        cache_only=args.cache_only,
    )

    # Summary
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total:           {stats['total']}")
    print(f"  Success:         {stats['success']}")
    print(f"  Failed:          {stats['failed']}")
    print(f"  Characters:      {stats['total_chars']:,}")
    print(f"  Avg confidence:  {stats['avg_confidence']:.2f}")

    if not args.dry_run:
        # Quick catalog verification
        conn = sqlite3.connect(str(CATALOG_DB))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE LENGTH(content) >= 500"
        )
        rich_count = cursor.fetchone()[0]
        cursor = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE LENGTH(content) < 100"
        )
        stub_count = cursor.fetchone()[0]
        conn.close()
        print(f"\n  Catalog status:")
        print(f"    Rich docs (500+ chars):  {rich_count:,}")
        print(f"    Stubs (<100 chars):      {stub_count:,}")

    print(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
