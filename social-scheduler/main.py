"""
Social Scheduler — Schedule mass content to Instagram Reels + Facebook Pages.

Usage:
    python main.py test-auth                  # Verify API credentials
    python main.py load                       # Load content from mass-content-maker
    python main.py captions                   # Review/edit captions
    python main.py upload                     # Upload videos to get public URLs (for Instagram)
    python main.py schedule --start 2026-03-12 --per-day 2 --time 12:00
    python main.py status                     # Check post statuses
    python main.py publish-test --index 0     # Publish a single post immediately (for testing)
    python main.py reset                      # Clear database and start over
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

load_dotenv(Path(__file__).parent / ".env")

from src.database import load_posts, get_all_posts, update_post, reset_db, get_db
from src.uploader import upload_file
from src.publisher import (
    test_auth,
    ig_create_reel_container,
    ig_create_image_container,
    ig_wait_for_container,
    ig_publish,
    fb_publish_video,
    fb_publish_image,
)

console = Console()

CONTENT_DIR = Path(__file__).parent.parent / "mass-content-maker"
VARIATIONS_FILE = CONTENT_DIR / "variations.json"
VIDEO_DIR = CONTENT_DIR / "output" / "videos"
IMAGE_DIR = CONTENT_DIR / "output"


def cmd_test_auth():
    """Verify API credentials work."""
    try:
        info = test_auth()
        console.print(f"\n[green]Page:[/green] {info['page'].get('name')} (ID: {info['page'].get('id')})")
        console.print(f"[green]Instagram:[/green] @{info['instagram'].get('username')} — {info['instagram'].get('name')}\n")
    except Exception as e:
        console.print(f"\n[red]Auth failed:[/red] {e}\n")
        sys.exit(1)


def cmd_load():
    """Load content from mass-content-maker into the database."""
    if not VARIATIONS_FILE.exists():
        console.print(f"[red]Not found:[/red] {VARIATIONS_FILE}")
        sys.exit(1)

    with open(VARIATIONS_FILE) as f:
        variations = json.load(f)

    result = load_posts(variations, VIDEO_DIR, IMAGE_DIR)
    if result == -1:
        console.print("[yellow]Database already has posts. Use 'reset' first to reload.[/yellow]")
        return

    console.print(f"[green]Loaded {result} posts into database.[/green]")

    # Show summary
    posts = get_all_posts()
    has_video = sum(1 for p in posts if p["video_path"])
    has_image = sum(1 for p in posts if p["image_path"])
    console.print(f"  Videos found: {has_video}/{len(posts)}")
    console.print(f"  Images found: {has_image}/{len(posts)}")


def cmd_captions():
    """Review and edit captions."""
    posts = get_all_posts()
    if not posts:
        console.print("[red]No posts loaded. Run 'load' first.[/red]")
        return

    table = Table(title="Post Captions", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Metric", width=25)
    table.add_column("Caption", width=70)

    for p in posts:
        caption_preview = p["caption"][:100] + "..." if len(p["caption"]) > 100 else p["caption"]
        table.add_row(str(p["id"]), p["metric"], caption_preview)

    console.print(table)
    console.print(f"\nTo edit a caption, run: python main.py edit-caption --id <post_id> --caption 'new caption'")


def cmd_edit_caption(post_id: int, caption: str):
    """Edit a single post's caption."""
    update_post(post_id, caption=caption)
    console.print(f"[green]Updated caption for post #{post_id}[/green]")


def cmd_upload():
    """Upload video files to get public URLs for Instagram."""
    posts = get_all_posts()
    need_upload = [p for p in posts if p["video_path"] and not p["public_url"]]

    if not need_upload:
        console.print("[yellow]All posts already have public URLs (or no videos to upload).[/yellow]")
        return

    console.print(f"Uploading {len(need_upload)} videos to get public URLs...\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading", total=len(need_upload))

        for p in need_upload:
            video_path = Path(p["video_path"])
            if not video_path.exists():
                console.print(f"  [red]Missing:[/red] {video_path.name}")
                progress.advance(task)
                continue

            try:
                url = upload_file(video_path)
                update_post(p["id"], public_url=url)
                progress.advance(task)
            except Exception as e:
                console.print(f"  [red]Failed {video_path.name}:[/red] {e}")
                progress.advance(task)

    uploaded = len([p for p in get_all_posts() if p["public_url"]])
    console.print(f"\n[green]Done. {uploaded}/{len(posts)} posts have public URLs.[/green]")


