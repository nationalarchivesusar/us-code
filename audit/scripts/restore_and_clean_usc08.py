from __future__ import annotations

import re
import subprocess
from pathlib import Path


def main() -> None:
    path = Path("usc/usc08.xml")
    blob = subprocess.check_output(["git", "show", "HEAD:usc/usc08.xml"])
    text = blob.decode("utf-8")

    def clean_note(match: re.Match[str]) -> str:
        note = match.group(0)
        note = re.sub(r"<p><b>Archive record\.</b>\s*https://trello\.com/[^<]*</p>", "", note)
        note = re.sub(
            r"<p><b>Source limitation\.</b>\s*Authenticated statutory text was unavailable or the supplied attachment yielded only viewer, permission, or account-page material\. No operative language has been invented\.</p>",
            "",
            note,
        )
        note = re.sub(r"<quotedContent\b[^>]*>.*?</quotedContent>", "", note, flags=re.DOTALL)
        return note

    text = re.sub(r'<note\b(?=[^>]*id="rp-)[\s\S]*?</note>', clean_note, text)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print("Restored usc08.xml from HEAD and reapplied rp-note cleanup")


if __name__ == "__main__":
    main()
