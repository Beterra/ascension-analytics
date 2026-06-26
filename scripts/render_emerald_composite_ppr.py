#!/usr/bin/env python3
"""
render_emerald_composite_ppr.py — Set 1 of the chart deliverable (Emerald Coast, 26016).

Three charts:
  1. Stacked response distribution (1-5 counts) by composite — AS SUBMITTED
        -> figures/ec_composite_stacked_raw.png
  2. Stacked response distribution (1-5 counts) by composite — CORRECTED
        -> figures/ec_composite_stacked_corrected.png
  3. Difference in percent-positive by composite (corrected - as submitted)
        -> figures/ec_composite_difference.png

Stacked charts: per composite, count of responses at each value 1-5 summed across
the composite's items, for the as-submitted (client_files/2024_original) and corrected
(client_files/2024_clientfixed) datasets. The 1-2 vs 4-5 mass swaps on affected composites
and is identical on the two unaffected ones (Communication About Error, Reporting).
BigQuery equivalent: sql/chart_emerald_composite_distribution.sql.

Difference chart: from the official compare export data/compare_corrected_vs_raw.csv;
the 8 affected composites are teal, the 2 unaffected are gray.

Run: python3 scripts/render_emerald_composite_ppr.py
"""
import csv, glob, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(REPO, "figures")
FACILITY = "26016"
RAW_DIR = "client_files/2024_original/3_submission"        # as submitted (normalized)
COR_DIR = "client_files/2024_clientfixed/3_submission"     # corrected (literal)

# ---- Beterra brand palette ----
TEAL = "#49B19A"; TEAL_DK = "#2F7D6C"; MUTED = "#C2C8CC"
INK = "#222222"; GRID = "#E4E7EA"; ZERO = "#444444"
UNAFFECTED = {"FCE", "RPSE"}

# AHRQ-standard 3-bucket split: % positive / % neutral / % negative.
# Responses are bucketed by FAVORABILITY per item polarity (so a composite can
# mix positive and negative items): favorable = 4/5 on positive items and 1/2
# (disagree) on reverse-worded items; neutral = 3; negative = the other end.
# The % positive (green) segment equals the composite percent-positive.
BUCKET_COLORS = {"pos": "#2F8F77", "neu": "#D9D9D9", "neg": "#B5413B"}
BUCKET_LABEL = {"pos": "% Positive", "neu": "% Neutral", "neg": "% Negative"}

COMPOSITE_ORDER = ["Teamwork", "Staffing and Work Pace",
    "Organizational Learning-Continuous Improvement", "Response to Error",
    "Supervisor/Manager/Clinical Leader Support", "Communication Openness",
    "Communication About Error", "Hospital Management Support for Patient Safety",
    "Handoffs and Information Exchange", "Reporting Patient Safety Events"]
SHORT = {"Teamwork": "Teamwork", "Staffing and Work Pace": "Staffing & Work Pace",
    "Organizational Learning-Continuous Improvement": "Organizational Learning",
    "Response to Error": "Response to Error",
    "Supervisor/Manager/Clinical Leader Support": "Supervisor / Manager Support",
    "Communication Openness": "Communication Openness",
    "Communication About Error": "Communication About Error",
    "Hospital Management Support for Patient Safety": "Hospital Mgmt Support",
    "Handoffs and Information Exchange": "Handoffs & Info Exchange",
    "Reporting Patient Safety Events": "Reporting Events"}
CODE = {"Teamwork": "TW", "Staffing and Work Pace": "Staffing",
    "Organizational Learning-Continuous Improvement": "OL", "Response to Error": "NPRE",
    "Supervisor/Manager/Clinical Leader Support": "S/ME", "Communication Openness": "CO",
    "Communication About Error": "FCE", "Hospital Management Support for Patient Safety": "MSPS",
    "Handoffs and Information Exchange": "HT", "Reporting Patient Safety Events": "RPSE"}

