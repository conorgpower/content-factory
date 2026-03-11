"""Upload local media files to get publicly accessible URLs.

Uses Litterbox (catbox.moe) — free, no-signup, 72-hour retention.
Meta only needs to download the file once when creating the container,
so temporary hosting is fine.
"""

import requests
from pathlib import Path

LITTERBOX_URL = "https://litterbox.catbox.moe/resources/internals/api.php"


def upload_file(file_path: Path) -> str:
    """Upload a file to Litterbox and return the public URL."""
    with open(file_path, "rb") as f:
        resp = requests.post(
            LITTERBOX_URL,
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": (file_path.name, f)},
            timeout=300,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Unexpected response: {url}")
    return url
