#!/usr/bin/env python3
"""
render_oppr_by_facility.py — Set 2 of the chart deliverable.

Three horizontal bar charts of OPPR (overall percent-positive across ALL scored
questions) for the 8 hospitals:
  1. raw (as submitted / incorrect)   -> figures/oppr_facility_raw.png
  2. corrected                        -> figures/oppr_facility_corrected.png
  3. difference (corrected - raw)      -> figures/oppr_facility_difference.png

OPPR = response-weighted mean of the question-level percent-positives
       ( sum(pct * n) / sum(n) over all scored questions ), i.e. positive
       responses pooled across all questions / all responses.

Data source: the official BigQuery export data/compare_corrected_vs_raw.csv
(equivalent to sql/chart_oppr_by_facility.sql). Pass a CSV path as argv[1] to use
a dedicated export instead.

Run: python3 scripts/render_oppr_by_facility.py
"""
import csv, glob, os, sys
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(REPO, "figures")

TEAL = "#49B19A"
TEAL_DK = "#2F7D6C"
INK = "#222222"
GRID = "#E4E7EA"
ZERO = "#444444"

SHORT = {
    "26012": "Pensacola", "26013": "Gulf", "26016": "Emerald Coast", "26042": "Bay",
    "52005": "Southside (St Luke's)", "52009": "Riverside", "52012": "Clay County",
    "52015": "St John's County",
}

def load_rows():
    """Official OPPR per facility from data/oppr_by_facility.csv (view's
    aggregation_level='overall', dimension_type='survey', composite_source='AHRQ').
    Pass a CSV path as argv[1] to use a dedicated export of sql/chart_oppr_by_facility.sql."""
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "data/oppr_by_facility.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = r["ascension_code"]
            rows.append({"code": code, "name": SHORT.get(code, r["facility"]),
                         "raw": round(float(r["oppr_raw"]), 1),
                         "corrected": round(float(r["oppr_corrected"]), 1),
                         "diff": round(float(r["oppr_corrected"]) - float(r["oppr_raw"]), 1)})
    return rows

def barh_chart(rows, value_key, title, outpath, *, signed=False, xlabel="Percent positive"):
    rows = sorted(rows, key=lambda r: r[value_key])
    labels = [r["name"] for r in rows]
    vals = [r[value_key] for r in rows]
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    y = range(len(rows))
    bars = ax.barh(list(y), vals, color=TEAL, edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=11, color=INK)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(axis="x", labelsize=10, colors="#666666")
    ax.set_xlabel(xlabel, fontsize=10, color="#666666")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    fmt = (lambda v: f"{v:+.1f}") if signed else (lambda v: f"{v:.1f}%")
    if signed:
        ax.axvline(0, color=ZERO, linewidth=0.9, zorder=2)
        m = max(abs(min(vals)), abs(max(vals)), 1)
        ax.set_xlim(-m * 1.30, m * 1.30)
    else:
        ax.set_xlim(0, 100)
    ax.bar_label(bars, labels=[fmt(v) for v in vals], padding=4, fontsize=10.5,
                 color=INK, fontweight="bold")
    ax.set_title(title, fontsize=14, color=TEAL_DK, fontweight="bold", loc="left", pad=12)
    fig.tight_layout()
    os.makedirs(FIGDIR, exist_ok=True)
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(outpath, REPO))

def main():
    rows = load_rows()
    assert len(rows) == 8, f"expected 8 facilities, got {len(rows)}"
    OPPR_LABEL = "Overall Percent Positive Response (OPPR)"
    barh_chart(rows, "raw", "Overall % Positive by Hospital (As Submitted)",
               os.path.join(FIGDIR, "oppr_facility_raw.png"), xlabel=OPPR_LABEL)
    barh_chart(rows, "corrected", "Overall % Positive by Hospital (Corrected)",
               os.path.join(FIGDIR, "oppr_facility_corrected.png"), xlabel=OPPR_LABEL)
    barh_chart(rows, "diff", "Correction Impact by Hospital (Corrected − As Submitted)",
               os.path.join(FIGDIR, "oppr_facility_difference.png"), signed=True,
               xlabel="Change in OPPR (percentage points)")

if __name__ == "__main__":
    main()
