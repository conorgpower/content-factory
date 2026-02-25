#!/usr/bin/env python3
"""
Podcast-to-Social — main entry point.

Commands:
  python main.py discover   Find new episodes and generate posts
  python main.py post       Post any approved content that is due now
  python main.py review     Interactive review/approval CLI
  python main.py status     Show today's post summary

Environment:
  AUTO_POST=false   Set to 'true' to skip manual review (fully automated)
  DRY_RUN=false     Set to 'true' to generate posts without saving/posting
"""
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent))

from src import database as db
from src import (
    youtube_monitor,
    transcript_extractor,
    thumbnail_fetcher,
    post_generator,
    scheduler,
    x_poster,
    reddit_poster,
)

BASE = Path(__file__).parent
CHANNELS_CONFIG   = BASE / "config" / "channels.yaml"
SUBREDDITS_CONFIG = BASE / "config" / "subreddits.yaml"
SCHEDULE_CONFIG   = BASE / "config" / "schedule.yaml"


# ── Config loader ──────────────────────────────────────────────────────────────

def load_config() -> tuple[list, dict, dict]:
    with open(CHANNELS_CONFIG) as f:
        channels = yaml.safe_load(f)["channels"]
    with open(SUBREDDITS_CONFIG) as f:
        subreddits = yaml.safe_load(f)
    with open(SCHEDULE_CONFIG) as f:
        schedule = yaml.safe_load(f)
    return channels, subreddits, schedule


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_discover():
    """Discover new episodes and generate posts."""
    print("\n=== Discovery run ===")

    channels, subreddits_cfg, schedule_cfg = load_config()
    auto_post = os.getenv("AUTO_POST", "false").lower() == "true"
    dry_run   = os.getenv("DRY_RUN",   "false").lower() == "true"

    if dry_run:
        print("[DRY_RUN] Posts will be generated but NOT saved.")
    if auto_post:
        print("[AUTO_POST] Posts will be approved automatically.")

    db.init_db()

    # 1. Find new videos across all channels
    print(f"\nChecking {len(channels)} channel(s)...")
    new_videos = youtube_monitor.check_channels(channels)
    print(f"Total new videos found: {len(new_videos)}")

    # 2. Filter already-processed
    unprocessed = [v for v in new_videos if not db.is_episode_processed(v["video_id"])]
    print(f"Unprocessed: {len(unprocessed)}")

    if not unprocessed:
        print("Nothing new to process today.")
        return

    # 3. Calculate schedule slots (one X slot + one Reddit slot per episode)
    x_slots = scheduler.get_schedule_slots(
        count=len(unprocessed),
        schedule_config=schedule_cfg,
    )
    reddit_stagger = schedule_cfg.get("reddit_stagger_minutes", 30)

    # 4. Process each video
    for i, video in enumerate(unprocessed):
        print(f"\n[{i+1}/{len(unprocessed)}] {video['title']}")

        # Transcript
        transcript = transcript_extractor.get_transcript(video["video_id"])
        if not transcript:
            print("  No transcript — falling back to description")
            transcript = video.get("description", "").strip()
        if not transcript:
            print("  No content available, skipping")
            continue

        # Thumbnail
        thumbnail_path = thumbnail_fetcher.download_thumbnail(
            video["video_id"], video["title"]
        )
        thumb_str = str(thumbnail_path) if thumbnail_path else None

        # Summarise the full episode (one API call, shared by both posts)
        print("  Summarising episode...")
        summary = post_generator.summarize_episode(
            channel_name=video["channel_name"],
            episode_title=video["title"],
            transcript=transcript,
        )
        if not summary:
            print("  Summarisation failed, skipping")
            continue

        # Save episode record (store the clean summary, not the raw transcript)
        import json as _json
        summary_text = _json.dumps(summary)
        if not dry_run:
            db.save_episode(
                video_id=video["video_id"],
                channel_id=video["channel_id"],
                channel_name=video["channel_name"],
                title=video["title"],
                published_at=video["published_at"],
                thumbnail_path=thumb_str,
                transcript=summary_text,
            )

        x_slot      = x_slots[i]
        reddit_slot = scheduler.add_stagger(x_slot, reddit_stagger)

        # Generate X post (from summary, not raw transcript)
        print("  Generating X thread...")
        x_content = post_generator.generate_x_post(
            channel_name=video["channel_name"],
            episode_title=video["title"],
            summary=summary,
        )
        if x_content and not dry_run:
            db.save_post(
                video_id=video["video_id"],
                platform="x",
                content=x_content,
                thumbnail_path=thumb_str,
                scheduled_at=x_slot,
                auto_approve=auto_post,
            )
            print(f"  X post queued → {x_slot} UTC")
        elif x_content and dry_run:
            print(f"  [DRY_RUN] X thread:")
            for j, tweet in enumerate(x_content.get("tweets", []), 1):
                print(f"    [{j}] {tweet}")

        # Reddit post generation disabled — uncomment to re-enable
        # if reddit_poster.is_configured():
        #     print("  Generating Reddit post...")
        #     reddit_content = post_generator.generate_reddit_post(
        #         channel_name=video["channel_name"],
        #         episode_title=video["title"],
        #         summary=summary,
        #         topic_tags=video.get("topic_tags", []),
        #     )
        #     if reddit_content and not dry_run:
        #         db.save_post(
        #             video_id=video["video_id"],
        #             platform="reddit",
        #             content=reddit_content,
        #             thumbnail_path=thumb_str,
        #             scheduled_at=reddit_slot,
        #             auto_approve=auto_post,
        #         )
        #         print(f"  Reddit post queued → {reddit_slot} UTC")
        #     elif reddit_content and dry_run:
        #         print(f"  [DRY_RUN] Reddit post:")
        #         print(f"    Title: {reddit_content.get('title', '')}")
        #         print(f"    Subreddits: {', '.join(reddit_content.get('suggested_subreddits', []))}")

    print("\n=== Discovery complete ===")
    if not auto_post and not dry_run:
        print("Run  python main.py review  to approve posts before they go out.")


