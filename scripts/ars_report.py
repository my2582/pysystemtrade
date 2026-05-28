"""ARS run report renderer (Arki Macro Mini style).

Single entry point: render_run_report(...). Loads
arki/templates/ars_run_report.html, fills {{KEY}} placeholders, writes
report.html into the run dir, optionally renders to PDF via headless
Chrome (~/Applications/Google Chrome.app).

Reused across ARS run scripts to standardise output style (Arki Green +
Roboto, 2-page A4: exec summary + per-trade analysis).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "arki" / "templates" / "ars_run_report.html"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _df_to_html_table(df: pd.DataFrame, label_col: str | None = None) -> str:
    """Render a DataFrame as an Arki-styled HTML table (no pandas styling)."""
    cols = list(df.columns)
    th = "".join(f'<th>{c}</th>' for c in ([label_col or df.index.name or ""] + cols))
    rows = []
    for idx, row in df.iterrows():
        cells = f'<td class="lbl">{idx}</td>' + "".join(
            f'<td>{_fmt(row[c])}</td>' for c in cols)
        rows.append(f"<tr>{cells}</tr>")
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _kv_table(pairs: Iterable[tuple[str, object]]) -> str:
    body = "".join(
        f'<tr><td class="lbl">{k}</td><td>{_fmt(v)}</td></tr>'
        for k, v in pairs)
    return f'<table class="kv"><tbody>{body}</tbody></table>'


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, dict):
        return ", ".join(f"{k}={v}" for k, v in v.items())
    return str(v)


def _verdict_row(claim: str, passed: bool, evidence: str) -> str:
    badge = '<span class="pass">PASS</span>' if passed else '<span class="fail">FAIL</span>'
    return (f'<div class="v-row">{badge}'
            f'<span class="v-claim">{claim}</span>'
            f'<span class="v-evidence">{evidence}</span></div>')


def render_run_report(
    run_dir: Path,
    *,
    title: str,
    subtitle: str,
    run_date: str,
    run_utc: str,
    git_sha: str,
    literature: str,
    summary_df: pd.DataFrame,
    trade_stats_df: pd.DataFrame,
    manifest_pairs: Iterable[tuple[str, object]],
    verdicts: list[tuple[str, bool, str]],
    equity_png: str,
    equity_caption: str,
    trade_png: str,
    trade_caption: str,
    instrument_list: str,
    make_pdf: bool = True,
) -> dict[str, Path]:
    """Render the standard ARS run report HTML (and optionally PDF)."""
    tpl = TEMPLATE.read_text()
    repl = {
        "TITLE": title,
        "SUBTITLE": subtitle,
        "RUN_DATE": run_date,
        "RUN_UTC": run_utc,
        "GIT_SHA_SHORT": git_sha[:8],
        "LITERATURE": literature,
        "INSTRUMENT_LIST": instrument_list,
        "EQUITY_PNG": equity_png,
        "EQUITY_CAPTION": equity_caption,
        "TRADE_PNG": trade_png,
        "TRADE_CAPTION": trade_caption,
        "SUMMARY_TABLE": _df_to_html_table(summary_df, "instrument"),
        "TRADE_TABLE": _df_to_html_table(trade_stats_df, "instrument"),
        "MANIFEST_TABLE": _kv_table(manifest_pairs),
        "VERDICT_ROWS": "\n".join(_verdict_row(*v) for v in verdicts),
    }
    html = tpl
    for k, v in repl.items():
        html = html.replace(f"{{{{{k}}}}}", str(v))

    html_path = run_dir / "report.html"
    html_path.write_text(html)
    out = {"html": html_path}

    if make_pdf and Path(CHROME).exists():
        pdf_path = run_dir / "report.pdf"
        cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
               "--no-pdf-header-footer", "--print-to-pdf-no-header",
               f"--print-to-pdf={pdf_path}",
               f"file://{html_path.resolve()}"]
        result = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
        if pdf_path.exists() and pdf_path.stat().st_size > 1024:
            out["pdf"] = pdf_path
        else:
            print(f"[warn] PDF render failed: {result.stderr.decode()[:200]}")
    elif make_pdf:
        print(f"[warn] Chrome not found at {CHROME}; PDF skipped")

    return out
