#!/usr/bin/env python3
"""Render the animated SVG cards used by the SourasishG profile README."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CARD_DIR = ROOT / "cards"
DATA_FILE = ROOT / "contributions.json"
USERNAME = "SourasishG"
DISPLAY_NAME = "Sourasish Ghosh"
BIO = "Full-stack developer building useful interfaces, immersive 3D, and applied AI."
GREEN = "#22C55E"
DEEP_GREEN = "#167C3B"
INK = "#17231B"
MUTED = "#617167"
PAPER = "#F6FAF6"
LINE = "#DCE8DE"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/Manrope%5Bwght%5D.ttf"

TILES = [
    ("FULL-STACK", "Useful systems", "Web apps, APIs, and thoughtful UI."),
    ("INTERACTIVE 3D", "Worlds in the browser", "Exploring space, motion, and detail."),
    ("APPLIED AI", "Tools with a purpose", "Practical automation and computer vision."),
]

REPOSITORIES = [
    (
        "Web-Based-Office-Automation-Platform-With-AI-Chatbot",
        "Office Automation + AI",
        "Office workflows with an integrated AI assistant.",
        "JavaScript",
        GREEN,
    ),
    (
        "Pokemon-Atlas-3D",
        "Pokémon Atlas 3D",
        "An interactive 3D atlas built for the browser.",
        "WebGL",
        "#70B77E",
    ),
    (
        "support-ticket-dashboard",
        "Support Ticket Dashboard",
        "A focused dashboard for AI-triaged support queues.",
        "JavaScript",
        "#5EAD83",
    ),
    (
        "Face-Recognition-System",
        "Real-Time Face Recognition",
        "A real-time face recognition system.",
        "Python",
        "#329A67",
    ),
    (
        "Gradient-Descent-Visualizer",
        "Gradient Descent Visualizer",
        "Visualizing optimization, one step at a time.",
        "JavaScript",
        "#8CCB91",
    ),
    (
        "orbital-music-app",
        "Orbital Music Player",
        "A music experience with an orbital point of view.",
        "JavaScript",
        "#3B8E5B",
    ),
]


class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        day = values.get("data-date", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return

        count = values.get("data-count", "")
        if count.isdigit():
            amount = int(count)
        else:
            label = unescape(values.get("aria-label", "") or values.get("title", ""))
            match = re.search(r"\b(\d+)\s+contributions?\b", label, re.IGNORECASE)
            amount = int(match.group(1)) if match else 0
        self.days[day] = max(self.days.get(day, 0), amount)


def refresh_contributions() -> None:
    end = date.today()
    start = end - timedelta(days=364)
    query = urlencode({"from": start.isoformat(), "to": end.isoformat()})
    request = Request(
        f"https://github.com/users/{USERNAME}/contributions?{query}",
        headers={"User-Agent": "profile-card-renderer/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(page)
    if not parser.days:
        raise RuntimeError("GitHub returned no dated contribution cells; existing data was kept.")

    daily = []
    current = start
    while current <= end:
        key = current.isoformat()
        daily.append({"date": key, "count": parser.days.get(key, 0)})
        current += timedelta(days=1)

    payload = {
        "username": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "daily": daily,
    }
    DATA_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Refreshed {len(daily)} contribution days from GitHub.")


def load_daily_data() -> dict[str, int]:
    if not DATA_FILE.exists():
        return {}
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for entry in payload.get("daily", []):
        try:
            result[str(entry["date"])] = max(0, int(entry["count"]))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def font_data_uri(text: str) -> str:
    subsetter = shutil.which("pyftsubset")
    if not subsetter:
        raise RuntimeError('Install the font subsetter with: python -m pip install "fonttools[woff]"')

    request = Request(FONT_URL, headers={"User-Agent": "profile-card-renderer/1.0"})
    with urlopen(request, timeout=30) as response:
        font = response.read()

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "manrope.ttf"
        output = Path(temp_dir) / "manrope-subset.woff2"
        source.write_bytes(font)
        subprocess.run(
            [
                subsetter,
                str(source),
                f"--text={text}",
                "--flavor=woff2",
                f"--output-file={output}",
                "--layout-features=*",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        encoded = base64.b64encode(output.read_bytes()).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


def svg_document(width: int, height: int, body: str, font_uri: str, delay: float, static: bool) -> str:
    animation_css = "" if static else f"""
      .reveal {{ animation: reveal .72s cubic-bezier(.2,.7,.2,1) {delay:.2f}s both; }}
      .bar {{ transform-box: fill-box; transform-origin: center bottom; animation: grow .8s cubic-bezier(.2,.7,.2,1) {delay + 0.35:.2f}s both; }}
      @keyframes reveal {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      @keyframes grow {{ from {{ transform: scaleY(.04); }} to {{ transform: scaleY(1); }} }}
    """
    reduced_motion = """@media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
      .reveal { opacity: 1 !important; transform: none !important; }
      .bar { transform: none !important; }
      animate, animateTransform, animateMotion { display: none !important; }
    }"""
    css = f"""@font-face {{ font-family: Manrope; src: url('{font_uri}') format('woff2'); font-style: normal; font-weight: 100 900; }}
      text {{ font-family: Manrope, 'Segoe UI', sans-serif; }}
      {animation_css}
      {reduced_motion}
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">'
        f"<style>{css}</style>"
        f'<rect class="surface" x="1" y="1" width="{width - 2}" height="{height - 2}" rx="8" fill="{PAPER}" stroke="{LINE}" stroke-width="2"/>'
        f'<g class="reveal">{body}</g></svg>\n'
    )


