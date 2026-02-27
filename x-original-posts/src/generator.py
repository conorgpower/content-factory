"""
Tweet generator.

Picks a topic pillar + angle that hasn't been used recently,
builds the prompt, calls the OpenAI API, and returns the generated tweet.
"""
import json
import os
import random
from pathlib import Path

from openai import OpenAI

BASE = Path(__file__).parent.parent
PILLARS_FILE = BASE / "config" / "pillars.json"
ANGLES_FILE  = BASE / "config" / "angles.json"
PROMPT_FILE  = BASE / "prompts" / "tweet.md"
PERSONA_FILE = BASE / "persona.md"


def _load_json(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def _load_text(path: Path) -> str:
    with open(path) as f:
        return f.read().strip()


def pick_combo(recent_combos: list[tuple[str, str]]) -> tuple[dict, dict]:
    """
    Select a (pillar, angle) pair not used in the last 30 tweets.
    Falls back to avoiding the last 12 if all combos are exhausted.
    """
    pillars = _load_json(PILLARS_FILE)
    angles  = _load_json(ANGLES_FILE)

    recent_set = set(recent_combos)

    available = [
        (p, a)
        for p in pillars
        for a in angles
        if (p["id"], a["id"]) not in recent_set
    ]

    if not available:
        # All 120 combos used — only avoid the last 12
        recent_12 = set(recent_combos[:12])
        available = [
            (p, a)
            for p in pillars
            for a in angles
            if (p["id"], a["id"]) not in recent_12
        ]

    return random.choice(available)


def _build_recent_themes_text(recent_combos: list[tuple[str, str]]) -> str:
    if not recent_combos:
        return "None yet."

    pillars = {p["id"]: p["label"] for p in _load_json(PILLARS_FILE)}
    angles  = {a["id"]: a["label"] for a in _load_json(ANGLES_FILE)}

    lines = []
    for topic_id, angle_id in recent_combos[:15]:
        t = pillars.get(topic_id, topic_id)
        a = angles.get(angle_id, angle_id)
        lines.append(f"- {t} / {a}")
    return "\n".join(lines)


def generate(recent_combos: list[tuple[str, str]]) -> dict:
    """
    Generate one tweet (and optional reply).
    Returns dict with keys: topic, angle, tweet_text, reply_text (may be None).
    """
    pillar, angle = pick_combo(recent_combos)

    prompt_template = _load_text(PROMPT_FILE)
    persona         = _load_text(PERSONA_FILE)
    recent_themes   = _build_recent_themes_text(recent_combos)

    prompt = (
        prompt_template
        .replace("{{topic_label}}", pillar["label"])
        .replace("{{topic_description}}", pillar["description"])
        .replace("{{angle_label}}", angle["label"])
        .replace("{{angle_description}}", angle["description"])
        .replace("{{recent_themes}}", recent_themes)
        .replace("{{persona}}", persona)
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)

    return {
        "topic":      pillar["id"],
        "angle":      angle["id"],
        "tweet_text": data["tweet"].strip(),
        "reply_text": data.get("reply") or None,
    }
