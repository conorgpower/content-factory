#!/usr/bin/env python3
"""
X Original Posts — generate and post one tweet immediately.

Usage:
  python main.py            Generate and post a tweet
  python main.py --dry-run  Generate only (print tweet, do not post or save)

Environment variables required:
  DATABASE_URL                  Supabase PostgreSQL connection string
  ANTHROPIC_API_KEY             Claude API key
  TWITTER_API_KEY               Twitter/X API key
  TWITTER_API_SECRET            Twitter/X API secret
  TWITTER_ACCESS_TOKEN          Twitter/X access token
  TWITTER_ACCESS_TOKEN_SECRET   Twitter/X access token secret
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src import database as db
from src import generator
from src import poster


def run(dry_run: bool = False):
    db.init_db()

    recent_combos = db.get_recent_combos(limit=30)
    result = generator.generate(recent_combos)

    tweet_text = result["tweet_text"]
    reply_text = result["reply_text"]
    topic      = result["topic"]
    angle      = result["angle"]

    print(f"\n[Topic]  {topic}")
    print(f"[Angle]  {angle}")
    print(f"\n--- Tweet ---\n{tweet_text}")
    if reply_text:
        print(f"\n--- Reply ---\n{reply_text}")

    if dry_run:
        print("\n[DRY RUN] Not saving or posting.")
        return

    tweet_id = db.save_tweet(
        topic=topic,
        angle=angle,
        tweet_text=tweet_text,
        reply_text=reply_text,
    )

    try:
        url = poster.post(tweet_text=tweet_text, reply_text=reply_text)
        db.update_status(tweet_id, "posted", post_url=url)
        print(f"\nPosted: {url}")
    except Exception as e:
        db.update_status(tweet_id, "failed", error=str(e))
        print(f"\nFailed to post: {e}")
        sys.exit(1)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
