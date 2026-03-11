"""
Publish the next unpublished Instagram Reel from schedule.json.
Designed to run in GitHub Actions — no heavy dependencies.

Env vars required:
    META_PAGE_ACCESS_TOKEN
    INSTAGRAM_ACCOUNT_ID
"""

import json
import os
import time
import requests
from pathlib import Path

SCHEDULE_FILE = Path(__file__).parent / "schedule.json"
API_VERSION = "v25.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def main():
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    ig_id = os.environ["INSTAGRAM_ACCOUNT_ID"]

    # Load schedule
    with open(SCHEDULE_FILE) as f:
        schedule = json.load(f)

    # Find next unpublished post
    post = None
    for p in schedule["posts"]:
        if not p["ig_published"]:
            post = p
            break

    if not post:
        print("All posts have been published!")
        return

    published_count = sum(1 for p in schedule["posts"] if p["ig_published"])
    print(f"Publishing post [{post['index']:02d}] — {post['metric']}")
    print(f"Progress: {published_count}/{schedule['total']}")
    print(f"Video URL: {post['video_url']}")

    # Step 1: Create container
    print("\nCreating Instagram Reel container...")
    resp = requests.post(
        f"{BASE_URL}/{ig_id}/media",
        data={
            "media_type": "REELS",
            "video_url": post["video_url"],
            "caption": post["caption"],
            "access_token": token,
        },
        timeout=60,
    )

    if resp.status_code != 200:
        print(f"ERROR creating container: {resp.status_code} — {resp.text}")
        return

    container_id = resp.json()["id"]
    print(f"Container created: {container_id}")

    # Step 2: Wait for processing
    print("Waiting for video processing...", end="", flush=True)
    for _ in range(60):  # Max 5 minutes
        time.sleep(5)
        status_resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        status = status_resp.json().get("status_code", "UNKNOWN")
        print(".", end="", flush=True)

        if status == "FINISHED":
            print(f" {status}")
            break
        if status == "ERROR":
            print(f"\nERROR: Container processing failed")
            print(status_resp.json())
            return
    else:
        print("\nTIMEOUT: Video processing took too long")
        return

    # Step 3: Publish
    print("Publishing...")
    pub_resp = requests.post(
        f"{BASE_URL}/{ig_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )

    if pub_resp.status_code != 200:
        print(f"ERROR publishing: {pub_resp.status_code} — {pub_resp.text}")
        return

    media_id = pub_resp.json()["id"]
    print(f"PUBLISHED! Media ID: {media_id}")

    # Step 4: Update schedule
    post["ig_published"] = True
    post["ig_media_id"] = media_id

    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

    published_count += 1
    print(f"\nProgress: {published_count}/{schedule['total']} published")


if __name__ == "__main__":
    main()
