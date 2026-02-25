"""
YouTube thumbnail downloader.
YouTube thumbnails are publicly accessible at predictable CDN URLs —
no API key or screenshot tool required.
"""
import re
import requests
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "thumbnails"

# Ordered highest → lowest quality
QUALITY_OPTIONS = [
    "maxresdefault",   # 1280×720
    "sddefault",       # 640×480
    "hqdefault",       # 480×360
    "mqdefault",       # 320×180
    "default",         # 120×90
]


def _sanitize(name: str, max_len: int = 80) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    return name[:max_len]


def download_thumbnail(video_id: str, title: str) -> Path | None:
    """
    Download the highest-resolution available thumbnail for a YouTube video.
    Returns the local Path to the saved file, or None on failure.
    Skips download if the file already exists (idempotent).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize(title)
    output_path = OUTPUT_DIR / f"{video_id}_{safe_name}.jpg"

    if output_path.exists():
        return output_path

    for quality in QUALITY_OPTIONS:
        url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            response = requests.get(url, timeout=10)
            # YouTube returns a small placeholder for missing resolutions;
            # real thumbnails are always > 5 KB.
            if response.status_code == 200 and len(response.content) > 5_000:
                output_path.write_bytes(response.content)
                print(f"    [thumbnail] Saved {quality}: {output_path.name}")
                return output_path
        except requests.RequestException:
            continue

    print(f"    [thumbnail] Could not download thumbnail for {video_id}")
    return None
