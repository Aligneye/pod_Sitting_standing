"""
Generate a single-page interactive event debug dashboard.

Aggregates ALL detected events (accepted and rejected) into one scrollable
HTML page with collapsible cards, embedded Plotly graphs, sticky sidebar
navigation, and top-level filters and summary statistics.

Existing individual event HTML files are NOT modified.

Run from the project root:

    python analysis/event_analysis/generate_dashboard.py

Output:

    analysis/event_analysis/reports/event_debug_dashboard.html
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List

import numpy as np

DEFAULT_ACCEPTED_DIR = Path("debug/events")
DEFAULT_REJECTED_DIR = Path("debug/rejected_events")
DEFAULT_OUTPUT = Path("analysis/event_analysis/reports/event_debug_dashboard.html")


def load_event_data(directory: Path, label: str) -> List[dict]:
    """Load event summaries and their plot HTML from a directory."""
    if not directory.exists():
        return []

    events = []
    for summary_path in sorted(directory.glob("event_*/event_summary.json")):
        event_dir = summary_path.parent
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        plot_path = event_dir / "event_plot.html"
        plot_html = ""
        if plot_path.exists():
            plot_html = _extract_plotly_div(plot_path)

        events.append({
            "label": label,
            "event_dir": str(event_dir),
            "summary": data,
            "plot_html": plot_html,
        })
    return events


def _extract_plotly_div(html_path: Path) -> str:
    """Extract the Plotly div+data script from a standalone HTML file.

    Plotly's write_html bundles the full library inline (~4.8MB). We skip that
    and only extract:
    1. The <div> placeholder
    2. The final <script> that calls Plotly.newPlot with the data/layout

    The dashboard loads Plotly from CDN, so the bundled library is not needed.
    """
    raw = html_path.read_text(encoding="utf-8")

    div_match = re.search(r'(<div id="[^"]*"[^>]*>.*?</div>)', raw, re.DOTALL)
    if not div_match:
        return ""

    scripts = re.findall(r'(<script>.*?</script>)', raw, re.DOTALL)
    data_script = None
    for script in reversed(scripts):
        if "Plotly.newPlot" in script:
            data_script = script
            break

    if not data_script:
        return ""

    return div_match.group(1) + "\n" + data_script


def _fmt(value, decimals=2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if np.isnan(value):
            return "N/A"
        return f"{value:.{decimals}f}"
    return str(value)


def _build_event_card(event: dict, card_index: int) -> str:
    """Build the HTML for one collapsible event card."""
    data = event["summary"]
    label = event["label"]
    general = data.get("general", {})
    movement = data.get("movement", {})
    validation = data.get("validation", {})
    stages = validation.get("stages", {})
    stats = data.get("statistical_features", {})
    rolling_std = validation.get("rolling_std_metrics", {})
    stability_diag = validation.get("stability_diagnostics", {})
    legacy = validation.get("legacy_orientation_metrics", {})

    event_id = general.get("event_id", "?")
    status = validation.get("status", "UNKNOWN")
    is_valid = status == "VALID_TRANSITION"
    status_icon = "✅" if is_valid else "❌"
    status_class = "valid" if is_valid else "rejected"

    movement_stage = stages.get("movement", {})
    orientation_stage = stages.get("orientation", {})
    movement_pass = movement_stage.get("passed")
    orientation_pass = orientation_stage.get("passed")

    def stage_icon(passed):
        if passed is None:
            return "—"
        return "✅" if passed else "❌"

    metrics_html = f"""
    <div class="metrics-grid">
        <div class="metric"><span class="metric-label">Total Duration</span><span class="metric-value">{_fmt(general.get('duration_ms'), 0)} ms</span></div>
        <div class="metric"><span class="metric-label">Movement Duration</span><span class="metric-value">{_fmt(movement.get('movement_duration_ms'), 0)} ms</span></div>
        <div class="metric"><span class="metric-label">Rolling STD Peak</span><span class="metric-value">{_fmt(rolling_std.get('rolling_std_peak'))}</span></div>
        <div class="metric"><span class="metric-label">Rolling STD Duration</span><span class="metric-value">{_fmt(rolling_std.get('rolling_std_duration_above_threshold'), 0)}</span></div>
        <div class="metric"><span class="metric-label">Movement Energy</span><span class="metric-value">{_fmt(stats.get('movement_energy'))}</span></div>
        <div class="metric"><span class="metric-label">Angle Change</span><span class="metric-value">{_fmt(legacy.get('angle_change_deg'))}&deg;</span></div>
        <div class="metric"><span class="metric-label">Sample Count</span><span class="metric-value">{_fmt(general.get('total_samples'), 0)}</span></div>
        <div class="metric"><span class="metric-label">Debounce Merges</span><span class="metric-value">{_fmt(movement.get('debounce_merges', 0), 0)}</span></div>
    </div>
    """

    rejection_html = ""
    if not is_valid:
        reason = validation.get("reason", "Unknown")
        rej_stage = validation.get("rejection_stage", "Unknown")
        rejection_html = f"""
        <div class="rejection-info">
            <strong>Rejected at:</strong> {rej_stage}<br>
            <strong>Reason:</strong> {reason}
        </div>
        """

    stability_html = ""
    if stability_diag:
        stability_html = f"""
        <div class="stability-info">
            <span class="stage-label">Stability (diagnostic):</span>
            PRE={_fmt(stability_diag.get('combined_std_pre'))} |
            POST={_fmt(stability_diag.get('combined_std_post'))} |
            Ratio={_fmt(stability_diag.get('transition_to_stable_ratio'))}
        </div>
        """

    plot_div = event["plot_html"]
    plot_section = ""
    if plot_div:
        plot_section = f'<div class="plot-container">{plot_div}</div>'
    else:
        plot_section = '<div class="plot-container"><p class="no-plot">Plot not available</p></div>'

    card_id = f"event-{event_id}"

    return f"""
    <div class="event-card {status_class}" id="{card_id}" data-label="{label}" data-event-id="{event_id}">
        <div class="card-header" onclick="toggleCard(this)">
            <span class="event-title">Event {event_id}</span>
            <span class="status-badge {status_class}">{status_icon} {status}</span>
            <span class="duration-badge">{_fmt(general.get('duration_ms'), 0)} ms</span>
            <span class="expand-icon">▼</span>
        </div>
        <div class="card-body" style="display:none;">
            <div class="validation-stages">
                <span class="stage-label">Movement:</span> {stage_icon(movement_pass)}
                <span class="stage-label" style="margin-left:16px;">Orientation:</span> {stage_icon(orientation_pass)}
            </div>
            {stability_html}
            {rejection_html}
            {metrics_html}
            {plot_section}
        </div>
    </div>
    """


def _build_summary_stats(events: List[dict]) -> str:
    """Build top-level summary statistics HTML."""
    accepted = [e for e in events if e["label"] == "accepted"]
    rejected = [e for e in events if e["label"] == "rejected"]

    def avg(events_list, *keys):
        values = []
        for e in events_list:
            d = e["summary"]
            val = None
            for k in keys:
                if isinstance(d, dict):
                    d = d.get(k)
                else:
                    break
            val = d
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                values.append(float(val))
        if not values:
            return "N/A"
        return f"{np.mean(values):.1f}"

    return f"""
    <div class="summary-stats">
        <div class="stat-group">
            <div class="stat-box accepted-box">
                <div class="stat-number">{len(accepted)}</div>
                <div class="stat-label">Accepted</div>
            </div>
            <div class="stat-box rejected-box">
                <div class="stat-number">{len(rejected)}</div>
                <div class="stat-label">Rejected</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(events)}</div>
                <div class="stat-label">Total</div>
            </div>
        </div>
        <div class="stat-group">
            <div class="stat-box">
                <div class="stat-number">{avg(events, 'general', 'duration_ms')}</div>
                <div class="stat-label">Avg Duration (ms)</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{avg(events, 'statistical_features', 'movement_energy')}</div>
                <div class="stat-label">Avg Movement Energy</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{avg(events, 'validation', 'legacy_orientation_metrics', 'angle_change_deg')}</div>
                <div class="stat-label">Avg Angle Change (&deg;)</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{avg(events, 'validation', 'rolling_std_metrics', 'rolling_std_duration_above_threshold')}</div>
                <div class="stat-label">Avg Rolling STD Duration</div>
            </div>
        </div>
    </div>
    """


def _build_sidebar(events: List[dict]) -> str:
    """Build the sticky sidebar navigation."""
    accepted = [e for e in events if e["label"] == "accepted"]
    rejected = [e for e in events if e["label"] == "rejected"]

    def link_list(event_list):
        links = []
        for e in event_list:
            eid = e["summary"].get("general", {}).get("event_id", "?")
            links.append(f'<a href="#event-{eid}" class="sidebar-link" data-label="{e["label"]}">Event {eid}</a>')
        return "\n".join(links)

    return f"""
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-header">Events</div>
        <div class="sidebar-section">
            <div class="sidebar-section-title accepted-title">Accepted ({len(accepted)})</div>
            {link_list(accepted)}
        </div>
        <div class="sidebar-section">
            <div class="sidebar-section-title rejected-title">Rejected ({len(rejected)})</div>
            {link_list(rejected)}
        </div>
    </nav>
    """


def generate_dashboard(accepted_dir: Path, rejected_dir: Path, output_path: Path) -> None:
    """Generate the single-page event debug dashboard."""
    events = []
    events.extend(load_event_data(accepted_dir, "accepted"))
    events.extend(load_event_data(rejected_dir, "rejected"))

    events.sort(key=lambda e: e["summary"].get("general", {}).get("event_id", 0))

    if not events:
        print("No events found.")
        return

    cards_html = "\n".join(
        _build_event_card(e, i) for i, e in enumerate(events)
    )
    sidebar_html = _build_sidebar(events)
    summary_html = _build_summary_stats(events)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Event Debug Dashboard</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f6fa;
    color: #2c3e50;
    line-height: 1.5;
}}
.layout {{
    display: flex;
    min-height: 100vh;
}}
.sidebar {{
    position: sticky;
    top: 0;
    width: 200px;
    height: 100vh;
    overflow-y: auto;
    background: #2c3e50;
    color: #ecf0f1;
    padding: 16px 0;
    flex-shrink: 0;
}}
.sidebar-header {{
    font-size: 16px;
    font-weight: 700;
    padding: 0 16px 12px;
    border-bottom: 1px solid #34495e;
    margin-bottom: 8px;
}}
.sidebar-section {{ margin-bottom: 12px; }}
.sidebar-section-title {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 16px 4px;
}}
.accepted-title {{ color: #2ecc71; }}
.rejected-title {{ color: #e74c3c; }}
.sidebar-link {{
    display: block;
    padding: 3px 16px 3px 24px;
    color: #bdc3c7;
    text-decoration: none;
    font-size: 12px;
    transition: background 0.15s;
}}
.sidebar-link:hover {{ background: #34495e; color: #fff; }}
.sidebar-link.hidden {{ display: none; }}
.main-content {{
    flex: 1;
    padding: 24px 32px;
    max-width: calc(100% - 200px);
}}
.top-bar {{
    background: #fff;
    border-radius: 8px;
    padding: 16px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.filters {{
    display: flex;
    gap: 16px;
    align-items: center;
    margin-bottom: 12px;
}}
.filters label {{
    font-size: 13px;
    cursor: pointer;
    user-select: none;
}}
.filters input {{ margin-right: 4px; }}
.summary-stats {{
    display: flex;
    flex-direction: column;
    gap: 12px;
}}
.stat-group {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}}
.stat-box {{
    background: #f8f9fa;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: center;
    min-width: 100px;
}}
.stat-box.accepted-box {{ border-left: 3px solid #2ecc71; }}
.stat-box.rejected-box {{ border-left: 3px solid #e74c3c; }}
.stat-number {{ font-size: 20px; font-weight: 700; }}
.stat-label {{ font-size: 11px; color: #7f8c8d; text-transform: uppercase; }}
.event-card {{
    background: #fff;
    border-radius: 8px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    overflow: hidden;
    border-left: 4px solid #bdc3c7;
}}
.event-card.valid {{ border-left-color: #2ecc71; }}
.event-card.rejected {{ border-left-color: #e74c3c; }}
.event-card.hidden {{ display: none; }}
.card-header {{
    display: flex;
    align-items: center;
    padding: 12px 20px;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;
}}
.card-header:hover {{ background: #f8f9fa; }}
.event-title {{ font-weight: 600; font-size: 14px; margin-right: 12px; }}
.status-badge {{
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
    margin-right: 12px;
}}
.status-badge.valid {{ background: #d4efdf; color: #1e8449; }}
.status-badge.rejected {{ background: #fadbd8; color: #922b21; }}
.duration-badge {{
    font-size: 12px;
    color: #7f8c8d;
    margin-right: auto;
}}
.expand-icon {{
    font-size: 12px;
    color: #7f8c8d;
    transition: transform 0.2s;
}}
.expand-icon.open {{ transform: rotate(180deg); }}
.card-body {{ padding: 12px 20px 20px; }}
.validation-stages {{
    font-size: 13px;
    margin-bottom: 8px;
}}
.stage-label {{ font-weight: 600; }}
.stability-info {{
    font-size: 12px;
    color: #7f8c8d;
    margin-bottom: 8px;
}}
.rejection-info {{
    background: #fdedec;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
    margin-bottom: 12px;
    border: 1px solid #f5c6cb;
}}
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 8px;
    margin-bottom: 16px;
}}
.metric {{
    display: flex;
    flex-direction: column;
    background: #f8f9fa;
    border-radius: 4px;
    padding: 8px 12px;
}}
.metric-label {{ font-size: 10px; text-transform: uppercase; color: #7f8c8d; letter-spacing: 0.3px; }}
.metric-value {{ font-size: 14px; font-weight: 600; }}
.plot-container {{
    width: 100%;
    min-height: 350px;
}}
.plot-container .js-plotly-plot {{
    width: 100% !important;
}}
.no-plot {{
    color: #7f8c8d;
    font-style: italic;
    padding: 24px;
    text-align: center;
}}
</style>
</head>
<body>
<div class="layout">
{sidebar_html}
<div class="main-content">
    <div class="top-bar">
        <div class="filters">
            <label><input type="checkbox" id="filter-accepted" checked onchange="applyFilters()"> Accepted</label>
            <label><input type="checkbox" id="filter-rejected" checked onchange="applyFilters()"> Rejected</label>
        </div>
        {summary_html}
    </div>
    <div id="events-container">
        {cards_html}
    </div>
</div>
</div>
<script>
function toggleCard(header) {{
    const body = header.nextElementSibling;
    const icon = header.querySelector('.expand-icon');
    if (body.style.display === 'none') {{
        body.style.display = 'block';
        icon.classList.add('open');
        // Trigger Plotly resize after expanding
        const plots = body.querySelectorAll('.js-plotly-plot');
        plots.forEach(p => Plotly.Plots.resize(p));
    }} else {{
        body.style.display = 'none';
        icon.classList.remove('open');
    }}
}}

function applyFilters() {{
    const showAccepted = document.getElementById('filter-accepted').checked;
    const showRejected = document.getElementById('filter-rejected').checked;

    document.querySelectorAll('.event-card').forEach(card => {{
        const label = card.getAttribute('data-label');
        if ((label === 'accepted' && showAccepted) || (label === 'rejected' && showRejected)) {{
            card.classList.remove('hidden');
        }} else {{
            card.classList.add('hidden');
        }}
    }});

    document.querySelectorAll('.sidebar-link').forEach(link => {{
        const label = link.getAttribute('data-label');
        if ((label === 'accepted' && showAccepted) || (label === 'rejected' && showRejected)) {{
            link.classList.remove('hidden');
        }} else {{
            link.classList.add('hidden');
        }}
    }});
}}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard generated: {output_path}")
    print(f"  Total events: {len(events)}")
    print(f"  Accepted: {sum(1 for e in events if e['label'] == 'accepted')}")
    print(f"  Rejected: {sum(1 for e in events if e['label'] == 'rejected')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate event debug dashboard.")
    parser.add_argument("--accepted-dir", default=str(DEFAULT_ACCEPTED_DIR))
    parser.add_argument("--rejected-dir", default=str(DEFAULT_REJECTED_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    generate_dashboard(
        Path(args.accepted_dir),
        Path(args.rejected_dir),
        Path(args.output),
    )


if __name__ == "__main__":
    main()
