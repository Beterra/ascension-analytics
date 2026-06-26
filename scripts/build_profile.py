#!/usr/bin/env python3
"""
Profiling + snapshot foundation for the report. Computes from local submission
CSVs (validated method: positive = 4/5 over all non-missing, neutrals in denom):

  1. data/response_profile.csv       n respondents per facility (+ region, + pooled system)
  2. data/reverse_item_distributions.csv  1-5 response counts per reverse item,
                                           corrected vs submitted, pooled across facilities
  3. data/exec_snapshot.csv          per-facility overall % positive corrected vs submitted + delta
  4. data/question_counts.csv        n answered per item per facility

Orientation (validated against BigQuery): client_files/2024_original is the prior vendor's
NORMALIZED export — its raw 1-5 values equal the AS-SUBMITTED distribution, and naive
4/5 scoring of it recovers the CORRECTED score; client_files/2024_clientfixed holds the literal
(CORRECTED) responses. exec_snapshot now sources the official OPPR directly.
"""
import csv, glob, json, os
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORR = "client_files/2024_original/3_submission"
SUBM = "client_files/2024_clientfixed/3_submission"

def load_items():
    rows = []
    with open(os.path.join(REPO, "data/item_reference.csv"), newline="") as f:
        for r in csv.DictReader(f):
            r["rev"] = r["reverse_scored"].strip().upper() == "TRUE"
            rows.append(r)
    return rows

def entities():
    with open(os.path.join(REPO, "surveys.json")) as f:
        return json.load(f)

def facilities():
    return [(e["ascension_code"], e["name"], e["region"]) for e in entities() if e.get("level") == "Facility"]

def load_sub(folder, code):
    hits = glob.glob(os.path.join(REPO, folder, f"{code} *.csv")) + glob.glob(os.path.join(REPO, folder, f"{code}.csv"))
    if not hits:
        return None
    with open(hits[0], newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return [dict(zip(rows[1], r)) for r in rows[2:] if any(c.strip() for c in r)]

def ival(s):
    s = s.strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None

def main():
    items = load_items()
    agree5 = [r for r in items if r["scale_type"] == "agree5"]
    revs = [r for r in items if r["rev"]]
    facs = facilities()

    # 1. response profile
    with open(os.path.join(REPO, "data/response_profile.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ascension_code", "facility", "region", "n_respondents"])
        total = 0
        for code, name, region in facs:
            recs = load_sub(CORR, code); n = len(recs) if recs else 0; total += n
            w.writerow([code, name, region, n])
        w.writerow(["", "Ascension Florida (pooled facilities)", "", total])
    print(f"[1] response_profile.csv  (pooled n={total})")

    # 2. reverse-item distributions (pooled across facilities), corrected vs submitted.
    # 2024_clientfixed = literal CORRECTED responses; 2024_original (normalized export)
    # carries the AS-SUBMITTED distribution. Verified vs BigQuery response_breakdown.
    with open(os.path.join(REPO, "data/reverse_item_distributions.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "composite", "version", "n", "pct_1", "pct_2", "pct_3", "pct_4", "pct_5", "item_text"])
        for folder, ver in [(SUBM, "corrected"), (CORR, "submitted")]:
            allrecs = []
            for code, _, _ in facs:
                r = load_sub(folder, code)
                if r: allrecs += r
            for it in revs:
                dist = defaultdict(int); n = 0
                for rec in allrecs:
                    x = ival(rec.get(it["ahca_col"], ""))
                    if x in (1, 2, 3, 4, 5):
                        dist[x] += 1; n += 1
                pcts = [round(100 * dist[k] / n, 1) if n else 0 for k in (1, 2, 3, 4, 5)]
                w.writerow([it["ahca_col"], it["composite"], ver, n, *pcts, it["item_text"]])
    print("[2] reverse_item_distributions.csv")

    # 3. exec snapshot — OFFICIAL overall OPPR per facility from the analytics system
    #    (data/oppr_by_facility.csv), not local naive scoring.
    oppr = {}
    with open(os.path.join(REPO, "data/oppr_by_facility.csv"), newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            oppr[r["ascension_code"]] = r
    with open(os.path.join(REPO, "data/exec_snapshot.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ascension_code", "facility", "region", "n", "overall_corrected", "overall_submitted", "delta_pts"])
        print("\n   exec snapshot (official OPPR):")
        print(f"   {'code':<7}{'corr':>6}{'subm':>6}{'Δ':>6}  facility")
        for code, name, region in facs:
            o = oppr.get(code)
            if not o:
                continue
            oc = round(float(o["oppr_corrected"]), 1)
            osub = round(float(o["oppr_raw"]), 1)
            d = round(oc - osub, 1)
            w.writerow([code, name, region, int(float(o["n"])), oc, osub, d])
            print(f"   {code:<7}{oc:>6}{osub:>6}{d:>6}  {name}")
    print("[3] exec_snapshot.csv")

    # 4. per-question counts (n answered) per facility, all 42 columns
    allcols = [r["ahca_col"] for r in items]
    with open(os.path.join(REPO, "data/question_counts.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ascension_code", "facility", "item", "n_answered"])
        for code, name, region in facs:
            recs = load_sub(CORR, code) or []
            for c in allcols:
                n = sum(1 for rec in recs if rec.get(c, "").strip())
                w.writerow([code, name, c, n])
    print("[4] question_counts.csv")

if __name__ == "__main__":
    main()