def item_meta():
    """{ahca_col: (composite, is_reverse)} for scored composite items."""
    m = {}
    with open(os.path.join(REPO, "data/item_reference.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["scale_type"] in ("agree5", "freq5"):
                m[r["ahca_col"]] = (r["composite"], r["reverse_scored"].strip().upper() == "TRUE")
    return m

def composite_distribution(folder):
    """{composite: {'pos','neu','neg': PERCENT}} across the composite's items for 26016.
    Bucketed by favorability so positive and negative items combine correctly."""
    meta = item_meta()
    hits = glob.glob(os.path.join(REPO, folder, f"{FACILITY} *.csv")) + \
           glob.glob(os.path.join(REPO, folder, f"{FACILITY}.csv"))
    with open(hits[0], newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = rows[1]
    recs = [dict(zip(header, r)) for r in rows[2:] if any(c.strip() for c in r)]
    cnt = {c: {"pos": 0, "neu": 0, "neg": 0} for c in COMPOSITE_ORDER}
    for rec in recs:
        for col, (comp, rev) in meta.items():
            v = rec.get(col, "").strip()
            if not v:
                continue
            try:
                x = int(float(v))
            except ValueError:
                continue
            if x == 3:
                cnt[comp]["neu"] += 1
            elif (x in (4, 5)) != rev:      # favorable: positive-item 4/5, reverse-item 1/2
                cnt[comp]["pos"] += 1
            elif x in (1, 2, 4, 5):
                cnt[comp]["neg"] += 1
    dist = {}
    for c, b in cnt.items():
        tot = b["pos"] + b["neu"] + b["neg"]
        dist[c] = {k: (100 * b[k] / tot if tot else 0) for k in b}
    return dist

def stacked_chart(dist, title, outpath):
    comps = COMPOSITE_ORDER[::-1]   # barh draws bottom-up; first listed ends on top
    labels = [SHORT[c] for c in comps]
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    y = range(len(comps))
    left = [0.0] * len(comps)
    for k in ("pos", "neu", "neg"):       # % positive anchored at 0, then neutral, then negative
        widths = [dist[c][k] for c in comps]
        ax.barh(list(y), widths, left=left, color=BUCKET_COLORS[k], edgecolor="white",
                linewidth=0.5, zorder=3, label=BUCKET_LABEL[k])
        for yi, (w, l) in enumerate(zip(widths, left)):
            if round(w) >= 1:        # label every non-zero segment
                ax.text(l + w / 2, yi, f"{w:.0f}", va="center", ha="center", fontsize=8.5,
                        color=("white" if k != "neu" else "#555555"), fontweight="bold")
        left = [l + w for l, w in zip(left, widths)]
    ax.set_xlim(0, 100)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=11, color=INK)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(axis="x", labelsize=10, colors="#666666")
    ax.set_xlabel("Percent of responses", fontsize=10, color="#666666")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.set_title(title, fontsize=14, color=TEAL_DK, fontweight="bold", loc="left", pad=12)
    ax.legend(ncol=3, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.10),
              frameon=False, handlelength=1.2, columnspacing=1.6)
    fig.tight_layout()
    os.makedirs(FIGDIR, exist_ok=True)
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(outpath, REPO))

def load_diff():
    path = glob.glob(os.path.join(REPO, "data", "compare_corr*_vs_raw.csv"))[0]
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["ascension_code"] == FACILITY and r["aggregation_level"] == "composite":
                code = r["aggregation_code"]
                rows.append({"name": SHORT.get(_full(code), code), "code": code,
                             "diff": round(float(r["pct_corrected"]) - float(r["pct_raw"]), 1),
                             "affected": code not in UNAFFECTED})
    return rows

def _full(code):
    for full, c in CODE.items():
        if c == code:
            return full
    return code

def difference_chart(rows, outpath):
    rows = sorted(rows, key=lambda r: r["diff"])
    labels = [r["name"] for r in rows]; vals = [r["diff"] for r in rows]
    colors = [TEAL if r["affected"] else MUTED for r in rows]
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    y = range(len(rows))
    bars = ax.barh(list(y), vals, color=colors, edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_axisbelow(True); ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=11, color=INK)
    ax.tick_params(axis="y", length=0, pad=6); ax.tick_params(axis="x", labelsize=10, colors="#666666")
    ax.set_xlabel("Percentage-point change", fontsize=10, color="#666666")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.axvline(0, color=ZERO, linewidth=0.9, zorder=2)
    m = max(abs(min(vals)), abs(max(vals)), 1); ax.set_xlim(-m * 1.30, m * 1.30)
    ax.bar_label(bars, labels=[f"{v:+.1f}" for v in vals], padding=4, fontsize=10.5, color=INK, fontweight="bold")
    ax.set_title("Emerald Coast — Correction Impact (Corrected − As Submitted)",
                 fontsize=14, color=TEAL_DK, fontweight="bold", loc="left", pad=12)
    ax.legend(handles=[Patch(color=TEAL, label="Contains reverse-worded items (affected)"),
                       Patch(color=MUTED, label="No reverse-worded items (unaffected)")],
              fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.10),
              ncol=2, frameon=False, handlelength=1.2, columnspacing=1.6)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(outpath, REPO))

def main():
    stacked_chart(composite_distribution(RAW_DIR),
                  "Emerald Coast — Response Distribution by Composite (As Submitted)",
                  os.path.join(FIGDIR, "ec_composite_stacked_raw.png"))
    stacked_chart(composite_distribution(COR_DIR),
                  "Emerald Coast — Response Distribution by Composite (Corrected)",
                  os.path.join(FIGDIR, "ec_composite_stacked_corrected.png"))
    difference_chart(load_diff(), os.path.join(FIGDIR, "ec_composite_difference.png"))

if __name__ == "__main__":
    main()
