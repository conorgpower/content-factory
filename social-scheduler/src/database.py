"""SQLite database for tracking social media posts."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "scheduler.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            variation_index INTEGER NOT NULL,
            metric          TEXT NOT NULL,
            hook            TEXT NOT NULL,
            caption         TEXT NOT NULL,
            video_path      TEXT,
            image_path      TEXT,
            public_url      TEXT,
            -- Scheduling
            scheduled_time  TEXT,
            -- Instagram
            ig_container_id TEXT,
            ig_post_id      TEXT,
            ig_status       TEXT DEFAULT 'pending',
            -- Facebook
            fb_post_id      TEXT,
            fb_status       TEXT DEFAULT 'pending',
            -- Meta
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def load_posts(variations: list[dict], video_dir: Path, image_dir: Path) -> int:
    """Load variations into the database, matching with video/image files."""
    conn = get_db()

    # Check if already loaded
    count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    if count > 0:
        conn.close()
        return -1  # Already loaded

    loaded = 0
    for i, v in enumerate(variations):
        slug = v["metric"].lower().replace(" ", "-").replace("/", "-")
        video_file = video_dir / f"{i:02d}-{slug}.mp4"
        image_file = image_dir / f"{i:02d}-{slug}.png"

        caption = f"{v['hook']}\n\n{v.get('hook_sub', '')}\n\nDownload Seneca Chat - link in bio"

        conn.execute("""
            INSERT INTO posts (variation_index, metric, hook, caption, video_path, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            i,
            v["metric"],
            v["hook"],
            caption,
            str(video_file) if video_file.exists() else None,
            str(image_file) if image_file.exists() else None,
        ))
        loaded += 1

    conn.commit()
    conn.close()
    return loaded


def get_all_posts() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM posts ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_posts_by_status(ig_status: str = None, fb_status: str = None) -> list[dict]:
    conn = get_db()
    conditions = []
    params = []
    if ig_status:
        conditions.append("ig_status = ?")
        params.append(ig_status)
    if fb_status:
        conditions.append("fb_status = ?")
        params.append(fb_status)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(f"SELECT * FROM posts WHERE {where} ORDER BY id", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_post(post_id: int, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [post_id]
    conn.execute(f"UPDATE posts SET {sets}, updated_at = datetime('now') WHERE id = ?", values)
    conn.commit()
    conn.close()


def reset_db():
    conn = get_db()
    conn.execute("DELETE FROM posts")
    conn.commit()
    conn.close()