def text(x: int | float, y: int | float, value: str, size: int, color: str = INK, weight: int = 500) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}">{escape(value)}</text>'
    )


def card_animations(delay: float, static: bool, x: int = 1135, y: int = 38) -> str:
    if static:
        return ""
    return (
        f'<circle cx="{x}" cy="{y}" r="4" fill="{GREEN}">'
        f'<animate attributeName="opacity" values=".45;1;.45" dur="2.8s" '
        f'begin="{delay + 0.7:.2f}s" repeatCount="indefinite"/></circle>'
    )


def make_hero(font_uri: str, static: bool, portrait_url: str) -> str:
    body = [
        text(56, 70, "FULL-STACK DEVELOPER  /  KOLKATA, INDIA", 15, DEEP_GREEN, 700),
        text(52, 144, DISPLAY_NAME, 58, INK, 800),
        text(56, 193, BIO, 23, MUTED, 500),
        '<rect x="56" y="218" width="98" height="5" rx="2" fill="' + GREEN + '"/>',
    ]
    if portrait_url:
        image_href = escape(portrait_url, quote=True)
        body.extend(
            [
                '<defs><clipPath id="portrait"><circle cx="1070" cy="130" r="78"/></clipPath></defs>',
                f'<image x="992" y="52" width="156" height="156" href="{image_href}" xlink:href="{image_href}" preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait)"/>',
                '<circle cx="1070" cy="130" r="79" fill="none" stroke="' + GREEN + '" stroke-width="3"/>',
            ]
        )
    else:
        body.extend(
            [
                f'<circle cx="1074" cy="130" r="76" fill="#E7F3E8"/>',
                f'<path d="M1020 152c18-42 91-42 108 0" fill="none" stroke="{GREEN}" stroke-width="8" stroke-linecap="round"/>',
                f'<circle cx="1074" cy="104" r="23" fill="{DEEP_GREEN}"/>',
            ]
        )
    return svg_document(1200, 260, "".join(body) + card_animations(0, static), font_uri, 0, static)


