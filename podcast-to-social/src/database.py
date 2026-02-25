"""
PostgreSQL database layer (Supabase).
Tracks processed episodes and post queue (pending → approved → posted).

Connection is configured via DATABASE_URL environment variable.
"""
import os
import json
from datetime import datetime

import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS episodes (
                        video_id       TEXT PRIMARY KEY,
                        channel_id     TEXT NOT NULL,
                        channel_name   TEXT NOT NULL,
                        title          TEXT NOT NULL,
                        published_at   TEXT NOT NULL,
                        thumbnail_path TEXT,
                        transcript     TEXT,
                        processed_at   TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id             SERIAL PRIMARY KEY,
                        video_id       TEXT NOT NULL,
                        platform       TEXT NOT NULL,
                        content        TEXT NOT NULL,
                        thumbnail_path TEXT,
                        scheduled_at   TEXT NOT NULL,
                        status         TEXT NOT NULL DEFAULT 'pending',
                        posted_at      TEXT,
                        post_url       TEXT,
                        error          TEXT,
                        created_at     TEXT NOT NULL,
                        FOREIGN KEY (video_id) REFERENCES episodes(video_id)
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_posts_status
                    ON posts(status)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_posts_scheduled
                    ON posts(scheduled_at)
                """)
    finally:
        conn.close()


# ── Episode helpers ────────────────────────────────────────────────────────────

def is_episode_processed(video_id: str) -> bool:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM episodes WHERE video_id = %s", (video_id,)
                )
                return cur.fetchone() is not None
    finally:
        conn.close()


def save_episode(
    video_id: str,
    channel_id: str,
    channel_name: str,
    title: str,
    published_at: str,
    thumbnail_path: str = None,
    transcript: str = None,
):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO episodes
                      (video_id, channel_id, channel_name, title, published_at,
                       thumbnail_path, transcript, processed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (video_id) DO UPDATE SET
                      channel_id     = EXCLUDED.channel_id,
                      channel_name   = EXCLUDED.channel_name,
                      title          = EXCLUDED.title,
                      published_at   = EXCLUDED.published_at,
                      thumbnail_path = EXCLUDED.thumbnail_path,
                      transcript     = EXCLUDED.transcript,
                      processed_at   = EXCLUDED.processed_at
                    """,
                    (
                        video_id, channel_id, channel_name, title, published_at,
                        thumbnail_path, transcript, datetime.utcnow().isoformat(),
                    ),
                )
    finally:
        conn.close()


# ── Post helpers ───────────────────────────────────────────────────────────────

def save_post(
    video_id: str,
    platform: str,
    content: dict,
    thumbnail_path: str,
    scheduled_at: str,
    auto_approve: bool = False,
):
    status = "approved" if auto_approve else "pending"
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts
                      (video_id, platform, content, thumbnail_path,
                       scheduled_at, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        video_id, platform, json.dumps(content), thumbnail_path,
                        scheduled_at, status, datetime.utcnow().isoformat(),
                    ),
                )
    finally:
        conn.close()


def get_pending_posts() -> list[dict]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT p.*, e.title AS episode_title, e.channel_name
                    FROM   posts p
                    JOIN   episodes e ON p.video_id = e.video_id
                    WHERE  p.status = 'pending'
                    ORDER  BY p.scheduled_at ASC
                    """
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_due_posts() -> list[dict]:
    """Approved posts whose scheduled time is now or in the past."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT p.*, e.title AS episode_title, e.channel_name
                    FROM   posts p
                    JOIN   episodes e ON p.video_id = e.video_id
                    WHERE  p.status = 'approved' AND p.scheduled_at <= %s
                    ORDER  BY p.scheduled_at ASC
                    """,
                    (now,),
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_post_status(
    post_id: int,
    status: str,
    post_url: str = None,
    error: str = None,
):
    posted_at = datetime.utcnow().isoformat() if status == "posted" else None
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE posts
                    SET    status = %s, post_url = %s, error = %s, posted_at = %s
                    WHERE  id = %s
                    """,
                    (status, post_url, error, posted_at, post_id),
                )
    finally:
        conn.close()


def approve_post(post_id: int):
    update_post_status(post_id, "approved")


def reject_post(post_id: int):
    update_post_status(post_id, "rejected")


def get_today_summary() -> list[dict]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT platform, status, COUNT(*) AS count
                    FROM   posts
                    WHERE  created_at::date = CURRENT_DATE
                    GROUP  BY platform, status
                    ORDER  BY platform, status
                    """
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
