#!/usr/bin/env python3
"""
Bundle the Arki Backtest Dashboard into a single standalone HTML file.

All data (CSV, JSON, YAML), CSS, JS, and CDN dependencies are embedded
inline so the recipient can open the file in any browser with zero setup.

Usage:
    python scripts/bundle_dashboard.py                         # latest run
    python scripts/bundle_dashboard.py 20260411_0047_full25_250k  # specific run
    python scripts/bundle_dashboard.py --output ~/Desktop/report.html
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH_DIR = ROOT / "scripts" / "dashboard"
RUNS_DIR = ROOT / "results" / "runs"

# CDN libs to download and embed
CDN_LIBS = [
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js",
    "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js",
]

# Files from the run's data/ directory
DATA_FILES = [
    "dashboard_meta.json",
    "rolling_stats.csv",
    "daily_returns.csv",
    "position_snapshot.csv",
    "notional_positions.csv",
    "factor_returns.csv",
    "forecast_weights.csv",
    "turnover.csv",
    "instrument_weights.csv",
    "rounded_positions.csv",
    "contract_values.csv",
    "spread_costs.csv",
    "methodology.json",
    "config.yaml",
    "stats.yaml",
    "equity_curve.csv",
    "subsystem_positions.csv",
]

# Dashboard-root level JSON files
DASHBOARD_JSONS = [
    "arki_macro_summary.json",
    "arki_macro_smaller.json",
    "arki_macro_comparison.json",
    "arki_universe_info.json",
    "sweep_summary.json",
]


def resolve_run(run_id: str | None) -> Path:
    """Resolve run directory. None = latest."""
    if run_id:
        p = RUNS_DIR / run_id
        if not p.is_dir():
            sys.exit(f"❌  Run not found: {p}")
        return p
    runs = sorted(d.name for d in RUNS_DIR.iterdir() if d.is_dir())
    if not runs:
        sys.exit("❌  No runs found in results/runs/")
    return RUNS_DIR / runs[-1]


def download_cdn(url: str) -> str:
    """Download a CDN script and return its text."""
    cache_dir = ROOT / ".cache" / "cdn"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = url.split("/")[-1]
    cache_path = cache_dir / fname

    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    print(f"  ⬇  Downloading {fname}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode("utf-8")
    cache_path.write_text(text, encoding="utf-8")
    return text


def read_safe(path: Path) -> str | None:
    """Read file if it exists, else None."""
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return None


def escape_for_js_string(text: str) -> str:
    """Escape text for use inside a JS template literal (backtick string)."""
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def build_embedded_store(run_dir: Path) -> str:
    """Build the JS object mapping paths to file contents."""
    store = {}

    # Data files from run directory
    for fname in DATA_FILES:
        content = read_safe(run_dir / fname)
        if content:
            store[f"data/{fname}"] = content

    # Sweep summary can also be inside data/
    sweep_data = read_safe(run_dir / "sweep_summary.json")
    if sweep_data:
        store["data/sweep_summary.json"] = sweep_data

    # Dashboard-root JSON files
    for fname in DASHBOARD_JSONS:
        content = read_safe(DASH_DIR / fname)
        if content:
            store[fname] = content

    # Universe compare (may be in data/)
    uc = read_safe(run_dir / "arki_macro_universe_compare.json")
    if uc:
        store["data/arki_macro_universe_compare.json"] = uc

    # Registry YAML from registry
    reg = read_safe(RUNS_DIR / "registry.yaml")
    if reg:
        store["data/registry.yaml"] = reg
        store["../../../results/runs/registry.yaml"] = reg

    total_kb = sum(len(v) for v in store.values()) / 1024
    print(f"  📦  Embedded {len(store)} files ({total_kb:.0f} KB)")

    # Build JS: use base64 to avoid any escaping issues with large CSVs
    lines = ["window.__EMBEDDED_DATA__ = {};"]
    for path, content in store.items():
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        lines.append(
            f'window.__EMBEDDED_DATA__["{path}"] = atob("{b64}");'
        )
    return "\n".join(lines)


def patch_app_js(js_text: str) -> str:
    """Replace the loadFile function to read from embedded store."""
    # Replace the loadFile function with one that reads from the embedded store
    patched_load = """\
