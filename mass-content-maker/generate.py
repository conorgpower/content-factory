"""
Mass Content Maker — Ranked Tier Image & Video Generator
Generates social media images/videos with ranked tiers (Bronze → Iridescent)
matching the viral Runify-style format, branded for Seneca Chat.

Usage:
    python generate.py                          # Generate all images
    python generate.py --index 0                # Generate specific image(s)
    python generate.py --list                   # List all variations
    python generate.py --video                  # Generate all videos
    python generate.py --video --index 0 1 2    # Generate specific videos
"""

import json
import asyncio
import argparse
import base64
import random
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
VARIATIONS_FILE = BASE_DIR / "variations.json"
LOGO_FILE = BASE_DIR / "logo.png"
AUDIO_DIR = BASE_DIR / "audio"
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_DIR = BASE_DIR / "output" / "videos"


def get_logo_base64() -> str:
    """Read the logo file and return as a base64 data URI."""
    logo_bytes = LOGO_FILE.read_bytes()
    b64 = base64.b64encode(logo_bytes).decode()
    return f"data:image/png;base64,{b64}"


def build_html(variation: dict, hide_card: bool = False) -> str:
    """Build the HTML for a single ranked-tier image.
    If hide_card=True, the card content is invisible (for fade-in effect).
    """
    hook = variation["hook"]
    hook_sub = variation["hook_sub"]
    metric = variation["metric"]
    tiers = variation["tiers"]

    tier_colors = {
        "Bronze": {"bg": "linear-gradient(135deg, #CD7F32, #8B4513)", "shadow": "#CD7F32"},
        "Gold": {"bg": "linear-gradient(135deg, #FFD700, #B8860B)", "shadow": "#FFD700"},
        "Emerald": {"bg": "linear-gradient(135deg, #50C878, #2E8B57)", "shadow": "#50C878"},
        "Diamond": {"bg": "linear-gradient(135deg, #B9F2FF, #4169E1)", "shadow": "#4169E1"},
        "Champion": {"bg": "linear-gradient(135deg, #FF4444, #8B0000)", "shadow": "#FF4444"},
        "Iridescent": {"bg": "linear-gradient(135deg, #E0C3FC, #8EC5FC, #F5576C)", "shadow": "#E0C3FC"},
    }

    logo_uri = get_logo_base64()

    card_visibility = "visibility: hidden;" if hide_card else ""

    tier_rows = ""
    for tier_name, tier_value in tiers.items():
        colors = tier_colors[tier_name]
        tier_rows += f"""
        <div class="tier-row">
            <div class="tier-left">
                <div class="tier-icon" style="background: {colors['bg']}; box-shadow: 0 0 12px {colors['shadow']}44;"></div>
                <span class="tier-name">{tier_name}</span>
            </div>
            <span class="tier-value">{tier_value}</span>
        </div>
        <div class="tier-divider"></div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}

    body {{
        width: 1080px;
        height: 1920px;
        font-family: 'Inter', -apple-system, sans-serif;
        background: #000;
        display: flex;
        flex-direction: column;
    }}

    .top-padding {{
        height: 120px;
        background: #000;
        flex-shrink: 0;
    }}

    .hook-section {{
        background: #f5f5f5;
        padding: 60px 70px 40px;
        text-align: center;
    }}

    .hook-text {{
        font-size: 62px;
        font-weight: 800;
        color: #1a1a1a;
        line-height: 1.2;
        margin-bottom: 16px;
    }}

    .hook-sub {{
        font-size: 38px;
        font-weight: 400;
        color: #555;
        line-height: 1.3;
    }}

    .card-section {{
        flex: 1;
        background: #0a0a0a;
        border-radius: 30px 30px 0 0;
        padding: 50px 70px 40px;
        display: flex;
        flex-direction: column;
    }}

    .card-content {{
        display: flex;
        flex-direction: column;
        flex: 1;
        {card_visibility}
    }}

    .app-brand {{
        text-align: center;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
    }}

    .app-logo {{
        width: 96px;
        height: 96px;
        object-fit: contain;
        border-radius: 16px;
    }}

    .app-name {{
        font-size: 64px;
        font-weight: 600;
        color: #ccc;
        letter-spacing: 0.5px;
    }}

    .metric-name {{
        text-align: center;
        font-size: 72px;
        font-weight: 900;
        background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 30px;
        margin-top: 10px;
    }}

    .tiers-container {{
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
    }}

    .tier-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 0;
    }}

    .tier-left {{
        display: flex;
        align-items: center;
        gap: 28px;
    }}

    .tier-icon {{
        width: 84px;
        height: 84px;
        border-radius: 50%;
        flex-shrink: 0;
    }}

    .tier-name {{
        font-size: 52px;
        font-weight: 700;
        color: #fff;
    }}

    .tier-value {{
        font-size: 52px;
        font-weight: 700;
        color: #fff;
    }}

    .tier-divider {{
        height: 1px;
        background: #333;
        margin: 2px 0;
    }}

    .bottom-padding {{
        height: 160px;
        background: #0a0a0a;
        flex-shrink: 0;
    }}
</style>
</head>
<body>
    <div class="top-padding"></div>
    <div class="hook-section">
        <div class="hook-text">{hook}</div>
        <div class="hook-sub">{hook_sub}</div>
    </div>
    <div class="card-section">
        <div class="card-content">
            <div class="app-brand">
                <img class="app-logo" src="{logo_uri}" alt="Seneca Chat">
                <span class="app-name">Seneca Chat</span>
            </div>
            <div class="metric-name">{metric}</div>
            <div class="tiers-container">
                {tier_rows}
            </div>
        </div>
    </div>
    <div class="bottom-padding"></div>
</body>
</html>"""


