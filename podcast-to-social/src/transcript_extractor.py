"""
YouTube transcript extractor.
Uses youtube-transcript-api (no API key required, no quota cost).
Priority: manual English → auto-generated English → first available (translated).

No length limit is applied here. The post_generator chunker handles splitting —
at ~800 chars/minute of speech:
  1 hour  ≈  48,000 chars  →  2 chunks
  2 hours ≈  96,000 chars  →  3 chunks
  3 hours ≈ 144,000 chars  →  4 chunks
"""
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)


def get_transcript(video_id: str) -> str | None:
    """
    Fetch and return the full transcript text for a YouTube video.
    Returns None if no transcript is available.
    """
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        print(f"    [transcript] Transcripts disabled for {video_id}")
        return None
    except Exception as e:
        print(f"    [transcript] Error listing transcripts for {video_id}: {e}")
        return None

    transcript = None

    # 1. Try manually-created English transcript
    try:
        transcript = transcript_list.find_manually_created_transcript(
            ["en", "en-US", "en-GB"]
        )
    except NoTranscriptFound:
        pass

    # 2. Fall back to auto-generated English
    if transcript is None:
        try:
            transcript = transcript_list.find_generated_transcript(
                ["en", "en-US", "en-GB"]
            )
        except NoTranscriptFound:
            pass

    # 3. Fall back to any available language and translate to English
    if transcript is None:
        try:
            available = list(transcript_list)
            if available and available[0].is_translatable:
                transcript = available[0].translate("en")
        except Exception:
            pass

    if transcript is None:
        print(f"    [transcript] No usable transcript found for {video_id}")
        return None

    try:
        fetched = transcript.fetch()
        full_text = " ".join(snippet.text for snippet in fetched).strip()
        print(f"    [transcript] {len(full_text):,} chars fetched")
        return full_text

    except Exception as e:
        print(f"    [transcript] Fetch error for {video_id}: {e}")
        return None