async function loadFile(path) {
  if (window.__EMBEDDED_DATA__ && window.__EMBEDDED_DATA__[path] !== undefined) {
    return window.__EMBEDDED_DATA__[path];
  }
  throw new Error('File not found in embedded data: ' + path);
}"""

    # Replace the original loadFile function
    old_load = """async function loadFile(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`);
  return resp.text();
}"""

    if old_load in js_text:
        js_text = js_text.replace(old_load, patched_load)
    else:
        # Fallback: regex-based replacement
        import re
        pattern = r'async function loadFile\(path\)\s*\{[^}]+\}'
        js_text = re.sub(pattern, patched_load, js_text, count=1)

    # Also patch the direct fetch() calls in renderRunsTable
    # Replace fetch('data/registry.yaml') pattern with loadFile equivalent
    old_registry = "fetch('data/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text => {"
    new_registry = "loadFile('data/registry.yaml').then(text => {"

    if old_registry in js_text:
        # Replace the entire renderRunsTable function's fetch chain
        old_block = """  fetch('data/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text => {
    if (!text) {
      fetch('../../../results/runs/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text2 => {
        if (!text2) {
          el.innerHTML = '<p style="color:var(--text-muted);padding:var(--space-md)">No registry found. Run backtests with <code>backtest_runner.py</code> to populate.</p>';
          return;
        }
        buildRunsTable(el, text2);
      });
      return;
    }
    buildRunsTable(el, text);
  });"""

        new_block = """  loadFile('data/registry.yaml').then(text => {
    buildRunsTable(el, text);
  }).catch(() => {
    el.innerHTML = '<p style="color:var(--text-muted);padding:var(--space-md)">Registry data not available in this export.</p>';
  });"""
        js_text = js_text.replace(old_block, new_block)

    return js_text


def build_html(run_dir: Path, output_path: Path) -> None:
    """Build the standalone HTML file."""

    run_id = run_dir.name
    print(f"\n🔧  Bundling dashboard for run: {run_id}")

    # 1. Download CDN dependencies
    print("  📥  Resolving CDN dependencies...")
    cdn_scripts = []
    for url in CDN_LIBS:
        cdn_scripts.append(download_cdn(url))

    # 2. Read CSS
    css_text = (DASH_DIR / "styles.css").read_text(encoding="utf-8")

    # 3. Read and patch app.js
    app_js = (DASH_DIR / "app.js").read_text(encoding="utf-8")
    app_js = patch_app_js(app_js)

    # 4. Build embedded data store
    data_store_js = build_embedded_store(run_dir)

    # 5. Read index.html and extract body content
    html_src = (DASH_DIR / "index.html").read_text(encoding="utf-8")

    # Extract the body content (between <body> and </body>)
    body_start = html_src.index("<body>") + len("<body>")
    body_end = html_src.index("</body>")
    body_content = html_src[body_start:body_end]

    # Remove the original script tags from body
    body_content = body_content.replace(
        '<script src="app.js?v=20260411f"></script>', ""
    )
    # Also handle other potential versions
    import re
    body_content = re.sub(
        r'<script src="app\.js[^"]*"></script>', "", body_content
    )

    # 6. Assemble the standalone HTML
    standalone = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arki Backtest Analytics — {run_id}</title>
  <meta name="description" content="Standalone backtest analytics dashboard for run {run_id}">
  <style>
{css_text}
  </style>
  <script>
{chr(10).join(cdn_scripts)}
  </script>
</head>
<body>
{body_content}
<script>
// ── Embedded Data Store ──
{data_store_js}
</script>
<script>
// ── Application ──
{app_js}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(standalone, encoding="utf-8")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n✅  Standalone dashboard saved: {output_path}")
    print(f"    Size: {size_mb:.1f} MB")
    print(f"    Open in browser: file://{output_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Bundle Arki Backtest Dashboard into a standalone HTML file"
    )
    parser.add_argument(
        "run_id",
        nargs="?",
        default=None,
        help="Run ID (default: latest run)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: results/exports/<RUN_ID>.html)",
    )
    args = parser.parse_args()

    run_dir = resolve_run(args.run_id)

    if args.output:
        output = Path(args.output)
    else:
        output = ROOT / "results" / "exports" / f"{run_dir.name}.html"

    build_html(run_dir, output)


if __name__ == "__main__":
    main()
