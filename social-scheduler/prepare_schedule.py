"""
Upload all videos to catbox.moe (permanent) and create schedule.json
for the GitHub Actions workflow.

Usage:
    python prepare_schedule.py
"""

import json
import time
import requests
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent / "mass-content-maker"
VARIATIONS_FILE = CONTENT_DIR / "variations.json"
VIDEO_DIR = CONTENT_DIR / "output" / "videos"
SCHEDULE_FILE = Path(__file__).parent / "schedule.json"

CATBOX_URL = "https://catbox.moe/user/api.php"


def upload_to_catbox(file_path: Path) -> str:
    """Upload a file to catbox.moe (permanent). Returns the public URL."""
    with open(file_path, "rb") as f:
        resp = requests.post(
            CATBOX_URL,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (file_path.name, f)},
            timeout=120,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Unexpected response: {url}")
    return url


def main():
    with open(VARIATIONS_FILE) as f:
        variations = json.load(f)

    # Load existing schedule if resuming
    existing = {}
    if SCHEDULE_FILE.exists():
        with open(SCHEDULE_FILE) as f:
            data = json.load(f)
            existing = {p["index"]: p for p in data["posts"]}

    posts = []
    for i, v in enumerate(variations):
        slug = v["metric"].lower().replace(" ", "-").replace("/", "-")
        video_file = VIDEO_DIR / f"{i:02d}-{slug}.mp4"

        if not video_file.exists():
            print(f"  SKIP [{i:02d}] — video not found")
            continue

        # Reuse existing URL if already uploaded
        if i in existing and existing[i].get("video_url"):
            url = existing[i]["video_url"]
            print(f"  CACHED [{i:02d}] {slug} → {url}")
        else:
            try:
                url = upload_to_catbox(video_file)
                print(f"  UPLOADED [{i:02d}] {slug} → {url}")
                time.sleep(2)  # Rate limit protection
            except Exception as e:
                print(f"  FAILED [{i:02d}] {slug} — {e}")
                continue

        caption = f"{v['hook']}\n\n{v.get('hook_sub', '')}\n\nDownload Seneca Chat - link in bio"

        posts.append({
            "index": i,
            "metric": v["metric"],
            "hook": v["hook"],
            "caption": caption,
            "video_url": url,
            "ig_published": existing.get(i, {}).get("ig_published", False),
            "fb_published": existing.get(i, {}).get("fb_published", False),
        })

    schedule = {
        "total": len(posts),
        "posts_per_day": 9,
        "posts": posts,
    }

    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

    published = sum(1 for p in posts if p["ig_published"])
    print(f"\nDone! {len(posts)} posts saved to schedule.json ({published} already published)")


if __name__ == "__main__":
    main()
