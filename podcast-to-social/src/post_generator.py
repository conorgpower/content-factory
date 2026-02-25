"""
Post generator — rolling chunk summarisation + high-quality final synthesis.

Pipeline per episode:
  1. chunk transcript into ~40k-char segments
  2. summarise each chunk with gpt-4o-mini, carrying forward all previous summaries
     so each chunk is understood in context of what came before
  3. synthesise ALL partial summaries into one structured JSON using gpt-4o
     (higher quality model — this output drives everything downstream)
  4. generate_x_post()     — gpt-4o-mini, turns final summary into X thread
  5. generate_reddit_post() — gpt-4o-mini, turns final summary into Reddit post

Speaking pace is ~130-150 words/min (~800 chars/min including spaces):
  1 hour  ≈  48,000 chars  →  2 chunks  →  3 API calls total
  2 hours ≈  96,000 chars  →  3 chunks  →  4 API calls total
  3 hours ≈ 144,000 chars  →  4 chunks  →  5 API calls total
All cheap gpt-4o-mini calls except the one synthesis step.
"""
import os
import json
import re
from pathlib import Path

from openai import OpenAI

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ~800 chars/min of speech. A 40k chunk ≈ 50 minutes of audio.
# gpt-4o-mini's 128k context easily holds a 40k chunk plus
# accumulated previous summaries (~500 words / ~3k chars each).
CHUNK_SIZE = 40_000


# ── OpenAI helpers ─────────────────────────────────────────────────────────────

def _get_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _call(prompt: str, model: str, max_tokens: int = 2000) -> str:
    """Call OpenAI with JSON mode forced on."""
    response = _get_client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text.strip())


def _chunk_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _synthesis_model() -> str:
    return os.environ.get("OPENAI_SYNTHESIS_MODEL", "gpt-4o")


# ── Prompt templates ───────────────────────────────────────────────────────────

_SINGLE_PASS_PROMPT = """\
You are extracting structured insights from a podcast transcript.
The transcript may be raw auto-generated captions — messy, no punctuation.
Find the signal in the noise.

Podcast: {channel_name}
Episode: {episode_title}

Transcript:
{transcript}

Extract:
1. main_thesis   — the central argument or biggest idea (2-3 sentences)
2. key_insights  — 5-7 distinct, specific insights. Each must be a complete
                   standalone idea, not vague ("talks about mindset") but
                   concrete ("Epictetus said the obstacle IS the training")
3. notable_quotes — up to 3 verbatim or near-verbatim memorable lines.
                    Empty list if none clearly present.
4. practical_applications — 3-5 ways to apply these ideas in real life
                            (stress, decisions, relationships, habits)
5. episode_context — 1-2 sentences: who is speaking, what the topic is

Return ONLY valid JSON:
main_thesis, key_insights, notable_quotes, practical_applications, episode_context
"""

_CHUNK_PROMPT = """\
You are summarising section {chunk_num} of {total_chunks} of a podcast transcript.
Raw auto-generated captions — messy, no punctuation. Find the signal.

Podcast: {channel_name}
Episode: {episode_title}

{previous_context}
Now here is section {chunk_num} of {total_chunks}:
---
{chunk}
---

Extract from THIS section only (do not repeat content already covered above):
1. section_summary — 2-3 sentences on the main ideas in this section
2. key_points      — 3-5 specific, concrete ideas from this section
3. notable_quotes  — up to 2 verbatim memorable quotes. Empty list if none.

Return ONLY valid JSON: section_summary, key_points, notable_quotes
"""

_SYNTHESIS_PROMPT = """\
You are synthesising section-by-section summaries of a full podcast episode
into one final structured analysis. Do not just repeat what's below — identify
the through-line, pick the sharpest insights, organise them.

Podcast: {channel_name}
Episode: {episode_title}

{all_summaries}

Produce a final analysis:
1. main_thesis   — the central argument of the whole episode (2-3 sentences)
2. key_insights  — 5-7 of the most important specific insights from the full
                   episode. Concrete, not vague. One complete idea per item.
3. notable_quotes — up to 3 of the most memorable quotes from any section
4. practical_applications — 3-5 ways to apply these ideas in real life
5. episode_context — 1-2 sentences of background

Return ONLY valid JSON:
main_thesis, key_insights, notable_quotes, practical_applications, episode_context
"""


# ── Chunking ───────────────────────────────────────────────────────────────────

def _chunk_transcript(transcript: str) -> list[str]:
    """
    Split transcript into chunks of ~CHUNK_SIZE chars, splitting on
    a word boundary so we never cut mid-word.
    """
    if len(transcript) <= CHUNK_SIZE:
        return [transcript]

    chunks = []
    remaining = transcript

    while len(remaining) > CHUNK_SIZE:
        # Find the nearest space within ±300 chars of the target boundary
        boundary = CHUNK_SIZE
        split_at = remaining.rfind(" ", boundary - 300, boundary + 300)
        if split_at == -1:
            split_at = boundary
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


# ── Context formatting ─────────────────────────────────────────────────────────

def _format_previous_context(partial_summaries: list[dict]) -> str:
    """
    Format all previous partial summaries into readable text to inject
    into the next chunk prompt.
    """
    if not partial_summaries:
        return ""

    lines = ["SUMMARIES FROM PREVIOUS SECTIONS:"]
    for i, s in enumerate(partial_summaries, 1):
        lines.append(f"\n--- Section {i} ---")
        if s.get("section_summary"):
            lines.append(s["section_summary"])
        if s.get("key_points"):
            lines.append("Key points:")
            for kp in s["key_points"]:
                lines.append(f"  • {kp}")
        if s.get("notable_quotes"):
            for q in s["notable_quotes"]:
                lines.append(f'  "{q}"')

    lines.append("")  # blank line before the new chunk
    return "\n".join(lines)


