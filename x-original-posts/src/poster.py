"""
X (Twitter) poster for original tweets.
Posts a single tweet with an optional reply that doubles down on it.
Uses API v2 via tweepy.
"""
import os

import tweepy


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )


def post(tweet_text: str, reply_text: str = None) -> str:
    """
    Post a tweet and optional reply.
    Returns the URL of the main tweet.
    """
    client = _get_client()

    response = client.create_tweet(text=tweet_text)
    tweet_id = response.data["id"]

    me = client.get_me()
    username = me.data.username
    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"

    if reply_text:
        client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet_id,
        )

    return tweet_url
