# Podcast-to-Social

Monitors YouTube podcast playlists daily for new episodes, summarises them into
X threads and Reddit posts using OpenAI, attaches the episode thumbnail, and
schedules posts across US peak-time windows.

---

## How it works

```
6 AM ET daily cron
  └── python main.py discover
        ├── Check YouTube channels for new episodes (last 25 hours)
        ├── Pull transcript via YouTube Transcript API
        ├── Download episode thumbnail from YouTube CDN
        ├── Generate X thread + Reddit post via OpenAI API
        └── Save to database as 'pending'

You run:  python main.py review
        ├── Review each post in the terminal
        ├── Approve (a), reject (r), or skip (s)
        └── Approved posts marked ready to send

Every 15 min cron
  └── python main.py post
        ├── Find approved posts whose scheduled time has passed
        ├── Post X thread (with thumbnail attached to first tweet)
        └── Post to matching Reddit communities
```

When you're ready to go fully automated: set `AUTO_POST=true` in `.env`.
Posts will be marked approved immediately and sent at their scheduled times.

---

## Setup

### 1. Install dependencies

```bash
cd content-factory/podcast-to-social
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Add your YouTube channels

Edit [config/channels.yaml](config/channels.yaml). Each entry uses a `playlist_id`
from the podcast tab URL (`?list=XXXX`). This ensures only real episodes are picked
up — not shorts or clips. Five channels are pre-configured (Tim Ferriss, Diary of a
CEO, Huberman Lab, Lex Fridman, High Performance).

### 4. API setup checklist

| Service | Where to get credentials |
|---|---|
| **OpenAI** | platform.openai.com → API Keys |
| **YouTube** | console.cloud.google.com → Enable YouTube Data API v3 → Create API Key |
| **Twitter/X** | developer.twitter.com → Create app with Read+Write → Generate OAuth 1.0a keys |
| **Reddit** | reddit.com/prefs/apps → Create "script" app |

### 5. Test with dry run

```bash
# Generate posts without saving or posting
DRY_RUN=true python main.py discover
```

### 6. Set up cron

```bash
crontab -e
```

Add these two lines (adjust the path to your project):

```cron
# Discover new episodes at 6 AM Eastern every day
0 6 * * * cd /path/to/podcast-to-social && source venv/bin/activate && python main.py discover >> logs/discover.log 2>&1

# Check for posts to send every 15 minutes
*/15 * * * * cd /path/to/podcast-to-social && source venv/bin/activate && python main.py post >> logs/post.log 2>&1
```

Create the logs directory: `mkdir -p logs`

---

## Daily workflow (review mode)

1. Run `python main.py discover` (or let cron handle it)
2. Review posts: `python main.py review`
3. Approve the ones you want to go out — they post at scheduled times automatically
4. Check status: `python main.py status`

---

## Going fully automated

Once you're happy with post quality:

1. Open `.env`
2. Change `AUTO_POST=false` → `AUTO_POST=true`
3. Done. Posts will be approved automatically and sent at scheduled times.

You can always flip back to `false` to re-enable review mode.

---

## Scheduling logic

Posts are distributed across US peak-time windows (configurable in
[config/schedule.yaml](config/schedule.yaml)):

| Window (US Eastern) | Audience behaviour |
|---|---|
| 7:30 AM | Early risers, commuters |
| 9:00 AM | Morning desk check |
| 12:00 PM | Lunch scroll |
| 3:30 PM | Afternoon lull |
| 7:00 PM | Evening wind-down (highest engagement) |
| 8:30 PM | Late evening |

If you get 3 new episodes today, they'll be spread across 3 of those windows.
Reddit posts go out 30 minutes after the matching X post.

---

## File structure

```
podcast-to-social/
├── main.py                  # CLI: discover / post / review / status
├── review.py                # Interactive approval terminal UI
├── style-guide.md           # Writing style guide (source of truth for prompts)
├── requirements.txt
├── .env.example
├── config/
│   ├── channels.yaml        # YouTube channels to monitor
│   ├── subreddits.yaml      # Reddit communities + allow-list
│   └── schedule.yaml        # Peak time windows
├── src/
│   ├── database.py          # SQLite: episodes + posts queue
│   ├── youtube_monitor.py   # YouTube Data API v3 channel polling
│   ├── transcript_extractor.py  # youtube-transcript-api
│   ├── thumbnail_fetcher.py # YouTube CDN thumbnail download
│   ├── post_generator.py    # OpenAI: chunk summarisation + post generation
│   ├── scheduler.py         # Distribute posts across time windows
│   ├── x_poster.py          # Twitter API v2 thread posting
│   └── reddit_poster.py     # Reddit API (PRAW) posting
├── prompts/
│   ├── x_post.md            # X thread generation prompt
│   └── reddit_post.md       # Reddit post generation prompt
├── output/
│   └── thumbnails/          # Downloaded episode thumbnails
└── data/
    └── podcast_to_social.db # SQLite database (auto-created)
```

---

## Notes

- **YouTube API quota:** The free tier gives 10,000 units/day. Using `playlistItems`
  costs 1 unit per call (not `search` which costs 100). You can monitor ~100+ channels
  comfortably within the free quota.

- **Twitter API tier:** The free tier allows ~50 posts/month. The Basic tier ($100/mo)
  allows 3,000 posts/month. For running multiple channels at scale, Basic is needed.

- **Reddit:** Free. PRAW handles authentication. Posts are capped at 3 subreddits per
  episode to avoid spam flags.

- **OpenAI models:** `gpt-4o-mini` is used for chunk summarisation and post generation
  (fast + cheap). `gpt-4o` is used for the final synthesis pass that structures the
  episode insights. Both are configurable via `OPENAI_MODEL` and `OPENAI_SYNTHESIS_MODEL`
  in `.env`.
