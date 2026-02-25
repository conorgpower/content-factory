"""
X (Twitter) poster.
Posts a thread of tweets, attaches the episode thumbnail to the first tweet.

Thread posting uses API v2 (tweepy.Client).
Media upload still requires the v1.1 endpoint (tweepy.API) —
this is a Twitter/X API limitation, not a tweepy limitation.
"""
import os
from pathlib import Path

import tweepy


def _get_v2_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )


def _get_v1_api() -> tweepy.API:
    """v1.1 API — only used for media uploads."""
    auth = tweepy.OAuth1UserHandler(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"],
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )
    return tweepy.API(auth)


def _upload_media(image_path: str) -> str | None:
    """Upload an image and return the media_id_string, or None on failure."""
    if not image_path or not Path(image_path).exists():
        return None
    try:
        api = _get_v1_api()
        media = api.media_upload(filename=image_path)
        return media.media_id_string
    except Exception as e:
        print(f"    [x_poster] Media upload failed: {e}")
        return None


def post_thread(
    tweets: list[str],
    thumbnail_path: str = None,
    video_id: str = None,
) -> str | None:
    """
    Post a list of tweet strings as a thread.
    - Thumbnail is attached to the first tweet.
    - [LINK] placeholder in any tweet is replaced with the YouTube URL.
    Returns the URL of the first tweet, or None on failure.
    """
    if not tweets:
        return None

    youtube_url = f"https://youtu.be/{video_id}" if video_id else ""
    tweets = [t.replace("[LINK]", youtube_url) for t in tweets]

    # Re-download thumbnail if the local file is missing (e.g., GitHub Actions
    # ephemeral runner — discover and post run in separate jobs).
    if thumbnail_path and not Path(thumbnail_path).exists() and video_id:
        from src import thumbnail_fetcher
        downloaded = thumbnail_fetcher.download_thumbnail(video_id, video_id)
        if downloaded:
            thumbnail_path = str(downloaded)

    client = _get_v2_client()
    media_id = _upload_media(thumbnail_path)

    previous_tweet_id = None
    first_tweet_url = None

    for i, text in enumerate(tweets):
        kwargs: dict = {"text": text}

        if i == 0 and media_id:
            kwargs["media_ids"] = [media_id]

        if previous_tweet_id:
            kwargs["in_reply_to_tweet_id"] = previous_tweet_id

        response = client.create_tweet(**kwargs)
        tweet_id = response.data["id"]

        if i == 0:
            me = client.get_me()
            username = me.data.username
            first_tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"

        previous_tweet_id = tweet_id

    return first_tweet_url
