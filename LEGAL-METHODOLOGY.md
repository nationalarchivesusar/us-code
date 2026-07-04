# Legal and Editorial Methodology

## I. Governing objective

The objective is not merely to display the text of a Trello card. It is to
produce a usable, consolidated USAR U.S. Code in which current general and
permanent law is placed at the location a Code reader would reasonably expect,
while enactments that do not belong in the Code remain available through the
public-law archive and codification record.

The package therefore distinguishes between:

- **enactment**: the complete public law as enacted;
- **Code text**: operative language consolidated into an existing or new Code
  section;
- **statutory note**: general and permanent or continuing law associated with a
  Code subject but not assigned a positive-law section by Congress;
- **non-Code law**: valid enactment that is temporary, one-time, constitutional,
  private, appropriational, commemorative, or otherwise unsuitable for the
  general and permanent Code;
- **nonoperative history**: repealed, expired, failed, rescinded, or superseded
  material that must not be presented as current law.

## II. Canonical Trello inventory

The board export is normalized into one canonical record per public-law number.
Duplicate cards are retained in the audit record. Canonical selection prefers:

1. a card labeled or listed as active;
2. a card with an enactment attachment;
3. a card with a substantial description;
4. the most recently active card.

Attachment links and substantial pasted descriptions from duplicate cards are
pooled so an active card can still use a source retained on an older archive
record. A stale duplicate cannot override an active record merely because it was
edited more recently; it can only supply source evidence for the canonical law.

## III. Source authentication

Source candidates include Trello uploads, Google Documents, Google Drive files,
links in the card description, and the card description itself. Candidate
selection scores:

- an exact public-law number;
- law-title words;
- enactment formulae such as “Be it enacted”;
- document labels such as signed, enrolled, or final;
- readable length and lexical variety;
- absence of login, access-denied, or JavaScript error pages.

The selected normalized text receives a SHA-256 hash. All candidate URLs,
failures, and scores remain in the per-law source record. The pipeline never
uses a blank title or empty source as authority to alter the Code.

## IV. Current-law reconciliation

Before analyzing remaining cards, the pipeline scans every existing title for
project-generated `rp-` elements and their primary public-law references. A law
already found there is classified `ALREADY_INCORPORATED`; it is not inserted a
second time. Only the first primary citation in a project-generated element is
used for this determination, so a replacement Act's historical discussion of an
older repealed law does not falsely classify the older law as incorporated. This
avoids relying solely on a local state file that may have been deleted, ignored,
or moved between machines.

## V. Dependency and repeal analysis

Every enactment is searched for references to other public laws. Context around
each reference determines whether the later law:

- repeals;
- supersedes or replaces;
- amends;
- overrides notwithstanding language; or
- merely references the earlier law.

A later express repeal or supersession prevents an earlier, not-yet-incorporated
law from being inserted. If the earlier law is already incorporated, the report
flags a reversal audit rather than silently deleting consolidated text that may
also contain later amendments.

## VI. Direct Code amendments

Direct Code text is preferred when Congress supplies a uniquely executable
instruction.

### A. Strike and insert

A strike-and-insert operation is executed only when:

1. the enactment names the title and section;
2. the target section exists;
3. both the struck and inserted language are recoverable;
4. the struck phrase occurs exactly once in the target element.

If uniqueness cannot be established, the exact instruction is published as a
controlling amendment note at the target section and the report explains why
textual consolidation was withheld.

### B. Complete restatement

A section is restated only when the enactment says that the identified section
“is amended to read as follows” and supplies a substantial replacement block.
The section identifier and preexisting editorial notes are preserved. A new
source credit and amendment note identify the USAR law and source hash.

### C. Repeal

An existing section is changed to a repealed placeholder only upon an express
repeal instruction naming that title and section. Historical notes are retained.

### D. New section

A new section is created only when the enactment expressly directs that a named
chapter of a named U.S. Code title be amended by adding a numbered section. The
operation also adds a chapter table-of-sections entry. Internal bill section
numbers, standing alone, are never treated as U.S. Code section numbers.

### E. Added subsections and structurally ambiguous language

Flat PDF or DOCX extraction often cannot prove the intended USLM nesting of an
added subsection, paragraph, or subparagraph. The package does not guess at that
hierarchy. It publishes the target-specific amendment as a note unless the
operation is structurally unambiguous.

## VII. Statutory notes

A freestanding law is treated as a statutory note when it creates continuing
rights, duties, prohibitions, offices, procedures, remedies, or jurisdiction but
does not assign itself to a Code section. The complete authenticated text is
included, not an AI paraphrase.

Placement priority is:

1. an expressly cited existing Code section;
2. the most frequently cited existing section;
3. a subject-matter title selected from a published rules map;
4. the closest existing section heading within that title;
5. Title 1 only as a final general-law fallback.

The per-law memorandum identifies the subject score and selected heading so the
placement remains reviewable.

## VIII. Non-Code dispositions

The following ordinarily receive no U.S. Code insertion:

- proposed or ratified constitutional amendments;
- concrete fiscal-year or dollar appropriations;
- continuing resolutions;
- individual appointments or confirmations;
- treaty ratification resolutions;
- private relief;
- congressional medals, commendations, building names, and commemorations;
- internal rules of either House;
- single-event authorizations lacking continuing legal effect.

A non-Code disposition does not imply invalidity. It means the enactment belongs
in the public-law archive rather than the general and permanent Code.

## IX. Transaction and validation standards

Before writing:

- at least 100 active remaining laws, or all remaining laws if fewer, must have
  actionable dispositions;
- no more than ten active records may lack a source;
- no excluded card may still resemble an unparsed public law;
- every target title and section must exist unless an express new-section
  operation creates it;
- no medium- or low-confidence destructive operation is eligible for execution.

During application:

- affected title XML is staged first;
- every staged title must parse without XML recovery;
- generated IDs are deterministic;
- duplicate `rp-` IDs are prohibited;
- suspected replacement characters and common mojibake fail validation;
- live files are replaced atomically;
- repository index, encoding, applied-material, and Title 42 checks run when
  present;
- a failure restores the backed-up title and state files.

## X. Citation and Trello record

Each final card comment includes:

- a unique idempotency marker;
- final disposition;
- legal/editorial rationale;
- operation and Code location;
- public `/cite/title/section/` link;
- Trello card and enactment links;
- source SHA-256;
- repository commit SHA;
- report location.

This makes the Trello database a cross-reference to the consolidated Code while
leaving the Code itself free of package files and workbench data.
## XI. Operation register and confidence treatment

Every proposed operation is preserved in `OPERATION-REGISTER.csv`, including its
confidence, target, rationale, warnings, and execution status. High-confidence,
uniquely executable operations may change Code text. A medium- or low-confidence
strike, repeal, replacement, or new-section operation is marked as withheld and
its enactment is preserved through an appropriate statutory or amendment note.
This prevents the mass scale of the migration from lowering the legal standard
for destructive edits.

`CODE-LOCATION-REGISTER.csv` provides the reverse map from each law to its Code
identifier, public citation URL, and changed XML file. Separate registers list
non-Code, nonoperative, and previously incorporated laws so every canonical card
has an auditable destination even when no Code text changes.

## XII. State integration and repeatability

The pipeline updates the local `codification/state.json` without treating that
file as the sole source of truth. It records mass-migration results, final
dispositions, changed files, source hashes, and Code locations while preserving
existing state fields. Deterministic project IDs and primary-citation scanning
make subsequent runs idempotent: already incorporated material is verified and
reported rather than duplicated.

