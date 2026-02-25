"""
Reddit poster.
Posts to a filtered set of subreddits derived from the episode's topic tags
and the subreddits.yaml allow-list.
Caps at 3 subreddits per episode to avoid spam flags.
"""
import os

import praw


def is_configured() -> bool:
    return all(os.environ.get(k) for k in (
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
        "REDDIT_USERNAME", "REDDIT_PASSWORD",
    ))


def _get_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "podcast-to-social/1.0"),
    )


def _allowed_subreddits(
    suggested: list[str],
    subreddits_config: dict,
    cap: int = 3,
) -> list[str]:
    """
    Filter AI-suggested subreddits against the config allow-list.
    Only includes subreddits where promo_allowed is true.
    Returns at most `cap` subreddits.
    """
    allowed: dict[str, dict] = {}
    for tag_subs in subreddits_config.get("topic_tags", {}).values():
        for sub in tag_subs:
            if sub.get("promo_allowed", True):
                key = sub["name"].lower().lstrip("r/")
                allowed[key] = sub

    result = []
    for name in suggested:
        clean = name.lower().lstrip("r/")
        if clean in allowed and len(result) < cap:
            result.append(name if name.startswith("r/") else f"r/{name}")

    return result


def post_to_subreddits(
    title: str,
    body: str,
    suggested_subreddits: list[str],
    subreddits_config: dict,
) -> list[str]:
    """
    Submit a text post to each allowed subreddit.
    Returns a list of post permalink URLs.
    """
    reddit = _get_reddit()
    targets = _allowed_subreddits(suggested_subreddits, subreddits_config)

    if not targets:
        print("    [reddit] No allowed subreddits found for this post")
        return []

    urls = []
    for subreddit_name in targets:
        clean = subreddit_name.lstrip("r/")
        try:
            subreddit = reddit.subreddit(clean)
            submission = subreddit.submit(
                title=title,
                selftext=body,
                nsfw=False,
            )
            url = f"https://reddit.com{submission.permalink}"
            urls.append(url)
            print(f"    [reddit] Posted to r/{clean} → {url}")
        except Exception as e:
            print(f"    [reddit] Failed to post to r/{clean}: {e}")

    return urls