def cmd_schedule(start_date: str, per_day: int, post_time: str, platforms: str):
    """Schedule posts on Instagram and/or Facebook."""
    posts = get_all_posts()
    unscheduled = [p for p in posts if p["ig_status"] == "pending" or p["fb_status"] == "pending"]

    if not unscheduled:
        console.print("[yellow]All posts are already scheduled.[/yellow]")
        return

    do_ig = "instagram" in platforms or "ig" in platforms
    do_fb = "facebook" in platforms or "fb" in platforms

    if do_ig:
        no_url = [p for p in unscheduled if not p["public_url"] and p["video_path"]]
        if no_url:
            console.print(f"[red]{len(no_url)} posts missing public URLs. Run 'upload' first.[/red]")
            return

    # Build schedule — spread posts evenly across the day
    start_hour, start_minute = map(int, post_time.split(":"))
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_hour = 22  # Last post no later than 10pm
    total_minutes = (end_hour * 60) - (start_hour * 60 + start_minute)
    spacing_minutes = total_minutes // max(per_day - 1, 1)
    slot = 0

    console.print(f"\nScheduling {len(unscheduled)} posts ({per_day}/day starting {start_date} at {post_time})...")
    console.print(f"Spacing: ~{spacing_minutes} min apart ({post_time}–{end_hour}:00)")
    console.print(f"Platforms: {'Instagram' if do_ig else ''} {'Facebook' if do_fb else ''}\n")

    errors = 0
    for i, post in enumerate(unscheduled):
        # Calculate scheduled time
        day_offset = slot // per_day
        time_in_day = slot % per_day
        minutes_offset = start_hour * 60 + start_minute + time_in_day * spacing_minutes
        publish_dt = current_date + timedelta(days=day_offset, minutes=minutes_offset)
        unix_time = int(publish_dt.timestamp())
        slot += 1

        # Ensure at least 10 minutes in the future
        if unix_time < int(time.time()) + 600:
            console.print(f"  [red]Post #{post['id']}: Scheduled time is in the past, skipping.[/red]")
            errors += 1
            continue

        update_post(post["id"], scheduled_time=publish_dt.isoformat())

        # ── Instagram ──
        if do_ig and post["video_path"] and post["public_url"]:
            try:
                container_id = ig_create_reel_container(
                    video_url=post["public_url"],
                    caption=post["caption"],
                    scheduled_time=unix_time,
                )
                update_post(post["id"], ig_container_id=container_id, ig_status="container_created")

                # Wait for container to be ready
                status = ig_wait_for_container(container_id, timeout_secs=120)
                if status == "FINISHED":
                    media_id = ig_publish(container_id)
                    update_post(post["id"], ig_post_id=media_id, ig_status="scheduled")
                    console.print(f"  [green]IG #{post['id']}[/green] scheduled for {publish_dt.strftime('%Y-%m-%d %H:%M')}")
                else:
                    update_post(post["id"], ig_status=f"error:{status}")
                    console.print(f"  [red]IG #{post['id']} container failed: {status}[/red]")
                    errors += 1
            except Exception as e:
                update_post(post["id"], ig_status=f"error:{e}")
                console.print(f"  [red]IG #{post['id']} failed: {e}[/red]")
                errors += 1
        elif do_ig and post["image_path"]:
            try:
                # Upload image for public URL if needed
                if not post["public_url"]:
                    url = upload_file(Path(post["image_path"]))
                    update_post(post["id"], public_url=url)
                    post["public_url"] = url

                container_id = ig_create_image_container(
                    image_url=post["public_url"],
                    caption=post["caption"],
                    scheduled_time=unix_time,
                )
                update_post(post["id"], ig_container_id=container_id, ig_status="container_created")

                status = ig_wait_for_container(container_id, timeout_secs=60)
                if status == "FINISHED":
                    media_id = ig_publish(container_id)
                    update_post(post["id"], ig_post_id=media_id, ig_status="scheduled")
                    console.print(f"  [green]IG #{post['id']}[/green] (image) scheduled for {publish_dt.strftime('%Y-%m-%d %H:%M')}")
                else:
                    update_post(post["id"], ig_status=f"error:{status}")
                    console.print(f"  [red]IG #{post['id']} container failed: {status}[/red]")
                    errors += 1
            except Exception as e:
                update_post(post["id"], ig_status=f"error:{e}")
                console.print(f"  [red]IG #{post['id']} failed: {e}[/red]")
                errors += 1

        # ── Facebook ──
        if do_fb and post["video_path"]:
            try:
                fb_id = fb_publish_video(
                    video_path=post["video_path"],
                    description=post["caption"],
                    scheduled_time=unix_time,
                )
                update_post(post["id"], fb_post_id=fb_id, fb_status="scheduled")
                console.print(f"  [green]FB #{post['id']}[/green] scheduled for {publish_dt.strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                update_post(post["id"], fb_status=f"error:{e}")
                console.print(f"  [red]FB #{post['id']} failed: {e}[/red]")
                errors += 1
        elif do_fb and post["image_path"]:
            try:
                fb_id = fb_publish_image(
                    image_path=post["image_path"],
                    caption=post["caption"],
                    scheduled_time=unix_time,
                )
                update_post(post["id"], fb_post_id=fb_id, fb_status="scheduled")
                console.print(f"  [green]FB #{post['id']}[/green] (image) scheduled for {publish_dt.strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                update_post(post["id"], fb_status=f"error:{e}")
                console.print(f"  [red]FB #{post['id']} failed: {e}[/red]")
                errors += 1

    console.print(f"\n[green]Done![/green] {len(unscheduled) - errors} scheduled, {errors} errors.")


def cmd_status():
    """Show status of all posts."""
    posts = get_all_posts()
    if not posts:
        console.print("[red]No posts loaded. Run 'load' first.[/red]")
        return

    table = Table(title=f"Post Status ({len(posts)} total)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Metric", width=22)
    table.add_column("Scheduled", width=18)
    table.add_column("IG Status", width=18)
    table.add_column("FB Status", width=18)
    table.add_column("URL", width=8)

    for p in posts:
        ig_style = "green" if p["ig_status"] == "scheduled" else ("red" if "error" in (p["ig_status"] or "") else "yellow")
        fb_style = "green" if p["fb_status"] == "scheduled" else ("red" if "error" in (p["fb_status"] or "") else "yellow")
        url_status = "[green]yes[/green]" if p["public_url"] else "[dim]no[/dim]"
        sched = p["scheduled_time"][:16] if p["scheduled_time"] else "[dim]—[/dim]"

        table.add_row(
            str(p["id"]),
            p["metric"][:22],
            sched,
            f"[{ig_style}]{p['ig_status']}[/{ig_style}]",
            f"[{fb_style}]{p['fb_status']}[/{fb_style}]",
            url_status,
        )

    console.print(table)

    # Summary
    ig_scheduled = sum(1 for p in posts if p["ig_status"] == "scheduled")
    fb_scheduled = sum(1 for p in posts if p["fb_status"] == "scheduled")
    ig_errors = sum(1 for p in posts if "error" in (p["ig_status"] or ""))
    fb_errors = sum(1 for p in posts if "error" in (p["fb_status"] or ""))

    console.print(f"\nIG: {ig_scheduled} scheduled, {ig_errors} errors")
    console.print(f"FB: {fb_scheduled} scheduled, {fb_errors} errors")


def cmd_publish_next(platforms: str):
    """Publish the next unpublished post immediately."""
    do_ig = "instagram" in platforms or "ig" in platforms
    do_fb = "facebook" in platforms or "fb" in platforms

    posts = get_all_posts()
    # Find next post where at least one target platform is still pending
    post = None
    for p in posts:
        if (do_ig and p["ig_status"] == "pending") or (do_fb and p["fb_status"] == "pending"):
            post = p
            break

    if not post:
        console.print("[yellow]No more posts to publish.[/yellow]")
        return

    console.print(f"\nPublishing post #{post['id']}: {post['metric']}")
    console.print(f"Caption: {post['caption'][:80]}...\n")

    # Upload if needed
    if post["video_path"] and not post["public_url"]:
        console.print("Uploading video for public URL...")
        url = upload_file(Path(post["video_path"]))
        update_post(post["id"], public_url=url)
        post["public_url"] = url

    # Instagram
    if do_ig and post["ig_status"] == "pending" and post["video_path"] and post["public_url"]:
        console.print("[bold]Instagram Reel:[/bold]", end=" ")
        try:
            container_id = ig_create_reel_container(post["public_url"], post["caption"])
            update_post(post["id"], ig_container_id=container_id, ig_status="processing")

            status = ig_wait_for_container(container_id, timeout_secs=180)
            if status == "FINISHED":
                media_id = ig_publish(container_id)
                update_post(post["id"], ig_post_id=media_id, ig_status="published")
                console.print(f"[green]Published! (ID: {media_id})[/green]")
            else:
                update_post(post["id"], ig_status=f"error:{status}")
                console.print(f"[red]Failed: {status}[/red]")
        except Exception as e:
            update_post(post["id"], ig_status=f"error:{e}")
            console.print(f"[red]Error: {e}[/red]")

    # Facebook
    if do_fb and post["fb_status"] == "pending" and post["video_path"]:
        console.print("[bold]Facebook Video:[/bold]", end=" ")
        try:
            fb_id = fb_publish_video(post["video_path"], post["caption"])
            update_post(post["id"], fb_post_id=fb_id, fb_status="published")
            console.print(f"[green]Published! (ID: {fb_id})[/green]")
        except Exception as e:
            update_post(post["id"], fb_status=f"error:{e}")
            console.print(f"[red]Error: {e}[/red]")

    # Summary
    all_posts = get_all_posts()
    ig_done = sum(1 for p in all_posts if p["ig_status"] == "published")
    fb_done = sum(1 for p in all_posts if p["fb_status"] == "published")
    console.print(f"\nProgress: IG {ig_done}/{len(all_posts)} | FB {fb_done}/{len(all_posts)}")


def cmd_publish_test(index: int):
    """Publish a single post immediately for testing."""
    posts = get_all_posts()
    if index >= len(posts):
        console.print(f"[red]Invalid index. Max is {len(posts)-1}[/red]")
        return

    post = posts[index]
    console.print(f"\nTest publishing post #{post['id']}: {post['metric']}")
    console.print(f"Caption: {post['caption'][:80]}...\n")

    # Upload if needed
    if post["video_path"] and not post["public_url"]:
        console.print("Uploading video for public URL...")
        url = upload_file(Path(post["video_path"]))
        update_post(post["id"], public_url=url)
        post["public_url"] = url
        console.print(f"  URL: {url}")

    # Instagram
    if post["video_path"] and post["public_url"]:
        console.print("\n[bold]Instagram Reel:[/bold]")
        try:
            container_id = ig_create_reel_container(post["public_url"], post["caption"])
            console.print(f"  Container: {container_id}")
            console.print("  Waiting for processing...", end="")

            status = ig_wait_for_container(container_id)
            console.print(f" {status}")

            if status == "FINISHED":
                media_id = ig_publish(container_id)
                update_post(post["id"], ig_post_id=media_id, ig_status="published")
                console.print(f"  [green]Published! Media ID: {media_id}[/green]")
            else:
                console.print(f"  [red]Failed: {status}[/red]")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    # Facebook
    if post["video_path"]:
        console.print("\n[bold]Facebook Video:[/bold]")
        try:
            fb_id = fb_publish_video(post["video_path"], post["caption"])
            update_post(post["id"], fb_post_id=fb_id, fb_status="published")
            console.print(f"  [green]Published! Post ID: {fb_id}[/green]")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")


def cmd_reset():
    """Clear the database."""
    reset_db()
    console.print("[green]Database cleared.[/green]")


def main():
    parser = argparse.ArgumentParser(description="Schedule mass content to Instagram + Facebook")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test-auth", help="Verify API credentials")
    sub.add_parser("load", help="Load content from mass-content-maker")
    sub.add_parser("captions", help="Review captions")

    edit_cap = sub.add_parser("edit-caption", help="Edit a post caption")
    edit_cap.add_argument("--id", type=int, required=True)
    edit_cap.add_argument("--caption", type=str, required=True)

    sub.add_parser("upload", help="Upload videos for public URLs")

    sched = sub.add_parser("schedule", help="Schedule posts")
    sched.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    sched.add_argument("--per-day", type=int, default=2, help="Posts per day (default: 2)")
    sched.add_argument("--time", default="12:00", help="Time of day for first post (HH:MM, default: 12:00)")
    sched.add_argument("--platforms", default="instagram,facebook", help="Platforms: instagram,facebook (default: both)")

    sub.add_parser("status", help="Check post statuses")

    pub_next = sub.add_parser("publish-next", help="Publish next unpublished post immediately")
    pub_next.add_argument("--platforms", default="instagram", help="Platforms: instagram,facebook (default: instagram)")

    pub_test = sub.add_parser("publish-test", help="Publish one post immediately")
    pub_test.add_argument("--index", type=int, default=0, help="Post index (default: 0)")

    sub.add_parser("reset", help="Clear database")

    args = parser.parse_args()

    if args.command == "test-auth":
        cmd_test_auth()
    elif args.command == "load":
        cmd_load()
    elif args.command == "captions":
        cmd_captions()
    elif args.command == "edit-caption":
        cmd_edit_caption(args.id, args.caption)
    elif args.command == "upload":
        cmd_upload()
    elif args.command == "schedule":
        cmd_schedule(args.start, args.per_day, args.time, args.platforms)
    elif args.command == "status":
        cmd_status()
    elif args.command == "publish-next":
        cmd_publish_next(args.platforms)
    elif args.command == "publish-test":
        cmd_publish_test(args.index)
    elif args.command == "reset":
        cmd_reset()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
