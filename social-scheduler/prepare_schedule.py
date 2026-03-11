"""
Build schedule.json from variations.json and local video files.
Videos are uploaded to Litterbox at publish time by publish_next.py.

Usage:
    python prepare_schedule.py
"""

import json
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent / "mass-content-maker"
VARIATIONS_FILE = CONTENT_DIR / "variations.json"
VIDEO_DIR = Path(__file__).parent / "videos"
SCHEDULE_FILE = Path(__file__).parent / "schedule.json"


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

        caption = f"{v['hook']}\n\n{v.get('hook_sub', '')}\n\nDownload Seneca Chat - link in bio"

        posts.append({
            "index": i,
            "metric": v["metric"],
            "hook": v["hook"],
            "caption": caption,
            "video_file": f"social-scheduler/videos/{i:02d}-{slug}.mp4",
            "ig_published": existing.get(i, {}).get("ig_published", False),
            "fb_published": existing.get(i, {}).get("fb_published", False),
        })
        print(f"  OK [{i:02d}] {slug}")

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