async def generate_images(indices: list[int] | None = None):
    """Generate images for specified variations (or all if None)."""
    with open(VARIATIONS_FILE) as f:
        variations = json.load(f)

    OUTPUT_DIR.mkdir(exist_ok=True)

    if indices is None:
        indices = list(range(len(variations)))

    print(f"Generating {len(indices)} image(s)...")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})

        for i in indices:
            variation = variations[i]
            html = build_html(variation)

            await page.set_content(html, wait_until="networkidle")
            # Wait for fonts to load
            await page.wait_for_timeout(1000)

            slug = variation["metric"].lower().replace(" ", "-").replace("/", "-")
            filename = f"{i:02d}-{slug}.png"
            filepath = OUTPUT_DIR / filename

            await page.screenshot(path=str(filepath), type="png")
            print(f"  ✓ {filename}")

        await browser.close()

    print(f"\nDone! Images saved to {OUTPUT_DIR}/")


def get_random_audio() -> Path | None:
    """Pick a random audio file from the audio directory."""
    if not AUDIO_DIR.exists():
        return None
    audio_files = list(AUDIO_DIR.glob("*.[mM][pP]3")) + list(AUDIO_DIR.glob("*.[wW][aA][vV]")) + list(AUDIO_DIR.glob("*.[mM]4[aA]")) + list(AUDIO_DIR.glob("*.[mM][pP]4"))
    if not audio_files:
        return None
    return random.choice(audio_files)


async def generate_videos(indices: list[int] | None = None):
    """Generate videos with fade-in effect and random audio."""
    with open(VARIATIONS_FILE) as f:
        variations = json.load(f)

    OUTPUT_DIR.mkdir(exist_ok=True)
    VIDEO_DIR.mkdir(exist_ok=True)

    if indices is None:
        indices = list(range(len(variations)))

    # Check for audio files
    audio_files = []
    if AUDIO_DIR.exists():
        audio_files = list(AUDIO_DIR.glob("*.[mM][pP]3")) + list(AUDIO_DIR.glob("*.[wW][aA][vV]")) + list(AUDIO_DIR.glob("*.[mM]4[aA]")) + list(AUDIO_DIR.glob("*.[mM][pP]4"))
    if not audio_files:
        print(f"⚠ No audio files found in {AUDIO_DIR}/")
        print("  Add .mp3, .wav, or .m4a files there, then re-run.")
        return

    print(f"Found {len(audio_files)} audio file(s)")
    print(f"Generating {len(indices)} video(s)...\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})

        for i in indices:
            variation = variations[i]
            slug = variation["metric"].lower().replace(" ", "-").replace("/", "-")

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)

                # Generate "before" frame (card content hidden)
                html_before = build_html(variation, hide_card=True)
                await page.set_content(html_before, wait_until="networkidle")
                await page.wait_for_timeout(500)
                before_path = tmpdir / "before.png"
                await page.screenshot(path=str(before_path), type="png")

                # Generate "after" frame (full content)
                html_after = build_html(variation, hide_card=False)
                await page.set_content(html_after, wait_until="networkidle")
                await page.wait_for_timeout(500)
                after_path = tmpdir / "after.png"
                await page.screenshot(path=str(after_path), type="png")

                # Pick random audio and get its duration
                audio_file = random.choice(audio_files)
                duration_result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(audio_file)],
                    capture_output=True, text=True,
                )
                audio_duration = float(duration_result.stdout.strip())

                video_filename = f"{i:02d}-{slug}.mp4"
                video_path = VIDEO_DIR / video_filename

                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    # Input 1: "before" image as 0.5s video
                    "-loop", "1", "-t", "1.0", "-i", str(before_path),
                    # Input 2: "after" image for full audio duration
                    "-loop", "1", "-t", str(audio_duration), "-i", str(after_path),
                    # Input 3: audio
                    "-i", str(audio_file),
                    # Filter: crossfade before→after over 0.5s, audio fade-in/out
                    "-filter_complex",
                    f"[0:v][1:v]xfade=transition=fade:duration=1.0:offset=0,format=yuv420p[v];"
                    f"[2:a]anull[a]",
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k",
                    "-t", str(audio_duration),
                    str(video_path),
                ]

                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  ✗ {video_filename} — ffmpeg error:")
                    print(f"    {result.stderr[-300:]}")
                else:
                    print(f"  ✓ {video_filename}  ({audio_duration:.1f}s, audio: {audio_file.name})")

        await browser.close()

    print(f"\nDone! Videos saved to {VIDEO_DIR}/")


def list_variations():
    with open(VARIATIONS_FILE) as f:
        variations = json.load(f)
    print(f"Found {len(variations)} variations:\n")
    for i, v in enumerate(variations):
        print(f"  [{i:2d}] {v['metric']}")
        print(f"       Hook: {v['hook']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Generate ranked-tier social media images & videos")
    parser.add_argument("--index", "-i", type=int, nargs="+", help="Generate specific variation(s) by index")
    parser.add_argument("--list", "-l", action="store_true", help="List all variations")
    parser.add_argument("--video", "-v", action="store_true", help="Generate videos instead of images")
    args = parser.parse_args()

    if args.list:
        list_variations()
        return

    if args.video:
        asyncio.run(generate_videos(args.index))
    else:
        asyncio.run(generate_images(args.index))


if __name__ == "__main__":
    main()