def cmd_post():
    """Post any approved content that is currently due."""
    print("\n=== Posting run ===")
    db.init_db()

    _, subreddits_cfg, _ = load_config()
    due = db.get_due_posts()

    if not due:
        print("No posts due right now.")
        return

    print(f"Found {len(due)} post(s) due")

    for post in due:
        content = json.loads(post["content"])
        platform = post["platform"].upper()
        print(f"\n  Posting {platform}: {post['episode_title']}")

        try:
            if post["platform"] == "x":
                url = x_poster.post_thread(
                    tweets=content["tweets"],
                    thumbnail_path=post.get("thumbnail_path"),
                    video_id=post["video_id"],
                )
                db.update_post_status(post["id"], "posted", post_url=url)
                print(f"  ✓ Posted: {url}")

            elif post["platform"] == "reddit":
                if not reddit_poster.is_configured():
                    print("  Reddit not configured — skipping")
                    continue
                urls = reddit_poster.post_to_subreddits(
                    title=content["title"],
                    body=content["body"],
                    suggested_subreddits=content.get("suggested_subreddits", []),
                    subreddits_config=subreddits_cfg,
                )
                db.update_post_status(
                    post["id"], "posted", post_url=",".join(urls)
                )
                print(f"  ✓ Posted to: {', '.join(urls)}")

        except Exception as e:
            db.update_post_status(post["id"], "failed", error=str(e))
            print(f"  ✗ FAILED: {e}")

    print("\n=== Posting run complete ===")


def cmd_review():
    """Launch the interactive review/approval CLI."""
    from review import run_review
    run_review()


def cmd_status():
    """Print today's post status summary."""
    db.init_db()
    summary = db.get_today_summary()

    if not summary:
        print("\nNo posts created today.")
        return

    print("\n=== Today's post summary ===")
    for row in summary:
        print(f"  {row['platform'].upper():<8} {row['status']:<12} {row['count']}")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

COMMANDS = {
    "discover": cmd_discover,
    "post":     cmd_post,
    "review":   cmd_review,
    "status":   cmd_status,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
