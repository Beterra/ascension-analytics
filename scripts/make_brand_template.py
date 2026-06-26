#!/usr/bin/env python3
"""
Regenerate reports/brand_template.docx — the Beterra brand SHELL used by
build_report.py. It takes the current live DRAFT, empties the document body
(keeping all brand styles, theme, fonts, header/footer, logo media, and page
setup), and writes a single-section shell. build_report.py pours its generated
body into this shell.

Run:  python3 scripts/make_brand_template.py
      python3 scripts/make_brand_template.py "reports/Some Other DRAFT.docx"

If no source is given, the newest reports/*DRAFT*.docx is used.
"""
import glob, os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = "/sessions/determined-funny-goodall/mnt/.claude/skills/docx/scripts/office"
OUT = os.path.join(REPO, "reports/brand_template.docx")


def pick_draft():
    if len(sys.argv) > 1:
        return os.path.join(REPO, sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1]
    drafts = glob.glob(os.path.join(REPO, "reports", "*DRAFT*.docx"))
    drafts = [d for d in drafts if not os.path.basename(d).startswith("~$")]
    if not drafts:
        sys.exit("No reports/*DRAFT*.docx found — pass the source explicitly.")
    return max(drafts, key=os.path.getmtime)


def main():
    draft = pick_draft()
    print("source DRAFT:", os.path.relpath(draft, REPO))
    work = tempfile.mkdtemp(prefix="brand_shell_")
    src = os.path.join(work, "src.docx")
    unpacked = os.path.join(work, "unpacked")
    shutil.copy(draft, src)
    subprocess.run(["python3", f"{SKILL}/unpack.py", src, unpacked], check=True)

    docpath = os.path.join(unpacked, "word", "document.xml")
    xml = open(docpath, encoding="utf-8").read()
    head = xml.split("<w:body>")[0] + "<w:body>"
    sects = list(re.finditer(r"<w:sectPr\b.*?</w:sectPr>", xml, re.DOTALL))
    if not sects:
        sys.exit("No <w:sectPr> found in DRAFT — cannot determine page setup.")
    sect = sects[-1].group(0)  # final body-level section props (page setup + hdr/ftr refs)
    open(docpath, "w", encoding="utf-8").write(head + "<w:p/>" + sect + "</w:body></w:document>")

    subprocess.run(["python3", f"{SKILL}/pack.py", unpacked, OUT, "--original", src], check=True)
    shutil.rmtree(work, ignore_errors=True)
    print("Wrote", os.path.relpath(OUT, REPO))


if __name__ == "__main__":
    main()
