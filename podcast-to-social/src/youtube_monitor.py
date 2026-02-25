"""
YouTube monitor.
Uses the YouTube Data API v3 to find new videos.
Quota-efficient: uses playlistItems (1 unit) instead of search (100 units).

Two modes per channel entry in channels.yaml:

  playlist_id:  poll a specific playlist directly (recommended — use this for
                podcast-tab playlists so you only pick up actual episodes,
                not shorts/clips/other uploads)

  id:           channel ID — the monitor looks up the channel's uploads
                playlist automatically (all uploads, not podcast-only)

If both are present, playlist_id takes precedence.
"""
import os
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def get_youtube_client():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not set in .env")
    return build("youtube", "v3", developerKey=api_key)


def _get_uploads_playlist_id(youtube, channel_id: str) -> str:
    """Look up the auto-generated uploads playlist for a channel ID."""
    response = youtube.channels().list(
        part="contentDetails",
        id=channel_id,
    ).execute()

    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")

    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _poll_playlist(
    youtube,
    playlist_id: str,
    channel_name: str,
    hours_back: int = 25,
) -> list[dict]:
    """
    Return videos added to `playlist_id` within the last `hours_back` hours.
    25-hour window (not 24) buffers against timezone edge cases.
    Playlist is ordered newest-first so we stop as soon as we pass the cutoff.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    videos = []
    next_page_token = None

    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            published_at = snippet.get("publishedAt", "")

            if published_at < cutoff_iso:
                return videos  # past the window — stop

            video_id = snippet["resourceId"]["videoId"]
            videos.append({
                "video_id":    video_id,
                "channel_name": channel_name,
                "title":       snippet["title"],
                "published_at": published_at,
                "description": snippet.get("description", ""),
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_recent_videos(
    youtube,
    channel: dict,
    hours_back: int = 25,
) -> list[dict]:
    """
    Return recent videos for a single channel config entry.
    Resolves the playlist to poll based on which fields are present.
    """
    name = channel["name"]

    # Prefer an explicit playlist_id (podcast tab) over the uploads playlist
    playlist_id = channel.get("playlist_id")

    if not playlist_id:
        channel_id = channel.get("id")
        if not channel_id:
            print(f"  [youtube] {name}: needs either playlist_id or id in channels.yaml")
            return []
        try:
            playlist_id = _get_uploads_playlist_id(youtube, channel_id)
        except (ValueError, HttpError) as e:
            print(f"  [youtube] {name}: could not resolve uploads playlist — {e}")
            return []

    try:
        return _poll_playlist(youtube, playlist_id, name, hours_back)
    except HttpError as e:
        print(f"  [youtube] {name}: API error — {e}")
        return []


def check_channels(channels: list[dict]) -> list[dict]:
    """
    Check every configured channel/playlist for new videos.
    Returns a flat list of video dicts enriched with topic_tags from config.
    """
    youtube = get_youtube_client()
    all_new = []

    for channel in channels:
        print(f"  Checking: {channel['name']}")
        videos = get_recent_videos(youtube, channel)

        # Optional keyword filter — useful for channels that mix podcast
        # episodes with other content in the same playlist
        keywords = [k.lower() for k in channel.get("check_keywords", [])]
        if keywords:
            videos = [
                v for v in videos
                if any(kw in v["title"].lower() for kw in keywords)
            ]

        for v in videos:
            v["topic_tags"] = channel.get("topic_tags", [])
            # Use channel id if available; fall back to playlist_id as identifier
            v["channel_id"] = channel.get("id") or channel.get("playlist_id", "")

        all_new.extend(videos)
        print(f"    → {len(videos)} new video(s)")

    return all_new
