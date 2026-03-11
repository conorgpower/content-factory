"""Instagram + Facebook Graph API publishing."""

import os
import time
import requests
from pathlib import Path

API_VERSION = os.getenv("META_API_VERSION", "v25.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def _get_credentials() -> tuple[str, str, str]:
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    page_id = os.environ["META_PAGE_ID"]
    ig_id = os.environ["INSTAGRAM_ACCOUNT_ID"]
    return token, page_id, ig_id


def test_auth() -> dict:
    """Verify credentials and return account info."""
    token, page_id, ig_id = _get_credentials()

    # Test page token
    page_resp = requests.get(
        f"{BASE_URL}/{page_id}",
        params={"fields": "name,id", "access_token": token},
        timeout=30,
    )
    page_resp.raise_for_status()
    page_data = page_resp.json()

    # Test Instagram account
    ig_resp = requests.get(
        f"{BASE_URL}/{ig_id}",
        params={"fields": "username,name,profile_picture_url", "access_token": token},
        timeout=30,
    )
    ig_resp.raise_for_status()
    ig_data = ig_resp.json()

    return {"page": page_data, "instagram": ig_data}


# ── Instagram ────────────────────────────────────────────────────────────────


def ig_create_reel_container(
    video_url: str,
    caption: str,
    scheduled_time: int | None = None,
) -> str:
    """Create an Instagram Reel container. Returns the container ID."""
    token, _, ig_id = _get_credentials()

    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
    }
    if scheduled_time:
        params["scheduled_publish_time"] = scheduled_time

    resp = requests.post(f"{BASE_URL}/{ig_id}/media", data=params, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]


def ig_create_image_container(
    image_url: str,
    caption: str,
    scheduled_time: int | None = None,
) -> str:
    """Create an Instagram image container. Returns the container ID."""
    token, _, ig_id = _get_credentials()

    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }
    if scheduled_time:
        params["scheduled_publish_time"] = scheduled_time

    resp = requests.post(f"{BASE_URL}/{ig_id}/media", data=params, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]


def ig_check_container_status(container_id: str) -> str:
    """Check container upload status. Returns: IN_PROGRESS, FINISHED, ERROR."""
    token, _, _ = _get_credentials()

    resp = requests.get(
        f"{BASE_URL}/{container_id}",
        params={"fields": "status_code,status", "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("status_code", "UNKNOWN")


def ig_wait_for_container(container_id: str, timeout_secs: int = 300) -> str:
    """Poll until container is ready. Returns final status."""
    start = time.time()
    while time.time() - start < timeout_secs:
        status = ig_check_container_status(container_id)
        if status == "FINISHED":
            return status
        if status == "ERROR":
            return status
        time.sleep(5)
    return "TIMEOUT"


def ig_publish(container_id: str) -> str:
    """Publish a ready container. Returns the published media ID."""
    token, _, ig_id = _get_credentials()

    resp = requests.post(
        f"{BASE_URL}/{ig_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


# ── Facebook ─────────────────────────────────────────────────────────────────


def fb_publish_video(
    video_path: str,
    description: str,
    scheduled_time: int | None = None,
) -> str:
    """Upload and publish/schedule a video to the Facebook Page. Returns post ID."""
    token, page_id, _ = _get_credentials()

    params = {
        "description": description,
        "access_token": token,
    }
    if scheduled_time:
        params["published"] = "false"
        params["scheduled_publish_time"] = str(scheduled_time)

    with open(video_path, "rb") as f:
        resp = requests.post(
            f"https://graph-video.facebook.com/{API_VERSION}/{page_id}/videos",
            data=params,
            files={"source": (Path(video_path).name, f, "video/mp4")},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.json().get("id", resp.json().get("post_id", "unknown"))


def fb_publish_image(
    image_path: str,
    caption: str,
    scheduled_time: int | None = None,
) -> str:
    """Upload and publish/schedule a photo to the Facebook Page. Returns post ID."""
    token, page_id, _ = _get_credentials()

    params = {
        "message": caption,
        "access_token": token,
    }
    if scheduled_time:
        params["published"] = "false"
        params["scheduled_publish_time"] = str(scheduled_time)

    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/{page_id}/photos",
            data=params,
            files={"source": (Path(image_path).name, f, "image/png")},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json().get("id", resp.json().get("post_id", "unknown"))
