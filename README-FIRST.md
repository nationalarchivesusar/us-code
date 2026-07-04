# USAR Full-Corpus Public-Law Codification Package

This is the **mass migration package**, not another five-law batch. It reads the
entire public NARA Trello board, downloads every available enactment, identifies
duplicate and nonoperative records, reconciles the corpus against the Code that
is actually in `D:\us-code`, and produces one written codification disposition
for every canonical public-law card.

## Run the complete migration

Extract this package **outside** the Git repository, then run:

```bat
MASS_CODIFY_ALL_PUBLIC_LAWS.bat D:\us-code
```

The package tries the public Trello JSON export automatically. If Trello blocks
that endpoint on your network, open this URL in a browser and save the JSON:

```text
https://trello.com/b/IeLG19O4/nara-public-law-database.json
```

Then provide the saved file as the second argument:

```bat
MASS_CODIFY_ALL_PUBLIC_LAWS.bat D:\us-code D:\Downloads\nara-public-law-database.json
```

## What “complete” means

Every canonical board record receives exactly one final disposition:

1. `ALREADY_INCORPORATED`
2. `DIRECT_CODE_AMENDMENT`
3. `HYBRID_DIRECT_AMENDMENT_AND_STATUTORY_NOTE`
4. `STATUTORY_NOTE`
5. `NON_CODE`
6. `NONOPERATIVE_OR_REPEALED`
7. `SUPERSEDED_BEFORE_CODIFICATION`
8. `SOURCE_UNAVAILABLE`

The analyzer processes **every canonical public-law record on the board**; it is
not capped at 100. The BAT refuses to touch live XML unless at least 100 active
remaining laws—or all active remaining laws when fewer than 100 remain—receive
actionable dispositions. It also refuses application when more than ten active
laws lack a readable source or when any excluded card still looks like an
unparsed public law. Those thresholds prevent a partial board export or source
scrape from being mistaken for a finished migration.

## Codification rules

- An exact strike-and-insert instruction changes existing Code text only when
  the target phrase occurs exactly once.
- A section repeal replaces the current section with a repealed placeholder and
  source note only when the target section exists.
- A new section is created only when the law expressly names the U.S. Code title,
  chapter, and section number.
- A complete section restatement replaces that section while preserving its
  editorial notes.
- General and permanent provisions without an express positive-law destination
  become statutory notes at the closest governing Code section.
- Ambiguous direct amendments are preserved as controlling amendment notes
  rather than guessed into the wrong subsection; medium- or low-confidence
  destructive operations are recorded but never executed.
- Constitutional amendments, concrete appropriations, appointments, treaty
  ratifications, private relief, commemorations, and similar one-off measures
  are recorded as non-Code enactments.
- Repealed, failed, expired, rescinded, and superseded measures are never revived.
- A later law that expressly repeals or supersedes an unincorporated earlier law
  prevents the earlier law from being inserted.

See `LEGAL-METHODOLOGY.md` for the complete decision framework.


## Important safeguards against false completion

- Duplicate Trello cards are consolidated, but their attachments and full pasted
  descriptions remain alternate source candidates.
- Existing Code reconciliation counts only the primary public-law citation in a
  project-generated element. A later note that merely mentions an older repealed
  law does not falsely mark the older law as incorporated.
- Every board card that is excluded as “not a public law” is still written to an
  audit file. Anything resembling a law without a parseable number blocks apply.
- Exact source text, candidate scores, SHA-256 hashes, dependencies, proposed
  operations, execution status, changed files, and final public citation links are
  all retained.
- The supplied test suite includes a complete transactional run over a synthetic
  205-law corpus, rollback tests, duplicate-card source recovery, later-law
  supersession, and safeguards against whole-section repeal from subdivision text.

## Repository repairs included

The preceding five-law package replaced the repository README with local BAT
instructions and published local finalizer files. During the apply run, this
package:

- restores the original U.S. Code Library README;
- removes `FINISH_PUBLIC_LAWS.bat`, `finish_public_laws.py`, and the prior package
  checksum file from the repository;
- removes other known Round 2/Round 3 package artifacts when present;
- adds explicit ignore rules for local codification tooling.

These repairs are backed up with the title XML before they are made.

## Output

All workbench material remains under the ignored local directory:

```text
D:\us-code\codification\mass_migration\latest\
```

Important outputs:

```text
reports\MASTER-CODIFICATION-REPORT.md
reports\MASTER-INVENTORY.csv
reports\MASTER-INVENTORY.json
reports\MASTER-DASHBOARD.html
reports\SOURCE-AUDIT.csv
reports\OPERATION-REGISTER.csv
reports\CODE-LOCATION-REGISTER.csv
reports\DEPENDENCY-GRAPH.json
reports\OVERRIDES-AND-REPEALS.md
reports\NON-CODE-REGISTER.md
reports\NONOPERATIVE-REGISTER.md
reports\ALREADY-INCORPORATED-REGISTER.md
reports\DUPLICATE-CARD-REGISTER.md
reports\UNRESOLVED-REGISTER.md
reports\TRELLO-COMMENTS.md
reports\TRELLO-COMMENTS.json
reports\APPLIED-MANIFEST.json
reports\laws\PL-xxx-xxx.md
plans\PL-xxx-xxx.json
sources\records\PL-xxx-xxx.json
```

Each law memorandum records:

- card and source links;
- source SHA-256;
- active/repealed status evidence;
- subject classification;
- direct Code citations;
- amendment, repeal, and supersession dependencies;
- permanent, temporary, and non-Code scores;
- the selected Code target;
- each planned and executed operation;
- the legal/editorial rationale;
- public website citation links;
- warnings or source defects.

## Trello comments

After reviewing the report, commit and push the resulting repository changes.
Set `TRELLO_KEY` and `TRELLO_TOKEN`, then run:

```bat
POST_TRELLO_COMMENTS.bat D:\us-code
```

The posting tool refuses to run with uncommitted tracked changes. It inserts the
current commit SHA, checks each card for the unique codification marker, and
will not duplicate a comment already posted. Duplicate archive cards receive a
short duplicate-record notice plus the same final law disposition, so the board
does not retain uncross-referenced copies of the same public law.

## Recovery

All touched title XML and state files are copied into a timestamped backup before
live replacement. Changed titles are first written to a staging directory and
parsed as strict XML. The process then checks duplicate `rp-` IDs and suspected
encoding corruption. If any later required validation fails, the title and state
files are restored from the run backup.
## Scope limitation and review standard

This package performs source-authenticated, rule-based codification over the
actual board export on the machine where it runs. It does not claim that an
unreadable attachment or genuinely ambiguous enactment can be resolved by
guessing. Such matters are identified by law number in the unresolved register,
and destructive Code changes are withheld. The completeness gate is intended to
ensure that a mass run cannot silently degrade into another small batch.

