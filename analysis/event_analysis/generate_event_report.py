"""
Automated Event Report Generator.

Scans debug/events and debug/rejected_events for event_plot.html files,
captures high-resolution screenshots via Playwright (headless Chromium),
reads event metadata, and produces:

    reports/event_images/         — PNG screenshots of every event plot
    reports/accepted_events.pdf   — 2x2 grid PDF of accepted events
    reports/rejected_events.pdf   — 2x2 grid PDF of rejected events
    reports/all_events.pdf        — 2x2 grid PDF of all events
    reports/index.html            — Responsive card gallery with thumbnails

This script is purely a reporting utility. It does NOT modify event detection
or validation logic.

Run from the project root:

    python analysis/event_analysis/generate_event_report.py

Requirements:
    pip install playwright fpdf2 tqdm Pillow
    python -m playwright install chromium
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fpdf import FPDF
from PIL import Image
from playwright.sync_api import sync_playwright
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACCEPTED_DIR = Path("debug/events")
REJECTED_DIR = Path("debug/rejected_events")
REPORTS_DIR = Path("reports")
IMAGES_DIR = REPORTS_DIR / "event_images"

VIEWPORT_WIDTH = 1400
VIEWPORT_HEIGHT = 700
RENDER_WAIT_MS = 300
SCREENSHOT_SCALE = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EventInfo:
    event_id: int
    label: str  # "accepted" or "rejected"
    event_dir: Path
    plot_path: Path
    image_path: Optional[Path] = None
    duration_ms: Optional[int] = None
    movement_duration_ms: Optional[int] = None
    movement_energy: Optional[float] = None
    rolling_std_peak: Optional[float] = None
    rolling_std_duration: Optional[int] = None
    angle_change_deg: Optional[float] = None
    sample_count: Optional[int] = None
    status: str = "UNKNOWN"
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# Step 1: Discovery
# ---------------------------------------------------------------------------

def discover_events(accepted_dir: Path, rejected_dir: Path) -> List[EventInfo]:
    """Find all event_plot.html files and build EventInfo records."""
    events: List[EventInfo] = []

    for directory, label in [(accepted_dir, "accepted"), (rejected_dir, "rejected")]:
        if not directory.exists():
            log.warning("Directory not found: %s", directory)
            continue
        for plot_path in sorted(directory.glob("event_*/event_plot.html")):
            event_dir = plot_path.parent
            event_id = _parse_event_id(event_dir.name)
            if event_id is None:
                continue
            events.append(EventInfo(
                event_id=event_id,
                label=label,
                event_dir=event_dir,
                plot_path=plot_path,
            ))

    events.sort(key=lambda e: e.event_id)
    return events


def _parse_event_id(dirname: str) -> Optional[int]:
    match = re.match(r"event_(\d+)", dirname)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Step 2: Screenshot capture
# ---------------------------------------------------------------------------

def capture_screenshots(events: List[EventInfo], output_dir: Path) -> None:
    """Launch headless Chromium and screenshot each event plot."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        for event in tqdm(events, desc="Capturing screenshots", unit="event"):
            image_path = output_dir / f"event_{event.event_id:04d}.png"
            try:
                file_url = event.plot_path.resolve().as_uri()
                page.goto(file_url)
                page.wait_for_function("() => document.querySelector('.js-plotly-plot')")
                page.wait_for_timeout(RENDER_WAIT_MS)

                plot_element = page.query_selector(".js-plotly-plot")
                if plot_element:
                    plot_element.screenshot(path=str(image_path), scale="device")
                else:
                    page.screenshot(path=str(image_path))

                event.image_path = image_path
            except Exception as exc:
                log.warning("Failed to capture event %d: %s", event.event_id, exc)

        browser.close()


# ---------------------------------------------------------------------------
# Step 3: Metadata loading
# ---------------------------------------------------------------------------

def load_metadata(events: List[EventInfo]) -> None:
    """Read event_summary.json for each event and populate fields."""
    for event in events:
        summary_path = event.event_dir / "event_summary.json"
        if not summary_path.exists():
            continue

        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Cannot read summary for event %d: %s", event.event_id, exc)
            continue

        general = data.get("general", {})
        movement = data.get("movement", {})
        stats = data.get("statistical_features", {})
        validation = data.get("validation", {})
        rolling_std = validation.get("rolling_std_metrics", {})
        legacy = validation.get("legacy_orientation_metrics", {})

        event.duration_ms = general.get("duration_ms")
        event.sample_count = general.get("total_samples")
        event.movement_duration_ms = movement.get("movement_duration_ms")
        event.movement_energy = stats.get("movement_energy")
        event.rolling_std_peak = rolling_std.get("rolling_std_peak")
        event.rolling_std_duration = rolling_std.get("rolling_std_duration_above_threshold")
        event.angle_change_deg = legacy.get("angle_change_deg")
        event.status = validation.get("status", "UNKNOWN")
        event.rejection_reason = validation.get("reason", "")


