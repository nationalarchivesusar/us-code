# Validation Report — Held-Law Round 2

## Result

The package approves two BAT-compatible plans:

- PL-004-036 — Defense Heraldic Services Act of 2022
- PL-038-266 — Speedy Trial Act of 2026

It resolves four other held laws without an executable Code operation:

- PL-001-004 — defective reference to nonexistent section 3(a), with the law recorded as repealed
- PL-002-005 — expressly repealed and superseded by PL-019-149 §§ 6–8
- PL-002-006 — expressly repealed and replaced by PL-014-089 §§ 3–6
- PL-003-025 — later repeal and replacement chain does not support a safe wholesale catch-up insertion

## Scratch application

The installer was tested using the same transactional `rp_codifier.py` engine used by the BAT. It successfully:

1. generated hashes from the current target elements;
2. generated repealed placeholders for 18 U.S.C. §§ 3164–3174 while preserving their existing source credits and notes;
3. applied PL-004-036 and PL-038-266 in a disposable repository;
4. committed one transactional write per affected title;
5. parsed the resulting Title 10 and Title 18 XML without recovery mode; and
6. recorded both laws in disposable state.

## Verified results

- New 10 U.S.C. § 206 appears immediately after § 205.
- New § 206 preserves the wording and punctuation enacted by PL-004-036 § III.
- 10 U.S.C. § 7594 and its TOC entry read `[Reserved]`.
- Existing § 7594 source credits and notes remain present.
- PL-038-266 § 3 is codified at 18 U.S.C. § 3161.
- PL-038-266 § 4 is codified at 18 U.S.C. § 3162.
- PL-038-266 § 5 is codified at 18 U.S.C. § 3163 under the heading `Deadlines`.
- Enacted labels including § 3161(b)(i), § 3161(c)(iv)(1)(a), and § 3162(b)(v) are preserved.
- The § 3163 TOC heading is synchronized to `Deadlines.`.
- Former §§ 3164–3174 and their TOC entries read `[Repealed]`.
- Preexisting source credits and editorial notes for §§ 3164–3174 remain present.
- No duplicate project-generated `rp-` IDs were created.
- No Unicode replacement characters or known mojibake patterns were introduced.
- Website title metadata rebuilt successfully in the reduced Title 10/18 test repository.

## Safety

The installer itself does not modify live `usc/*.xml` files and does not modify `codification/state.json`. It installs approved plans only after repeating the scratch application against the user’s actual current Title 10 and Title 18 files. The BAT remains the only application mechanism.