# ── Summary → readable text (for post generation prompts) ─────────────────────

def _summary_to_text(summary: dict) -> str:
    """
    Convert the final structured summary dict into clean labelled text.
    This is what the X and Reddit post prompts receive as their input.
    """
    lines = []

    if summary.get("main_thesis"):
        lines.append(f"MAIN ARGUMENT:\n{summary['main_thesis']}\n")

    if summary.get("key_insights"):
        lines.append("KEY INSIGHTS:")
        for i, insight in enumerate(summary["key_insights"], 1):
            lines.append(f"  {i}. {insight}")
        lines.append("")

    if summary.get("notable_quotes"):
        lines.append("NOTABLE QUOTES:")
        for q in summary["notable_quotes"]:
            lines.append(f'  "{q}"')
        lines.append("")

    if summary.get("practical_applications"):
        lines.append("PRACTICAL APPLICATIONS:")
        for a in summary["practical_applications"]:
            lines.append(f"  - {a}")
        lines.append("")

    if summary.get("episode_context"):
        lines.append(f"CONTEXT:\n{summary['episode_context']}")

    return "\n".join(lines).strip()


# ── Step 1: Summarise ─────────────────────────────────────────────────────────

def summarize_episode(
    channel_name: str,
    episode_title: str,
    transcript: str,
) -> dict | None:
    """
    Summarise a full transcript into a structured insights dict.

    Short transcripts (≤ CHUNK_SIZE):
      → single pass with the synthesis model (gpt-4o)

    Long transcripts (> CHUNK_SIZE):
      → rolling chunk summaries with gpt-4o-mini
         each chunk receives all previous summaries as context
      → final synthesis pass with gpt-4o
    """
    chunks = _chunk_transcript(transcript)
    n = len(chunks)
    print(f"    [generator] Transcript: {len(transcript):,} chars → {n} chunk(s)")

    # ── Short transcript: single high-quality pass ─────────────────────────
    if n == 1:
        print(f"    [generator] Single-pass summarisation ({_synthesis_model()})...")
        prompt = _SINGLE_PASS_PROMPT.format(
            channel_name=channel_name,
            episode_title=episode_title,
            transcript=transcript,
        )
        try:
            response = _call(prompt, _synthesis_model(), max_tokens=1500)
            return _extract_json(response)
        except Exception as e:
            print(f"    [generator] Summarisation error: {e}")
            return None

    # ── Long transcript: rolling chunks ───────────────────────────────────
    partial_summaries: list[dict] = []

    for i, chunk in enumerate(chunks):
        print(f"    [generator] Chunk {i+1}/{n} ({_chunk_model()})...")
        previous_context = _format_previous_context(partial_summaries)

        prompt = _CHUNK_PROMPT.format(
            chunk_num=i + 1,
            total_chunks=n,
            channel_name=channel_name,
            episode_title=episode_title,
            previous_context=previous_context,
            chunk=chunk,
        )
        try:
            response = _call(prompt, _chunk_model(), max_tokens=1000)
            partial_summaries.append(_extract_json(response))
        except Exception as e:
            print(f"    [generator] Chunk {i+1} error: {e}")
            # Keep going — partial coverage is better than nothing

    if not partial_summaries:
        print("    [generator] All chunks failed")
        return None

    # ── Final synthesis: all partial summaries → structured output ─────────
    print(f"    [generator] Final synthesis ({_synthesis_model()})...")
    all_summaries = _format_previous_context(partial_summaries)

    prompt = _SYNTHESIS_PROMPT.format(
        channel_name=channel_name,
        episode_title=episode_title,
        all_summaries=all_summaries,
    )
    try:
        response = _call(prompt, _synthesis_model(), max_tokens=2000)
        return _extract_json(response)
    except Exception as e:
        print(f"    [generator] Synthesis error: {e}")
        return None


# ── Step 2: Generate posts ────────────────────────────────────────────────────

def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _fill(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


def generate_x_post(
    channel_name: str,
    episode_title: str,
    summary: dict,
) -> dict | None:
    """
    Generate an X thread from the final episode summary.
    Returns a dict with key 'tweets' (list of str), or None on failure.
    """
    try:
        template = _load_prompt("x_post.md")
        prompt = _fill(
            template,
            channel_name=channel_name,
            episode_title=episode_title,
            transcript=_summary_to_text(summary),
        )
        response = _call(prompt, _chunk_model(), max_tokens=1500)
        return _extract_json(response)
    except Exception as e:
        print(f"    [generator] X post error: {e}")
        return None


def generate_reddit_post(
    channel_name: str,
    episode_title: str,
    summary: dict,
    topic_tags: list[str],
) -> dict | None:
    """
    Generate a Reddit post from the final episode summary.
    Returns a dict with keys 'title', 'body', 'suggested_subreddits', or None.
    """
    try:
        template = _load_prompt("reddit_post.md")
        prompt = _fill(
            template,
            channel_name=channel_name,
            episode_title=episode_title,
            transcript=_summary_to_text(summary),
            topic_tags=", ".join(topic_tags) if topic_tags else "general",
        )
        response = _call(prompt, _chunk_model(), max_tokens=2000)
        return _extract_json(response)
    except Exception as e:
        print(f"    [generator] Reddit post error: {e}")
        return None
