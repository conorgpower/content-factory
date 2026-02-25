"""
Interactive post review + approval CLI.
Run:  python review.py   (or via  python main.py review)

Controls per post:
  a  → approve  (will post at scheduled time)
  r  → reject   (won't post)
  s  → skip     (leave as pending, review later)
  q  → quit session

When AUTO_POST=true, all posts skip review and this file is not used.
"""
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich import box
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from src import database as db

console = Console()


def _render_x_thread(content: dict):
    tweets = content.get("tweets", [])
    lines = []
    for i, tweet in enumerate(tweets, 1):
        char_count = len(tweet)
        colour = "green" if char_count <= 280 else "red"
        lines.append(f"[dim]{i}.[/dim] {tweet}")
        lines.append(f"[{colour}]   {char_count} chars[/{colour}]\n")
    console.print(
        Panel("\n".join(lines).strip(), title="[cyan]X Thread[/cyan]", border_style="cyan")
    )


def _render_reddit_post(content: dict):
    title = content.get("title", "")
    body  = content.get("body",  "")
    subs  = content.get("suggested_subreddits", [])
    console.print(
        Panel(
            f"[bold]Title:[/bold] {title}\n\n"
            f"[bold]Subreddits:[/bold] {', '.join(subs)}\n\n"
            f"[bold]Body:[/bold]\n{body}",
            title="[orange1]Reddit Post[/orange1]",
            border_style="orange1",
        )
    )


def _render_episode_header(post: dict, index: int, total: int):
    console.print(Rule(f"[bold blue]Post {index} of {total}"))
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column(style="bold dim", width=14)
    table.add_column()
    table.add_row("Episode",  post["episode_title"])
    table.add_row("Channel",  post["channel_name"])
    table.add_row("Platform", post["platform"].upper())
    table.add_row("Scheduled", post["scheduled_at"] + " UTC")
    if post.get("thumbnail_path"):
        table.add_row("Thumbnail", post["thumbnail_path"])
    console.print(table)


def run_review():
    db.init_db()
    pending = db.get_pending_posts()

    if not pending:
        console.print("\n[green]No pending posts to review.[/green]\n")
        return

    console.print(f"\n[bold]Pending posts:[/bold] {len(pending)}\n")

    approved = rejected = skipped = 0

    for i, post in enumerate(pending, 1):
        content = json.loads(post["content"])

        _render_episode_header(post, i, len(pending))

        if post["platform"] == "x":
            _render_x_thread(content)
        elif post["platform"] == "reddit":
            _render_reddit_post(content)

        choice = Prompt.ask(
            "\n  [a]pprove  [r]eject  [s]kip  [q]uit",
            choices=["a", "r", "s", "q"],
            default="s",
        )

        if choice == "a":
            db.approve_post(post["id"])
            console.print("  [green]✓ Approved[/green]")
            approved += 1
        elif choice == "r":
            db.reject_post(post["id"])
            console.print("  [red]✗ Rejected[/red]")
            rejected += 1
        elif choice == "s":
            console.print("  [yellow]→ Skipped[/yellow]")
            skipped += 1
        elif choice == "q":
            console.print("\n  [dim]Session ended early.[/dim]")
            break

        console.print()

    console.print(Rule())
    console.print(
        f"\n[bold]Done:[/bold] "
        f"[green]{approved} approved[/green]  "
        f"[red]{rejected} rejected[/red]  "
        f"[yellow]{skipped} skipped[/yellow]\n"
    )

    if approved:
        console.print(
            "[dim]Approved posts will go out at their scheduled times "
            "when  python main.py post  runs.[/dim]\n"
        )


if __name__ == "__main__":
    run_review()
