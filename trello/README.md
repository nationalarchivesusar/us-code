# Trello disposition updates

After application, add a comment to each affected NARA card containing:

- source SHA-256;
- classification location;
- Code sections/files changed;
- application date and commit;
- whether the law was classified as Code text, statutory note, repeal-only,
  superseded, or audit-only;
- unresolved ambiguities.

The pipeline writes decision memoranda in `codification\decisions`. Those are the
source for the Trello comments. Do not claim a candidate plan was applied until
`codification\state.json` and the Git diff confirm it.
