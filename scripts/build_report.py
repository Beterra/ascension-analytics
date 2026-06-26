#!/usr/bin/env python3
"""
Build the Ascension AHCA HSOPS data-reconciliation report (.docx) by injecting a
data-driven body into the unpacked Beterra brand template (preserving all brand
styles, header/footer, page setup).

The brand template (reports/brand_template.docx) is a body-emptied shell derived
from the live DRAFT — regenerate it from a current DRAFT with scripts/make_brand_template.py.

Numbers come from the OFFICIAL BigQuery export data/compare_corrected_vs_raw.csv
(facility rows = resubmission scope; system rows used only for the supplementary
section, filtered to the clean 2.0 rows where n_corrected == n_raw).
Scoping inventory from data/item_reference.csv. Reverse-item distribution
exhibit from data/reverse_item_distributions.csv.

Run inside the workspace VM:  python3 scripts/build_report.py
Produces: reports/Ascension AHCA HSOPS Data Reconciliation (generated).docx
"""
import csv, glob, os, subprocess, shutil
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = "/sessions/determined-funny-goodall/mnt/.claude/skills/docx"
TEMPLATE = os.path.join(REPO, "reports/brand_template.docx")
# NOTE: the builder writes to a SEPARATE "(generated)" file so it never overwrites
# the working DRAFT that Jeff is hand-editing. Your edited DRAFT is the live document;
# the generated file is only a from-scratch reference to diff/merge against.
OUT = os.path.join(REPO, "reports/Ascension AHCA HSOPS Data Reconciliation (generated).docx")
WORK = "/tmp/report_build"

COMPOSITE_ORDER = ["TW", "Staffing", "OL", "NPRE", "S/ME", "CO", "FCE", "MSPS", "HT", "RPSE"]
UNAFFECTED = {"FCE", "RPSE"}          # contain no reverse-worded items
MINIMAL = {"MSPS"}                    # one reverse item (F03); small/mixed movement

# ---------- escaping ----------
def esc(s):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace("'", "&#x2019;").replace('"', "&#x201D;")

# ---------- XML blocks ----------
def run(text, b=False, i=False):
    rpr = ""
    if b or i:
        rpr = "<w:rPr>" + ("<w:b/><w:bCs/>" if b else "") + ("<w:i/><w:iCs/>" if i else "") + "</w:rPr>"
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{esc(text)}</w:t></w:r>"

def para(runs, style=None):
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    if isinstance(runs, str):
        runs = [run(runs)]
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"

def eyebrow(t): return para(t, "Eyebrow")
def h1(t):      return para(t, "Heading1")
def h2(t):      return para(t, "Heading2")
def body(*r):   return para(list(r))
def caption(t): return para(t, "Caption")
def emphasis(t):return para(t, "BodyEmphasis")
def pagebreak():return '<w:p><w:pPr><w:pageBreakBefore/></w:pPr></w:p>'

IMG = os.path.join(REPO, "figures/process_map.png")
def image_para(cx=5943600, cy=2447000):  # EMU; ~6.5in wide, aspect of 1433x590
    return ('<w:p><w:pPr><w:spacing w:before="120" w:after="40"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
      '<wp:inline distT="0" distB="0" distL="0" distR="0">'
      f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
      '<wp:docPr id="101" name="ProcessMap"/>'
      '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
      '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
      '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
      '<pic:nvPicPr><pic:cNvPr id="101" name="ProcessMap"/><pic:cNvPicPr/></pic:nvPicPr>'
      '<pic:blipFill><a:blip r:embed="rIdProcMap"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
      f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
      '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

def callout(title, text):
    return ('<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/>'
      '<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
      '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders>'
      '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
      '<w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid><w:tr><w:tc><w:tcPr><w:tcW w:w="9360" w:type="dxa"/>'
      '<w:tcBorders><w:top w:val="none" w:sz="0" w:space="0" w:color="FFFFFF"/><w:left w:val="none" w:sz="0" w:space="0" w:color="FFFFFF"/>'
      '<w:bottom w:val="none" w:sz="0" w:space="0" w:color="FFFFFF"/><w:right w:val="none" w:sz="0" w:space="0" w:color="FFFFFF"/></w:tcBorders>'
      '<w:shd w:val="clear" w:color="auto" w:fill="49B19A"/>'
      '<w:tcMar><w:top w:w="240" w:type="dxa"/><w:left w:w="360" w:type="dxa"/><w:bottom w:w="240" w:type="dxa"/><w:right w:w="360" w:type="dxa"/></w:tcMar></w:tcPr>'
      f'<w:p><w:pPr><w:spacing w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:bCs/><w:caps/><w:color w:val="ADE2B6"/><w:spacing w:val="60"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr><w:t>{esc(title)}</w:t></w:r></w:p>'
      f'<w:p><w:pPr><w:pStyle w:val="CalloutText"/></w:pPr><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'
      '</w:tc></w:tr></w:tbl><w:p/>')

def cell(text, w, fill=None, bold=False, align=None):
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    jc = f'<w:jc w:val="{align}"/>' if align else ""
    bd = ('<w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/><w:left w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/>'
          '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/><w:right w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/></w:tcBorders>')
    rpr = "<w:rPr><w:b/><w:bCs/></w:rPr>" if bold else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{bd}{shd}'
            '<w:tcMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0"/>{jc}</w:pPr><w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p></w:tc>')

