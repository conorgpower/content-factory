"""
PostgreSQL database layer (Supabase).
Tracks generated original tweets and their post status.

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
                    CREATE TABLE IF NOT EXISTS original_tweets (
                        id          SERIAL PRIMARY KEY,
                        topic       TEXT NOT NULL,
                        angle       TEXT NOT NULL,
                        tweet_text  TEXT NOT NULL,
                        reply_text  TEXT,
                        status      TEXT NOT NULL DEFAULT 'pending',
                        posted_at   TEXT,
                        post_url    TEXT,
                        error       TEXT,
                        created_at  TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_original_tweets_status
                    ON original_tweets(status)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_original_tweets_created
                    ON original_tweets(created_at)
                """)
    finally:
        conn.close()


def get_recent_combos(limit: int = 30) -> list[tuple[str, str]]:
    """Return (topic, angle) pairs from the most recent N tweets."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic, angle
                    FROM   original_tweets
                    ORDER  BY created_at DESC
                    LIMIT  %s
                    """,
                    (limit,),
                )
                return [(row[0], row[1]) for row in cur.fetchall()]
    finally:
        conn.close()


def save_tweet(
    topic: str,
    angle: str,
    tweet_text: str,
    reply_text: str = None,
) -> int:
    """Save a generated tweet and return its id."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO original_tweets
                      (topic, angle, tweet_text, reply_text, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        topic, angle, tweet_text, reply_text,
                        datetime.utcnow().isoformat(),
                    ),
                )
                return cur.fetchone()[0]
    finally:
        conn.close()


def update_status(
    tweet_id: int,
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
                    UPDATE original_tweets
                    SET    status = %s, post_url = %s, error = %s, posted_at = %s
                    WHERE  id = %s
                    """,
                    (status, post_url, error, posted_at, tweet_id),
                )
    finally:
        conn.close()