def make_tile(index: int, font_uri: str, delay: float, static: bool) -> str:
    eyebrow, headline, caption = TILES[index]
    body = "".join(
        [
            f'<rect x="25" y="24" width="38" height="38" rx="8" fill="#E4F2E6"/>',
            text(44, 49, f"0{index + 1}", 13, DEEP_GREEN, 800).replace('x="44"', 'x="35"'),
            text(26, 83, eyebrow, 11, DEEP_GREEN, 800),
            text(26, 108, headline, 19, INK, 750),
            text(26, 128, caption, 10, MUTED, 500),
            f'<path d="M352 42h12m-5-5 5 5-5 5" fill="none" stroke="{DEEP_GREEN}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    )
    return svg_document(390, 150, body + card_animations(delay, static, 365, 31), font_uri, delay, static)


def month_keys(today: date) -> list[tuple[int, int]]:
    keys = []
    year, month = today.year, today.month
    for _ in range(12):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return list(reversed(keys))


def contribution_stats(daily: dict[str, int], today: date) -> tuple[int, int, str, int]:
    parsed = {date.fromisoformat(day): count for day, count in daily.items()}
    active_days = sum(count > 0 for count in parsed.values())
    busiest_day, busiest_count = max(parsed.items(), key=lambda item: (item[1], item[0]), default=(today, 0))
    streak_end = today if parsed.get(today, 0) else today - timedelta(days=1)
    streak = 0
    while parsed.get(streak_end, 0) > 0:
        streak += 1
        streak_end -= timedelta(days=1)
    return streak, active_days, busiest_day.strftime("%b %d"), busiest_count


def make_month_chart(font_uri: str, delay: float, static: bool, daily: dict[str, int]) -> str:
    today = date.today()
    totals: dict[str, int] = defaultdict(int)
    for day, count in daily.items():
        totals[day[:7]] += count
    months = month_keys(today)
    values = [totals[f"{year:04d}-{month:02d}"] for year, month in months]
    maximum = max(values, default=0) or 1
    body = [
        text(48, 48, "CONTRIBUTION PACE", 14, DEEP_GREEN, 800),
        text(48, 78, "A year of showing up", 25, INK, 750),
        f'<line x1="64" y1="260" x2="866" y2="260" stroke="{LINE}" stroke-width="2"/>',
    ]
    for index, ((year, month), value) in enumerate(zip(months, values)):
        height = 8 + int(104 * value / maximum) if value else 3
        x = 70 + index * 65
        y = 260 - height
        color = GREEN if index == 11 else "#9FCFAA"
        body.append(f'<rect class="bar" x="{x}" y="{y}" width="34" height="{height}" rx="4" fill="{color}"/>')
        body.append(text(x - 5, 283, date(year, month, 1).strftime("%b"), 11, MUTED, 600))

    streak, active, busiest_day, busiest_count = contribution_stats(daily, today)
    body.extend(
        [
            f'<line x1="903" y1="82" x2="903" y2="274" stroke="{LINE}" stroke-width="2"/>',
            text(938, 105, "CURRENT STREAK", 11, MUTED, 800),
            text(938, 143, f"{streak} days", 29, INK, 800),
            text(938, 184, "ACTIVE DAYS", 11, MUTED, 800),
            text(938, 216, str(active), 24, INK, 750),
            text(1050, 184, "BUSIEST DAY", 11, MUTED, 800),
            text(1050, 216, busiest_day, 16, INK, 750),
            text(1050, 238, f"{busiest_count} contributions", 10, MUTED, 600),
            text(48, 309, "Monthly contributions", 11, MUTED, 500),
        ]
    )
    if not daily:
        body.append(text(530, 192, "Data will appear after the first scheduled refresh.", 13, MUTED, 600))
    return svg_document(1200, 330, "".join(body) + card_animations(delay, static), font_uri, delay, static)


def make_repository(index: int, repo: tuple[str, str, str, str, str], font_uri: str, delay: float, static: bool) -> str:
    slug, title, description, language, accent = repo
    body = "".join(
        [
            f'<rect x="42" y="42" width="8" height="62" rx="4" fill="{accent}"/>',
            text(76, 57, f"FEATURED REPOSITORY  /  0{index + 1}", 11, DEEP_GREEN, 800),
            text(76, 91, title, 24, INK, 750),
            text(76, 119, description, 14, MUTED, 500),
            f'<rect x="1005" y="54" width="142" height="34" rx="17" fill="#E6F3E8"/>',
            text(1024, 76, language, 12, DEEP_GREEN, 700),
            f'<path d="M1149 111h18m-6-6 6 6-6 6" fill="none" stroke="{DEEP_GREEN}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<title>{escape(slug)}</title>',
        ]
    )
    return svg_document(1200, 150, body + card_animations(delay, static), font_uri, delay, static)


def make_contribution_graph(font_uri: str, delay: float, static: bool, daily: dict[str, int]) -> str:
    today = date.today()
    start = today - timedelta(days=364)
    grid_start = start - timedelta(days=(start.weekday() + 1) % 7)
    values = {date.fromisoformat(day): count for day, count in daily.items()}
    colors = ["#E8F0E9", "#B9E4C2", "#7CCB8D", "#43AF62", DEEP_GREEN]
    body = [
        text(48, 48, "CONTRIBUTION GRAPH", 14, DEEP_GREEN, 800),
        text(48, 77, "Small steps, over time", 24, INK, 750),
        text(1053, 74, f"{sum(daily.values())} contributions", 12, MUTED, 700),
    ]
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(text(56, 106 + row * 15, label, 9, MUTED, 600))

    month_labels: set[tuple[int, int]] = set()
    for column in range(53):
        for row in range(7):
            current = grid_start + timedelta(days=column * 7 + row)
            if current > today:
                continue
            count = values.get(current, 0)
            level = 0 if count == 0 else min(4, 1 + (count > 1) + (count > 3) + (count > 6))
            x, y = 105 + column * 14, 91 + row * 15
            body.append(f'<rect x="{x}" y="{y}" width="10" height="10" rx="2" fill="{colors[level]}"/>')
            if current.day == 1:
                month_key = (current.year, current.month)
                if month_key not in month_labels:
                    body.append(text(x - 1, 84, current.strftime("%b"), 9, MUTED, 600))
                    month_labels.add(month_key)

    body.extend(
        [
            text(105, 207, "LESS", 9, MUTED, 600),
            *[
                f'<rect x="{1170 + index * 6}" y="198" width="8" height="8" rx="2" fill="{color}"/>'
                for index, color in enumerate(colors)
            ],
            text(1210, 207, "MORE", 9, MUTED, 600),
        ]
    )
    return svg_document(1280, 225, "".join(body) + card_animations(delay, static, 1235, 38), font_uri, delay, static)


def render_cards(static: bool) -> None:
    daily = load_daily_data()
    all_text = [DISPLAY_NAME, BIO, " ".join(part for tile in TILES for part in tile)]
    all_text.extend(" ".join(repo[:4]) for repo in REPOSITORIES)
    all_text.extend("CONTRIBUTION PACE CONTRIBUTION GRAPH CURRENT STREAK ACTIVE DAYS BUSIEST DAY Monthly contributions Small steps over time LESS MORE".split())
    glyphs = "".join(chr(codepoint) for codepoint in range(32, 127)) + "".join(all_text)
    font_uri = font_data_uri(glyphs)
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    portrait_url = os.environ.get("PROFILE_PORTRAIT_URL", "").strip()

    cards: dict[str, str] = {
        "hero.svg": make_hero(font_uri, static, portrait_url),
        "contributions-month.svg": make_month_chart(font_uri, 1.25, static, daily),
        "contribution-graph.svg": make_contribution_graph(font_uri, 4.20, static, daily),
    }
    for index in range(len(TILES)):
        cards[f"tile-{('fullstack', '3d', 'ai')[index]}.svg"] = make_tile(index, font_uri, 0.55 + index * 0.12, static)
    for index, repo in enumerate(REPOSITORIES):
        cards[f"repo-{('office-aid', 'pokemon-3d', 'support-ticket', 'face-recog', 'gradient-descent', 'orbital-music')[index]}.svg"] = make_repository(
            index, repo, font_uri, 2.05 + index * 0.28, static
        )

    for filename, contents in cards.items():
        (CARD_DIR / filename).write_text(contents, encoding="utf-8")
    mode = "static" if static else "animated"
    print(f"Rendered {len(cards)} {mode} SVG cards to {CARD_DIR.relative_to(ROOT)}/.")


def main() -> None:
    if "--refresh-data" in sys.argv[1:]:
        refresh_contributions()
        return
    render_cards(static=os.environ.get("STATIC") == "1")


if __name__ == "__main__":
    main()