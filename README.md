# Final Public-Law Implementation

Run from Command Prompt:

```bat
FINISH_PUBLIC_LAWS.bat D:\us-code
```

The finalizer uses the authenticated texts already downloaded here:

```text
D:\us-code\codification\round3\sources\text\
```

It implements:

- PL 19-149 at 18 U.S.C. § 3551 as the current general sentencing note;
- PL 14-89 at 18 U.S.C. § 242 as the current federal-agent misconduct note;
- PL 38-263 at 50 U.S.C. § 3341 as the current national-security framework;
- PL 38-264 at 18 U.S.C. § 1961 as the current organized-crime framework;
- PL 3-25 as repealed/superseded, with no wholesale catch-up insertion.

It backs up all changed files, validates XML before and after writing, rebuilds
the title index, runs the available repository audits, updates the local
codification state, archives the downloaded Round 3 source record, and removes
the temporary Round 2/Round 3 package files.

Final records:

```text
codification\reports\FINAL-PUBLIC-LAWS-REPORT.md
codification\reports\FINAL-TRELLO-COMMENTS.md
codification\reports\PL-003-025-final-survival-audit.json
```
