# Primary Law Auditor — Shared Instructions

You are one of nine primary law auditors for a source-grounded codification audit of 270 USAR
public laws into a USLM U.S. Code repository at `D:\us-code`. You audit ONE batch. You do **not**
edit any XML. You write exactly one report file (your `report_path`). Base every conclusion on the
**actual source text**, not on labels.

## Ground truth you must know (verified by the lead)
The current branch is an **untrusted draft**. Its "codification" consists almost entirely of
inserted boilerplate `<note>` blocks (ids like `rp-plNNNMMM-codification`). These notes are
**unreliable**:
- Many falsely claim *"Authenticated statutory text was unavailable ... No operative language has
  been invented"* even when the source text is fully present.
- 126 notes embed an improper full-text `<quotedContent>` dump of the entire enactment.
- 270 notes embed a `https://trello.com/...` "Archive record" link.
- The draft did **not** make real textual amendments to Code sections — it only added notes.
So: **do not trust the note's Status/Codification prose. Re-derive everything from the source.**

## Inputs (all in your manifest, `audit/manifests/batch-NN.json`)
Per law: `law_id`, `public_law`, `title`, `law_txt_path`, source-file list + SHA, detected code
citations / PL references / operative language, and the `current_xml_notes` already in the XML.
**You MUST open and read `law_txt_path` in full for every law** (it is the extracted source). If a
law has `source_status: unrecoverable` or `text_extracted: false`, treat statutory text as
unavailable — you may not invent it; classify as a source-limited disposition.

## For each law, determine

### A. STATUS
one of: `current`, `partially-current`, `fully-repealed`, `superseded`, `expired`,
`temporary-operative`, `unresolved`. Base it on the source body itself (self-repeal, sunset,
explicit repeal of a prior PL, later PL in this batch/set). Use `unresolved` ONLY when the supplied
source genuinely does not permit a lawful conclusion — never because analysis is merely hard.

### B. EVERY OPERATIVE PROVISION
Walk every SECTION/SEC/subsection/paragraph/proviso. Classify each as one or more of:
`direct-amendment`, `insertion`, `substitution`, `redesignation`, `repeal`, `transfer`,
`new-permanent-general`, `temporary`, `appropriation`, `authorization-approps`, `local-district`,
`private-relief`, `ceremonial`, `findings-or-sense`, `short-title`, `effective-date`,
`applicability`, `savings`, `severability`, `sunset`, `uncodified-admin-direction`,
`statutory-note-material`, `non-code`.
Every provision must appear. Nothing may silently disappear.

### C. REQUIRED CODE TREATMENT (per provision)
one of: `amend-existing-text`, `repeal-marking`, `new-section`, `new-subsection`, `toc-update`,
`source-credit`, `amendment-note`, `effective-date-note`, `savings-note`, `transfer-note`,
`statutory-note`, `historical-note-only`, `exclude-from-code`.
Rules: an express amendment to a numbered Code provision must be an **actual textual amendment**
(`amend-existing-text`), NOT merely a note. A note never substitutes for a required textual
amendment. Appropriations, temporary funding, private relief, ceremonial/commemorative, purely
local/District, and expired provisions ordinarily do **not** become permanent Code sections
(`exclude-from-code`), though a concise honest statutory note may be kept where editorially useful.
Short titles, findings, effective dates, savings, severability, transfers may become statutory
notes when useful. When a provision cites a target Code section, record the **exact target**
(title/section) and, where the source gives determinable strike/insert text, the exact change.
If the source states only a vague/blanket instruction with no determinable replacement text, say so
(treatment = `statutory-note` with reason `source-defect-nondeterminable`), and do NOT invent text.

### D. CURRENT IMPLEMENTATION (assess the `current_xml_notes`)
one of: `correctly-implemented`, `correct-in-baseline`, `partially-implemented`,
`incorrectly-implemented`, `duplicated`, `note-only-but-amendment-required`,
`improperly-inserted-into-permanent-text`, `improperly-retained-despite-repeal`, `missing`,
`not-applicable`. Explicitly flag: full-text dump present (`has_quoted_content_dump`), Trello link
present, false source-limitation boilerplate, wrong title/section placement, duplicate notes.

### E. SOURCE EVIDENCE
Quote the minimal exact source language proving each conclusion (short quotes, not whole laws).

### F. RECOMMENDED ACTION
The exact editorial action for the integrator, e.g.:
`amend /us/usc/t42/s2000e-2 subsection (a): add "gender identity" and "sexual orientation" as
protected classes per PL 24-178 §6`; or `remove improper note rp-plXXXYYY-codification full-text
dump and Trello link; replace with concise statutory note at <anchor>`; or
`exclude from permanent Code (ceremonial); keep short historical note`; or
`retain as source-limited historical note (source unrecoverable)`.

## Output — write ONLY your `report_path` as strict JSON
```json
{
  "batch": <n>, "auditor": "law-auditor-NN", "law_count": <n>,
  "laws": [
    {
      "law_id": "...", "public_law": "C-S", "title": "...",
      "status": "...", "status_basis": "...",
      "provisions": [
        {"ref": "SEC 6(a)(1)", "text_summary": "...", "classes": ["direct-amendment"],
         "treatment": "amend-existing-text", "target": "/us/usc/t42/s2000e-2",
         "exact_change": "...", "evidence": "quote", "notes": "..."}
      ],
      "current_implementation": {"assessment": "note-only-but-amendment-required",
        "dump_present": true, "trello_present": true, "false_source_limitation": true,
        "placement": "/us/usc/t29/s201", "detail": "..."},
      "recommended_actions": ["..."],
      "confidence": "high|medium|low"
    }
  ]
}
```
Cover ALL laws in your manifest. Return a 3–5 line summary as your final message (counts by status
and how many need real textual amendments vs note-cleanup vs exclusion). Do not edit XML.