# ---------------------------------------------------------------------------
# Step 4 & 5: PDF generation
# ---------------------------------------------------------------------------

class EventPDF(FPDF):
    """PDF with 2x2 grid layout for event tiles."""

    def __init__(self) -> None:
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)

    def build(self, events: List[EventInfo], title: str) -> None:
        """Populate the PDF with event tiles in a 2x2 grid."""
        if not events:
            self.add_page()
            self.set_font("Helvetica", "B", 16)
            self.cell(0, 20, f"{title} - No events", align="C")
            return

        tiles_per_page = 4
        page_w = 297  # A4 landscape width mm
        page_h = 210  # A4 landscape height mm
        margin = 6
        gap = 4
        tile_w = (page_w - 2 * margin - gap) / 2
        tile_h = (page_h - 2 * margin - gap) / 2

        positions = [
            (margin, margin),
            (margin + tile_w + gap, margin),
            (margin, margin + tile_h + gap),
            (margin + tile_w + gap, margin + tile_h + gap),
        ]

        for idx, event in enumerate(events):
            if idx % tiles_per_page == 0:
                self.add_page()

            pos_idx = idx % tiles_per_page
            x, y = positions[pos_idx]
            self._draw_tile(event, x, y, tile_w, tile_h)

    def _draw_tile(self, event: EventInfo, x: float, y: float, w: float, h: float) -> None:
        self.set_draw_color(200, 200, 200)
        self.rect(x, y, w, h)

        # Header
        self.set_xy(x + 2, y + 1)
        self.set_font("Helvetica", "B", 9)
        status_icon = "[OK]" if event.label == "accepted" else "[X]"
        status_word = "VALID" if event.label == "accepted" else "REJECTED"
        header = f"Event {event.event_id}  {status_icon} {status_word}"
        self.cell(w - 4, 5, header, new_x="LMARGIN", new_y="NEXT")

        # Metrics
        self.set_xy(x + 2, y + 7)
        self.set_font("Helvetica", "", 7)
        metrics = (
            f"Duration: {_fmt_int(event.duration_ms)} ms  |  "
            f"Mvmt: {_fmt_int(event.movement_duration_ms)} ms  |  "
            f"Energy: {_fmt_float(event.movement_energy)}  |  "
            f"Angle: {_fmt_float(event.angle_change_deg)} deg  |  "
            f"STD Peak: {_fmt_float(event.rolling_std_peak)}  |  "
            f"STD Dur: {_fmt_int(event.rolling_std_duration)}  |  "
            f"Samples: {_fmt_int(event.sample_count)}"
        )
        self.cell(w - 4, 4, metrics, new_x="LMARGIN", new_y="NEXT")

        # Graph image
        img_y = y + 13
        img_h = h - 15
        img_w = w - 4
        if event.image_path and event.image_path.exists():
            try:
                self.image(str(event.image_path), x + 2, img_y, img_w, img_h)
            except Exception:
                self._draw_placeholder(x + 2, img_y, img_w, img_h)
        else:
            self._draw_placeholder(x + 2, img_y, img_w, img_h)

    def _draw_placeholder(self, x: float, y: float, w: float, h: float) -> None:
        self.set_fill_color(245, 245, 245)
        self.rect(x, y, w, h, style="F")
        self.set_xy(x, y + h / 2 - 3)
        self.set_font("Helvetica", "I", 8)
        self.cell(w, 6, "Plot not available", align="C")


