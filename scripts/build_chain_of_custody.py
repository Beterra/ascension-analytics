#!/usr/bin/env python3
"""
Comprehensive chain-of-custody table: for every facility x question x composite,
percent-positive at each stage of the chain, as columns:

  export_pct       - Perceptyx SOURCE export (.xlsx), scored AHCA-standard
  as_submitted_pct - what AHCA received (= BigQuery raw, from the comparison export)
  corrected_pct    - corrected/literal (= BigQuery corrected, from the comparison export)

Scoring = AHRQ/AHCA standard: positively-worded item positive = responses 4/5;
negatively-worded item positive = responses 1/2; neutral (3) kept in denominator.
Composites = mean of their item percent-positives (item-averaged, matching the DB).

export_pct should ~equal as_submitted_pct on every item (the AHCA tool passed the
normalized export straight through); both diverge from corrected_pct only on the
13 reverse-worded items. Output: data/chain_of_custody.csv
"""
import openpyxl, csv, glob, os
from collections import defaultdict, Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUS = ["26012", "26013", "26016", "26042", "52005", "52009", "52012", "52015"]

def load_items():
    items = {}
    with open(os.path.join(REPO, "data/item_reference.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["scale_type"] == "agree5":
                items[r["ahca_col"]] = {"text": r["item_text"], "composite": r["composite"],
                                        "neg": r["reverse_scored"].strip().upper() == "TRUE"}
    return items

def norm(s):
    return "".join(c for c in s.lower() if c.isalnum())[:40]

def pct(counts, neg):
    tot = sum(counts.get(k, 0) for k in (1, 2, 3, 4, 5))
    if not tot:
        return None
    pos = (counts.get(1, 0)+counts.get(2, 0)) if neg else (counts.get(4, 0)+counts.get(5, 0))
    return 100*pos/tot

def export_counts(items):
    """per BU per AHCA-col Counter of 1-5 from the Perceptyx source export."""
    wb = openpyxl.load_workbook(os.path.join(REPO, "client_files/2024_original/1_perceptyx/Original Perceptyx Data File - Florida Hospitals Only.xlsx"), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    hdr = [("" if h is None else str(h)) for h in next(rows)]
    # FULL normalized text (no truncation) and EXACT match only — loose substring
    # matching previously mis-mapped F5/F6 to the short "Shift" demographic column.
    def nfull(s): return "".join(c for c in s.lower() if c.isalnum())
    hfull = [nfull(h) for h in hdr]
    col_idx = {}
    for col, meta in items.items():
        key = nfull(meta["text"])
        idx = next((i for i, hn in enumerate(hfull) if hn == key), None)
        if idx is None:  # fallback: unambiguous prefix match (>=25 chars), guards against short generics
            cands = [i for i, hn in enumerate(hfull) if len(hn) >= 25 and (hn.startswith(key) or key.startswith(hn))]
            idx = cands[0] if len(cands) == 1 else None
        if idx is not None:
            col_idx[col] = idx
    missing = [c for c in items if c not in col_idx]
    assert not missing, f"unmapped export columns: {missing}"
    data = {bu: {c: Counter() for c in items} for bu in BUS}
    for r in rows:
        bu = str(r[2])
        if bu not in BUS:
            continue
        for col, idx in col_idx.items():
            try:
                x = int(float(r[idx]))
                if 1 <= x <= 5:
                    data[bu][col][x] += 1
            except (TypeError, ValueError):
                pass
    return data, missing

def load_compare():
    """ (level, code, ascension_code) -> (as_submitted=pct_raw, corrected=pct_corrected) """
    path = glob.glob(os.path.join(REPO, "data", "compare_corr*_vs_raw.csv"))[0]
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["ascension_code"] == "SYSTEM":
                continue
            code = r["aggregation_code"].lstrip("0") if r["aggregation_code"][:1].isalpha() is False else r["aggregation_code"]
            # normalize question codes A01->A1 etc.; composite codes left as-is
            if r["aggregation_level"] == "question":
                c = r["aggregation_code"]
                code = c[0] + str(int(c[1:])) if c[1:].isdigit() else c
            else:
                code = r["aggregation_code"]
            out[(r["aggregation_level"], code, r["ascension_code"])] = (
                float(r["pct_raw"]), float(r["pct_corrected"]))
    return out

def main():
    items = load_items()
    exp, missing = export_counts(items)
    if missing:
        print("WARN unmatched export columns:", missing)
    cmp = load_compare()
    # composite membership
    comp_items = defaultdict(list)
    for col, m in items.items():
        comp_items[m["composite"]].append(col)
    COMP_CODE = {"Teamwork": "TW", "Staffing and Work Pace": "Staffing",
        "Organizational Learning-Continuous Improvement": "OL", "Response to Error": "NPRE",
        "Supervisor/Manager/Clinical Leader Support": "S/ME", "Communication About Error": "FCE",
        "Communication Openness": "CO", "Hospital Management Support for Patient Safety": "MSPS",
        "Handoffs and Information Exchange": "HT"}

    out = open(os.path.join(REPO, "data/chain_of_custody.csv"), "w", newline="")
    w = csv.writer(out)
    w.writerow(["ascension_code", "level", "code", "name", "polarity",
                "export_pct", "as_submitted_pct", "corrected_pct",
                "export_eq_submitted", "submitted_vs_corrected_delta"])
    def emit(bu, level, code, name, pol, exp_pct):
        key = (level, code, bu)
        sub, corr = cmp.get(key, (None, None))
        eq = "" if (exp_pct is None or sub is None) else ("yes" if abs(exp_pct-sub) <= 1.0 else "NO")
        delta = "" if (sub is None or corr is None) else round(corr-sub, 1)
        w.writerow([bu, level, code, name, pol,
                    "" if exp_pct is None else round(exp_pct, 1),
                    "" if sub is None else round(sub, 1),
                    "" if corr is None else round(corr, 1), eq, delta])
    for bu in BUS:
        # questions
        for col, m in items.items():
            emit(bu, "question", col, m["text"], "neg" if m["neg"] else "pos",
                 pct(exp[bu][col], m["neg"]))
        # composites (item-averaged export)
        for comp, cols in comp_items.items():
            if comp not in COMP_CODE:
                continue
            vals = [pct(exp[bu][c], items[c]["neg"]) for c in cols]
            vals = [v for v in vals if v is not None]
            cexp = sum(vals)/len(vals) if vals else None
            emit(bu, "composite", COMP_CODE[comp], comp, "", cexp)
    out.close()
    print("Wrote data/chain_of_custody.csv")
    # quick QC: how many items have export != submitted?
    import collections
    rows = list(csv.DictReader(open(os.path.join(REPO, "data/chain_of_custody.csv"))))
    ne = [r for r in rows if r["export_eq_submitted"] == "NO"]
    print(f"rows={len(rows)}  export!=submitted: {len(ne)}")
    print("sample 52005 questions:")
    for r in rows:
        if r["ascension_code"] == "52005" and r["level"] == "question" and r["code"] in ("A1", "A3", "B2", "F3"):
            print(f"  {r['code']:4}{r['polarity']:>4}  exp={r['export_pct']:>5}  subm={r['as_submitted_pct']:>5}  corr={r['corrected_pct']:>5}  eq={r['export_eq_submitted']}")

if __name__ == "__main__":
    main()