def table(widths, header, rows, header_fill="49B19A"):
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
           '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
           f'<w:tblGrid>{grid}</w:tblGrid>']
    out.append('<w:tr>' + "".join(cell(h, w, fill=header_fill, bold=True, align=("center" if i else None)) for i, (h, w) in enumerate(zip(header, widths))) + '</w:tr>')
    for r in rows:
        out.append('<w:tr>' + "".join(cell(v, w, align=("center" if i else None)) for i, (v, w) in enumerate(zip(r, widths))) + '</w:tr>')
    out.append('</w:tbl><w:p/>')
    return "".join(out)

# ---------- data ----------
def find(name_glob):
    hits = glob.glob(os.path.join(REPO, "data", name_glob))
    return hits[0] if hits else None

def load_compare():
    """returns rows list of dicts from the official export (handles the typo filename)."""
    path = find("compare_corr*_vs_raw.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def load_items():
    rows = []
    with open(os.path.join(REPO, "data/item_reference.csv"), newline="") as f:
        for r in csv.DictReader(f):
            r["rev"] = r["reverse_scored"].strip().upper() == "TRUE"
            rows.append(r)
    return rows

def facilities():
    import json
    with open(os.path.join(REPO, "surveys.json")) as f:
        return [(e["ascension_code"], e["name"], e["region"]) for e in json.load(f) if e.get("level") == "Facility"]

def comp_name(code):
    return {"TW": "Teamwork", "Staffing": "Staffing and Work Pace",
            "OL": "Organizational Learning – Continuous Improvement", "NPRE": "Response to Error",
            "S/ME": "Supervisor / Manager Support", "CO": "Communication Openness",
            "FCE": "Communication About Error", "MSPS": "Hospital Management Support",
            "HT": "Handoffs and Information Exchange", "RPSE": "Reporting Patient Safety Events"}[code]

def f(x):  # 1-dp string
    return f"{float(x):.1f}"

def build_body():
    cmp_rows = load_compare()
    items = load_items()
    facs = facilities()
    fac_codes = {c for c, _, _ in facs}

    # facility composites: comp[ascension_code][agg_code] = (corr, raw, delta, n)
    comp = defaultdict(dict)
    for r in cmp_rows:
        if r["aggregation_level"] != "composite" or r["ascension_code"] not in fac_codes:
            continue
        comp[r["ascension_code"]][r["aggregation_code"]] = (
            float(r["pct_corrected"]), float(r["pct_raw"]), float(r["delta_pts"]), int(float(r["n_corrected"])))

    # per-facility overall = response-weighted mean across composites
    def overall(code):
        cc = comp[code]
        num_c = sum(v[0]*v[3] for v in cc.values()); num_r = sum(v[1]*v[3] for v in cc.values())
        den = sum(v[3] for v in cc.values())
        return (num_c/den, num_r/den)

    # composite pattern across all 8 (response-weighted)
    agg = {}
    for code in COMPOSITE_ORDER:
        nc = sum(comp[c][code][0]*comp[c][code][3] for c, _, _ in facs if code in comp[c])
        nr = sum(comp[c][code][1]*comp[c][code][3] for c, _, _ in facs if code in comp[c])
        d = sum(comp[c][code][3] for c, _, _ in facs if code in comp[c])
        agg[code] = (nc/d, nr/d) if d else (0, 0)

    # scoping (composite -> #items, #reverse) from item_reference
    scop = defaultdict(lambda: {"n": 0, "rev": 0})
    code_by_comp = {"Teamwork": "TW", "Staffing and Work Pace": "Staffing",
        "Organizational Learning-Continuous Improvement": "OL", "Response to Error": "NPRE",
        "Supervisor/Manager/Clinical Leader Support": "S/ME", "Communication About Error": "FCE",
        "Communication Openness": "CO", "Hospital Management Support for Patient Safety": "MSPS",
        "Handoffs and Information Exchange": "HT", "Reporting Patient Safety Events": "RPSE"}
    revs = []
    for r in items:
        if r["scale_type"] not in ("agree5", "freq5"):
            continue
        code = code_by_comp.get(r["composite"])
        if not code:
            continue
        scop[code]["n"] += 1
        if r["rev"]:
            scop[code]["rev"] += 1
            revs.append(r)

    # B2 response distribution — OFFICIAL, from BigQuery response_breakdown (corrected
    # survey_ids 3434-3441). LITERAL responses: staff overwhelmingly DISAGREE (1-2)
    # that the supervisor pushes shortcuts (the favorable answer). The submitted/raw
    # version is the exact 6-x inverse (validated 100%), so it is the reverse.
    b2_counts = {1: 1072, 2: 1753, 3: 534, 4: 196, 5: 116}
    b2_tot = sum(b2_counts.values())
    b2_corr = [round(100 * b2_counts[k] / b2_tot, 1) for k in (1, 2, 3, 4, 5)]
    b2_subm = b2_corr[::-1]

    P = []
    # ---- Title block ----
    P.append(eyebrow("AHCA Culture of Safety — Data Revalidation"))
    P.append(para("Patient Safety Culture Survey: Submission Data Review", "Title"))
    P.append(para("Identifying and correcting a reverse-worded scoring error in Ascension Florida’s 2024 AHCA hospital submission", "Subtitle"))
    P.append('<w:p><w:r><w:br/></w:r></w:p>')
    for label, val in [("Prepared by", "Beterra"), ("Date", "June 2026"), ("For", "Ascension Florida Leadership")]:
        P.append('<w:p><w:pPr><w:spacing w:after="60"/></w:pPr>'
                 f'<w:r><w:rPr><w:caps/><w:color w:val="6B7280"/><w:spacing w:val="40"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr><w:t xml:space="preserve">{label}  </w:t></w:r>'
                 f'<w:r><w:rPr><w:b/><w:bCs/></w:rPr><w:t>{esc(val)}</w:t></w:r></w:p>')
    P.append(pagebreak())

    # ---- 1 Executive summary ----
    P.append(eyebrow("Section 1"))
    P.append(h1("Executive summary"))
    P.append(body(run("In September 2024, Ascension Florida fielded the AHRQ Survey on Patient Safety Culture (Hospital version) across eight hospitals and submitted the results to the Agency for Health Care Administration (AHCA). During revalidation, Beterra identified that a defined set of negatively-worded (“reverse-worded”) questions had their responses inverted at the response level before scoring.")))
    P.append(body(run("AHCA scoring counts a 4 or 5 (Agree / Strongly Agree) as positive for every question. Inverting the responses to negatively-worded questions therefore distorts exactly the composite measures that contain them — depressing Staffing and Work Pace, Response to Error, Handoffs, and related measures — while leaving every composite without a reverse-worded question unchanged.")))
    P.append(body(run("This review is scoped to the eight hospitals, which is the level at which data is submitted to AHCA. It documents, from the ground up, how the data moved from collection to submission, which questions are affected and why, and the difference between the figures as originally submitted and the corrected results. An Ascension Florida system roll-up is included as supplementary context.")))
    P.append(callout("Key takeaway", "Thirteen negatively-worded questions were inverted before scoring. Correcting them changes only the composites that contain those questions; measures with no reverse-worded questions are identical in both versions, confirming the rest of the data is sound."))

    # ---- 2 Background ----
    P.append(eyebrow("Section 2"))
    P.append(h1("Background and scope"))
    P.append(body(run("The review covers eight Ascension Florida hospitals in two regions. "),
                  run("Sacred Heart West:", b=True), run(" Pensacola, Gulf, Emerald Coast, and Bay. "),
                  run("Jacksonville East:", b=True), run(" St. Vincent’s Southside (St. Luke’s), Riverside (St. Vincent’s Medical Center), Clay County, and St. John’s County.")))
    P.append(body(run("The instrument is the AHRQ Survey on Patient Safety Culture (SOPS), Hospital version, administered by the prior survey vendor and entered into AHCA’s Hospital Survey data-entry tool. Only the hospital surveys were required for the AHCA submission; other care settings are out of scope.")))

    # ---- 3 Scoping ----
    P.append(eyebrow("Section 3"))
    P.append(h1("How the survey is scored"))
    P.append(body(run("Each scored question uses a five-point scale. AHCA reports each result as a "), run("percent positive", b=True),
                  run(" — the share of responses that are 4 or 5, with neutral responses counted in the denominator. The same rule applies to every question.")))
    P.append(body(run("Most questions are "), run("positively worded", b=True),
                  run(" (“we work together as an effective team”) — agreement is good. Thirteen are "), run("negatively worded", b=True),
                  run(" (“staff feel like their mistakes are held against them”) — agreement is bad. For the uniform 4/5-is-positive rule to score these correctly, the response must be stored in the correct (reversed) orientation. Inverting a negatively-worded response a second time makes the score count backwards.")))
    P.append(h2("Composites and where the reverse-worded questions sit"))
    P.append(body(run("The scored questions roll up into ten composites. The table shows how many questions each contains and how many are reverse-worded — which determines whether the error can affect it.")))
    rows = []
    for code in COMPOSITE_ORDER:
        s = scop[code]
        aff = "No — unaffected" if s["rev"] == 0 else ("Minimal (1 of %d)" % s["n"] if code in MINIMAL else "Yes")
        rows.append([comp_name(code), str(s["n"]), str(s["rev"]), aff])
    P.append(table([4360, 1400, 1800, 1800], ["Composite", "Questions", "Reverse-worded", "Affected?"], rows))
    P.append(caption("Table 1.  Communication About Error and Reporting Patient Safety Events contain no reverse-worded questions and are unaffected."))
    P.append(h2("The thirteen reverse-worded questions"))
    rrows = [[r["ahca_col"], comp_name(code_by_comp[r["composite"]]), r["item_text"]] for r in revs]
    P.append(table([900, 2600, 5860], ["Item", "Composite", "Question wording"], rrows))

    # ---- 4 Process ----
    P.append(eyebrow("Section 4"))
    P.append(h1("How the data moved — and where it diverged"))
    P.append(body(run("The survey data passed through four points. "),
                  run("Perceptyx survey and reporting:", b=True), run(" the vendor collected the responses and reported results "), run("correctly", b=True), run(". "),
                  run("Perceptyx data export:", b=True), run(" the vendor’s raw data file, however, normalized the thirteen reverse-worded items — storing them pre-inverted so that a uniform 4/5-is-positive rule scores them correctly inside the vendor’s own system. "),
                  run("AHCA data-entry tool:", b=True), run(" Ascension loaded that export into AHCA’s macro-enabled Excel tool, which applies standard reverse-scoring and so expects un-normalized responses — it did not account for the vendor’s normalization. "),
                  run("Submission:", b=True), run(" the tool produced the per-facility files for AHCA’s system with the reverse-worded items still normalized, so AHCA’s scoring counted them backwards.")))
    P.append(image_para())
    P.append(caption("Figure 1.  The data chain. The error originates in the Perceptyx export (reverse-worded items normalized) and is carried unchanged through the AHCA tool into the submission; the correction undoes the normalization."))
    P.append(body(run("The table traces a control question (A1, positively worded) and a reverse-worded question (A3) through these points, pooled across all eight hospitals. The reverse-worded value is "),
                  run("identical from the Perceptyx export through the AHCA submission", b=True),
                  run(" — the tool passed it through unchanged — and moves only when the normalization is undone in the corrected data. The control question is stable everywhere.")))
    P.append(table([3960, 2700, 2700], ["Stage", "A1 — control (% positive)", "A3 — reverse-worded (% positive)"],
        [["Perceptyx source export", "88.5%", "20.8%"],
         ["AHCA tool submission (as submitted)", "88.5%", "20.8%"],
         ["Corrected (literal responses)", "88.5%", "50.8%"]]))
    P.append(caption("Table 2.  Chain of custody, pooled across eight hospitals. The reverse-worded item is unchanged from export to submission and diverges only when the normalization is reversed; the control item is stable throughout."))
    P.append(body(run("Perceptyx’s own facility reports corroborate this: for Sacred Heart Emerald Coast the vendor report shows Teamwork 88.6% and “staff work longer hours than is best for patient care” at 53.4% — matching the "),
                  run("corrected", b=True),
                  run(" figures, not the submitted ones. Perceptyx analyzed the data correctly; the error entered at the export-to-AHCA-tool handoff and was never reversed before submission.")))

    # ---- 5 The defect ----
    P.append(eyebrow("Section 5"))
    P.append(h1("The defect and how we confirmed it"))
    P.append(body(run("For each of the thirteen reverse-worded questions, every response was replaced by its inverse on the 1–5 scale (a 1 became a 5, a 2 a 4, and so on). Comparing the affected and corrected datasets respondent-by-respondent, the inversion is exact and complete: across more than 3,800 matched respondents, 100% of non-neutral responses to these thirteen questions are inverted, with no exceptions, and no other questions are touched.")))
    P.append(body(run("The clearest illustration is a single question’s response distribution. On item B2 (“my supervisor wants us to work faster … even if it means taking shortcuts”), staff overwhelmingly "),
                  run("disagreed", b=True),
                  run(" (responses 1–2) — the favorable answer. In the submitted data these responses were inverted to agreement (4–5), an exact mirror image (scale: 1 = Strongly Disagree, 5 = Strongly Agree):")))
    P.append(table([3120, 1248, 1248, 1248, 1248, 1248],
        ["Response distribution (B2)", "1", "2", "3", "4", "5"],
        [["Corrected (as answered)"] + [f(x)+"%" for x in b2_corr],
         ["As submitted (inverted)"] + [f(x)+"%" for x in b2_subm]]))
    P.append(caption("Table 3.  Corrected percentages are the literal responses from the analytics system (response_breakdown, survey_ids 3434–3441); the submitted distribution is their exact 1↔5 / 2↔4 inversion — the signature of a response-level flip."))

    # ---- 6 Impact (facility) ----
    P.append(eyebrow("Section 6"))
    P.append(h1("Impact: corrected versus submitted results"))
    P.append(body(run("The table below shows each hospital’s overall percent positive as submitted versus corrected. All figures are the official scored values from the analytics system.")))
    snap = []
    for code, name, region in facs:
        oc, orr = overall(code)
        snap.append([name, f(oc)+"%", f(orr)+"%", f"{oc-orr:+.1f}"])
    P.append(table([4360, 1666, 1667, 1667], ["Hospital", "Corrected", "As submitted", "Change"], snap))
    P.append(caption("Table 4.  Overall percent positive by hospital (response-weighted across composites)."))
    P.append(h2("Where the change concentrates"))
    P.append(body(run("Across all eight hospitals, the gap falls entirely on composites containing reverse-worded questions. Communication About Error and Reporting Patient Safety Events do not move; Hospital Management Support moves only slightly (it has a single reverse-worded question).")))
    crows = []
    for code in COMPOSITE_ORDER:
        oc, orr = agg[code]
        tag = comp_name(code) + (" (unaffected)" if code in UNAFFECTED else (" (minimal)" if code in MINIMAL else ""))
        crows.append([tag, f(oc)+"%", f(orr)+"%", f"{oc-orr:+.1f}"])
    P.append(table([4360, 1666, 1667, 1667], ["Composite (all hospitals)", "Corrected", "As submitted", "Change"], crows))
    P.append(caption("Table 5.  Composite percent positive across all eight hospitals (response-weighted). Per-hospital detail is in data/compare_corrected_vs_raw.csv."))

    # ---- 7 Supplementary system ----
    sysrows = [r for r in cmp_rows if r["ascension_code"] == "SYSTEM" and r["aggregation_level"] == "composite"
               and r["n_corrected"] == r["n_raw"] and int(float(r["n_corrected"])) > 1000]
    P.append(eyebrow("Section 7 — Supplementary"))
    P.append(h1("Ascension Florida system roll-up"))
    P.append(body(run("Provided as additional context (not part of the facility-level resubmission), the system roll-up shows the same pattern at the aggregate level.")))
    if sysrows:
        seen = {}
        for r in sysrows:
            seen[r["aggregation_code"]] = r
        srows = []
        for code in COMPOSITE_ORDER:
            if code in seen:
                r = seen[code]
                srows.append([comp_name(code), f(r["pct_corrected"])+"%", f(r["pct_raw"])+"%", f"{float(r['delta_pts']):+.1f}"])
        P.append(table([4360, 1666, 1667, 1667], ["Composite (system)", "Corrected", "As submitted", "Change"], srows))
        P.append(caption("Table 6.  Ascension Florida system composite percent positive (supplementary)."))

    # ---- 8 Conclusion ----
    P.append(eyebrow("Section 8"))
    P.append(h1("Conclusion and next steps"))
    P.append(body(run("The submitted figures understate patient safety culture at the affected composites because of a response-level inversion of thirteen negatively-worded questions — introduced in the Perceptyx export and not reversed by the AHCA data-entry tool. The corrected, validated results are ready for resubmission at the facility level.")))
    P.append(h2("Next steps"))
    P.append(body(run("AHCA resubmission — ", b=True), run("corrected facility files are validated and ready; target submission date "), run("[to be confirmed]", i=True), run(".")))
    P.append(body(run("Leadership communication — ", b=True), run("executive / CEO memo summarizing the issue and remediation; audience and timing "), run("[to be confirmed]", i=True), run(".")))
    P.append(body(run("Recurrence prevention — ", b=True), run("confirm the reverse-worded normalization convention with the vendor and in the AHCA tool workflow "), run("[to be confirmed]", i=True), run(".")))
    P.append(body(run("Owner and timeline — ", b=True), run("responsible party and key dates "), run("[to be confirmed]", i=True), run(".")))
    P.append(callout("Placeholder — to finalize", "Confirm the four items above (resubmission date, leadership communication, recurrence-prevention step, and owner/timeline) before this report is issued."))
    return "".join(P)

def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    subprocess.run(["python3", f"{SKILL}/scripts/office/unpack.py", TEMPLATE, f"{WORK}/unpacked"], check=True)
    # Strip the template's stale attachedTemplate link (points to an absent .dotx).
    import re
    rels = f"{WORK}/unpacked/word/_rels/settings.xml.rels"
    if os.path.exists(rels):
        t = open(rels, encoding="utf-8").read()
        t = re.sub(r'<Relationship\b[^>]*attachedTemplate[^>]*/>', '', t)
        t = re.sub(r'<Relationship\b[^>]*\.dotx[^>]*/>', '', t)
        open(rels, "w", encoding="utf-8").write(t)
    setp = f"{WORK}/unpacked/word/settings.xml"
    if os.path.exists(setp):
        t = open(setp, encoding="utf-8").read()
        t = re.sub(r'<w:attachedTemplate\b[^>]*/>', '', t)
        open(setp, "w", encoding="utf-8").write(t)

    # Embed the process-map image: copy into media, register content type + relationship.
    media = f"{WORK}/unpacked/word/media"
    os.makedirs(media, exist_ok=True)
    shutil.copy(IMG, f"{media}/process_map.png")
    ct = f"{WORK}/unpacked/[Content_Types].xml"
    t = open(ct, encoding="utf-8").read()
    if 'Extension="png"' not in t:
        t = t.replace("</Types>", '<Default Extension="png" ContentType="image/png"/></Types>')
        open(ct, "w", encoding="utf-8").write(t)
    drels = f"{WORK}/unpacked/word/_rels/document.xml.rels"
    t = open(drels, encoding="utf-8").read()
    if "rIdProcMap" not in t:
        t = t.replace("</Relationships>",
                      '<Relationship Id="rIdProcMap" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/process_map.png"/></Relationships>')
        open(drels, "w", encoding="utf-8").write(t)

    docpath = f"{WORK}/unpacked/word/document.xml"
    xml = open(docpath, encoding="utf-8").read()
    pre = xml.split("<w:body>")[0] + "<w:body>"
    sect = "<w:sectPr" + xml.split("<w:sectPr", 1)[1]
    open(docpath, "w", encoding="utf-8").write(pre + build_body() + sect)
    subprocess.run(["python3", f"{SKILL}/scripts/office/pack.py", f"{WORK}/unpacked", OUT, "--original", TEMPLATE], check=True)
    print("Wrote", OUT)

if __name__ == "__main__":
    main()
