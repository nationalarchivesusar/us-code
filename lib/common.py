from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


LAW_RE = re.compile(
    r"(?:Public\s+Law|Pub\.?\s*L\.?|P\.?L\.?)\s*"
    r"(?P<congress>\d{1,3})\s*[\-–—]\s*(?P<number>\d{1,4})",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://[^\s<>\]\[\)\(\"']+", re.IGNORECASE)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "into", "is", "it", "its", "law", "of", "on",
    "or", "public", "section", "shall", "that", "the", "this", "to", "under",
    "united", "states", "with", "act", "title", "code", "amend", "amended",
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deterministic_id(*parts: str, length: int = 20) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:length]
    return f"rp-{digest}"


def safe_slug(value: str, fallback: str = "item") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value or fallback


def normalize_whitespace(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_xml_text(text: str) -> str:
    # XML 1.0 permits tab, LF, CR, and the normal Unicode ranges below.
    return "".join(
        ch
        for ch in text
        if ch in "\t\n\r"
        or "\u0020" <= ch <= "\ud7ff"
        or "\ue000" <= ch <= "\ufffd"
    )


def extract_law_number(*values: str) -> tuple[str, int | None, int | None]:
    for value in values:
        if not value:
            continue
        match = LAW_RE.search(value)
        if match:
            congress = int(match.group("congress"))
            number = int(match.group("number"))
            return f"PL-{congress:03d}-{number:03d}", congress, number
    # NARA card titles sometimes begin with a bare Congress-law pair such as
    # `38-265 | Employment Clarity ...`. Restrict this fallback to the beginning
    # of each supplied field so dates and section ranges are not misidentified.
    bare = re.compile(r"^\s*(?:P\.?L\.?\s*)?(\d{1,3})\s*[\-–—]\s*(\d{1,4})(?:\b|\s*[|:—-])", re.IGNORECASE)
    for value in values:
        if not value:
            continue
        match = bare.search(value)
        if match:
            congress, number = int(match.group(1)), int(match.group(2))
            return f"PL-{congress:03d}-{number:03d}", congress, number
    return "", None, None


def parse_law_id(value: str) -> tuple[int, int] | None:
    match = re.search(r"PL-(\d+)-(\d+)", value, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def law_sort_key(value: str) -> tuple[int, int, str]:
    parsed = parse_law_id(value)
    if parsed:
        return parsed[0], parsed[1], value
    return 10**6, 10**6, value


def title_from_card_name(name: str) -> str:
    value = LAW_RE.sub("", name)
    # Some NARA cards use a bare leading pair such as `38-265 | Title` rather
    # than spelling out Public Law. Remove only a leading pair so dates and
    # section ranges elsewhere in the title remain untouched.
    value = re.sub(
        r"^\s*(?:P\.?L\.?\s*)?\d{1,3}\s*[\-–—]\s*\d{1,4}\s*(?:[|:—-]\s*)?",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^[\s|:–—-]+|[\s|:–—-]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value or name.strip()


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text.lower())
    return [word for word in words if word not in STOPWORDS]


def unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def atomic_write_text(path: Path, text: str, validator=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        if validator:
            validator(temp_path)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)