def generate_pdfs(events: List[EventInfo], output_dir: Path) -> dict:
    """Generate accepted, rejected, and all-events PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    accepted = [e for e in events if e.label == "accepted"]
    rejected = [e for e in events if e.label == "rejected"]

    for subset, name, title in [
        (accepted, "accepted_events.pdf", "Accepted Events"),
        (rejected, "rejected_events.pdf", "Rejected Events"),
        (events, "all_events.pdf", "All Events"),
    ]:
        pdf = EventPDF()
        pdf.build(subset, title)
        path = output_dir / name
        pdf.output(str(path))
        paths[name] = path
        log.info("PDF: %s (%d events)", path, len(subset))

    return paths


# ---------------------------------------------------------------------------
# Step 6: Index HTML
# ---------------------------------------------------------------------------

def generate_index_html(events: List[EventInfo], output_dir: Path) -> Path:
    """Generate a responsive card gallery HTML."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"

    cards_html = "\n".join(_build_card_html(e) for e in events)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Event Report Index</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    padding: 24px;
    color: #2c3e50;
}}
h1 {{ margin-bottom: 16px; font-size: 22px; }}
.summary {{ margin-bottom: 20px; font-size: 14px; color: #555; }}
.filters {{
    margin-bottom: 16px;
    display: flex;
    gap: 16px;
}}
.filters label {{ font-size: 13px; cursor: pointer; }}
.filters input {{ margin-right: 4px; }}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}}
.card {{
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    transition: box-shadow 0.2s;
    cursor: pointer;
    text-decoration: none;
    color: inherit;
    border-left: 4px solid #bdc3c7;
}}
.card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
.card.accepted {{ border-left-color: #2ecc71; }}
.card.rejected {{ border-left-color: #e74c3c; }}
.card.hidden {{ display: none; }}
.card-thumb {{
    width: 100%;
    height: 180px;
    object-fit: cover;
    background: #f8f9fa;
}}
.card-body {{ padding: 12px 14px; }}
.card-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}}
.card-title {{ font-weight: 600; font-size: 13px; }}
.badge {{
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    font-weight: 600;
}}
.badge.accepted {{ background: #d4efdf; color: #1e8449; }}
.badge.rejected {{ background: #fadbd8; color: #922b21; }}
.card-metrics {{
    font-size: 11px;
    color: #666;
    line-height: 1.6;
}}
</style>
</head>
<body>
<h1>Event Report Index</h1>
<div class="summary">
    Accepted: {sum(1 for e in events if e.label == 'accepted')} |
    Rejected: {sum(1 for e in events if e.label == 'rejected')} |
    Total: {len(events)}
</div>
<div class="filters">
    <label><input type="checkbox" checked onchange="filter()"> Accepted</label>
    <label><input type="checkbox" checked onchange="filter()"> Rejected</label>
</div>
<div class="grid" id="grid">
{cards_html}
</div>
<script>
function filter() {{
    const checks = document.querySelectorAll('.filters input');
    const showAccepted = checks[0].checked;
    const showRejected = checks[1].checked;
    document.querySelectorAll('.card').forEach(c => {{
        const label = c.dataset.label;
        c.classList.toggle('hidden',
            (label === 'accepted' && !showAccepted) ||
            (label === 'rejected' && !showRejected));
    }});
}}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


def _build_card_html(event: EventInfo) -> str:
    status_word = "VALID" if event.label == "accepted" else "REJECTED"
    badge_class = event.label

    img_tag = ""
    if event.image_path and event.image_path.exists():
        rel_path = event.image_path.relative_to(REPORTS_DIR).as_posix()
        img_tag = f'<img class="card-thumb" src="{rel_path}" alt="Event {event.event_id}">'
    else:
        img_tag = '<div class="card-thumb" style="display:flex;align-items:center;justify-content:center;color:#aaa;">No image</div>'

    plot_link = event.plot_path.resolve().as_posix()

    return f"""
    <a class="card {event.label}" data-label="{event.label}" href="file:///{plot_link}" target="_blank">
        {img_tag}
        <div class="card-body">
            <div class="card-header">
                <span class="card-title">Event {event.event_id}</span>
                <span class="badge {badge_class}">{status_word}</span>
            </div>
            <div class="card-metrics">
                Duration: {_fmt_int(event.duration_ms)} ms |
                Energy: {_fmt_float(event.movement_energy)} |
                Angle: {_fmt_float(event.angle_change_deg)}&deg;
            </div>
        </div>
    </a>"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_int(value) -> str:
    if value is None:
        return "N/A"
    return str(int(value))


def _fmt_float(value, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{decimals}f}"


# ---------------------------------------------------------------------------
# Step 7: Summary
# ---------------------------------------------------------------------------

def print_summary(events: List[EventInfo], pdf_paths: dict, html_path: Path) -> None:
    accepted = sum(1 for e in events if e.label == "accepted")
    rejected = sum(1 for e in events if e.label == "rejected")

    print()
    print("=" * 44)
    print("         REPORT SUMMARY")
    print("=" * 44)
    print()
    print(f"  Accepted : {accepted}")
    print(f"  Rejected : {rejected}")
    print(f"  Total    : {len(events)}")
    print()
    print("  PDF location:")
    for name, path in pdf_paths.items():
        print(f"    {path}")
    print()
    print(f"  HTML dashboard:")
    print(f"    {html_path}")
    print()
    print(f"  PNG folder:")
    print(f"    {IMAGES_DIR}")
    print()
    print("=" * 44)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Discovering events...")
    events = discover_events(ACCEPTED_DIR, REJECTED_DIR)

    if not events:
        log.error("No events found in %s or %s", ACCEPTED_DIR, REJECTED_DIR)
        sys.exit(1)

    log.info("Found %d events (%d accepted, %d rejected)",
             len(events),
             sum(1 for e in events if e.label == "accepted"),
             sum(1 for e in events if e.label == "rejected"))

    log.info("Loading metadata...")
    load_metadata(events)

    log.info("Capturing screenshots (headless Chromium)...")
    capture_screenshots(events, IMAGES_DIR)

    log.info("Generating PDFs...")
    pdf_paths = generate_pdfs(events, REPORTS_DIR)

    log.info("Generating index HTML...")
    html_path = generate_index_html(events, REPORTS_DIR)

    print_summary(events, pdf_paths, html_path)


if __name__ == "__main__":
    main()
