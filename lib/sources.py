from __future__ import annotations

import html
import io
import json
import mimetypes
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.etree import ElementTree as ET

import requests
from pypdf import PdfReader

from .common import LAW_RE, normalize_whitespace, safe_slug, sha256_bytes, sha256_text, tokenize, unique_preserve, write_json
from .model import Attachment, LawCard, SourceRecord


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ODT_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

TEXT_EXTENSIONS = {".txt", ".md", ".rtf", ".html", ".htm", ".docx", ".pdf", ".odt", ".xml"}
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav"}


class SourceManager:
    def __init__(self, workspace: Path, delay: float = 0.35):
        self.workspace = workspace
        self.raw_root = workspace / "sources" / "raw"
        self.text_root = workspace / "sources" / "text"
        self.record_root = workspace / "sources" / "records"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.text_root.mkdir(parents=True, exist_ok=True)
        self.record_root.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36 "
                    "USAR-Codification-Workbench/2.0"
                ),
                "Accept": "*/*",
            }
        )

    def process(self, card: LawCard, refresh: bool = False) -> SourceRecord:
        record_path = self.record_root / f"{safe_slug(card.law_id)}.json"
        if record_path.exists() and not refresh:
            try:
                data = json.loads(record_path.read_text(encoding="utf-8"))
                if data.get("text_path") and Path(data["text_path"]).exists():
                    return SourceRecord(**data)
            except Exception:
                pass

        candidates: list[dict] = []
        raw_dir = self.raw_root / safe_slug(card.law_id)
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Evaluate pasted enactment text before making any extra card-API calls.
        # Older NARA cards often contain the complete law in the description; a
        # strong description source should not trigger redundant network requests
        # across a 200-law corpus. Duplicate cards are also preserved as alternate
        # source candidates because the older duplicate sometimes contains the
        # only intact enactment text.
        description_sources: list[tuple[str, str, str, str]] = [
            (
                card.description,
                card.url,
                "Trello card description",
                "selected from canonical card description rather than attachment",
            )
        ]
        for alternate in card.alternate_descriptions:
            description_sources.append(
                (
                    alternate.get("description", ""),
                    alternate.get("card_url", ""),
                    f"Duplicate card description: {alternate.get('card_name', alternate.get('card_id', 'unknown card'))}",
                    f"selected from duplicate Trello card {alternate.get('card_id', '')}",
                )
            )

        description_candidates: list[dict] = []
        for raw_description, source_url, source_name, source_warning in description_sources:
            description = normalize_whitespace(raw_description)
            if len(description) < 120:
                continue
            pseudo = Attachment(name=source_name, url=source_url, source="description")
            score, matches, warnings = self.score_text(
                card, description, pseudo, Path(f"{safe_slug(source_name)}.txt")
            )
            candidate = {
                "path": "",
                "source_url": source_url,
                "name": source_name,
                "sha256": sha256_text(description),
                "characters": len(description),
                "score": score - 3,
                "identity_matches": matches,
                "warnings": warnings + [source_warning],
                "text": description,
            }
            candidates.append(candidate)
            description_candidates.append(candidate)

        attachments = self._rank_attachments(card)
        strongest_description = max(
            description_candidates,
            key=lambda item: (item.get("score", -100), item.get("characters", 0)),
            default=None,
        )
        strongest_description_text = (
            str(strongest_description.get("text", "")) if strongest_description else ""
        )
        description_looks_enacted = bool(
            strongest_description
            and strongest_description.get("score", -100) >= 8
            and strongest_description.get("identity_matches")
            and (
                "be it enacted" in strongest_description_text.lower()
                or len(
                    re.findall(
                        r"(?im)^\s*(?:SEC(?:TION)?\.?)\s+\d+[A-Za-z]?\s*[.\-—:]",
                        strongest_description_text,
                    )
                ) >= 2
            )
        )
        if not attachments and card.short_link and not description_looks_enacted:
            attachments = self._rank_attachments(self._enrich_card_attachments(card))
        for index, attachment in enumerate(attachments):
            try:
                downloaded = self._download_attachment(card, attachment, raw_dir, index)
                for path, source_url in downloaded:
                    try:
                        text = self.extract_text(path)
                        text = normalize_whitespace(text)
                        score, matches, warnings = self.score_text(card, text, attachment, path)
                        candidates.append(
                            {
                                "path": str(path),
                                "source_url": source_url,
                                "name": attachment.name or path.name,
                                "sha256": sha256_text(text),
                                "characters": len(text),
                                "score": score,
                                "identity_matches": matches,
                                "warnings": warnings,
                                "text": text,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        candidates.append(
                            {
                                "path": str(path),
                                "source_url": source_url,
                                "name": attachment.name or path.name,
                                "score": -100,
                                "characters": 0,
                                "warnings": [f"text extraction failed: {exc}"],
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                candidates.append(
                    {
                        "path": "",
                        "source_url": attachment.url,
                        "name": attachment.name,
                        "score": -100,
                        "characters": 0,
                        "warnings": [f"download failed: {exc}"],
                    }
                )

        candidates.sort(key=lambda item: (item.get("score", -100), item.get("characters", 0)), reverse=True)
        def candidate_is_usable(item: dict) -> bool:
            characters = int(item.get("characters", 0) or 0)
            score = float(item.get("score", -100) or -100)
            if characters < 120 or score < 8:
                return False
            if not item.get("identity_matches") and score < 45:
                return False
            # A Trello description may be a synopsis rather than the enacted law.
            # Use it only when it is substantial and displays actual statutory
            # structure or an enactment formula.
            if "card description" in str(item.get("name", "")).lower():
                source_text = str(item.get("text", ""))
                lower_source = source_text.lower()
                section_count = len(
                    re.findall(
                        r"(?im)^\s*(?:SEC(?:TION)?\.?)\s+\d+[A-Za-z]?\s*[.\-—:]",
                        source_text,
                    )
                )
                statutory_signals = sum(
                    lower_source.count(signal)
                    for signal in (" shall ", " may not ", " is established", " there is established")
                )
                short_but_enacted = (
                    characters >= 120
                    and "be it enacted" in lower_source
                    and statutory_signals >= 2
                    and "public-law number" in item.get("identity_matches", [])
                )
                if not short_but_enacted and (
                    characters < 500
                    or ("be it enacted" not in lower_source and section_count < 2)
                ):
                    return False
            return True

        usable = next((item for item in candidates if candidate_is_usable(item)), None)
        if usable is None:
            record = SourceRecord(
                law_id=card.law_id,
                candidates=[self._clean_candidate(item) for item in candidates],
                error="No readable, plausibly matching enactment source was recovered.",
            )
            write_json(record_path, record.to_dict())
            return record

        text_path = self.text_root / f"{safe_slug(card.law_id)}.txt"
        text_path.write_text(usable["text"] + "\n", encoding="utf-8")
        record = SourceRecord(
            law_id=card.law_id,
            selected_path=usable.get("path", ""),
            selected_url=usable.get("source_url", ""),
            selected_name=usable.get("name", ""),
            text_path=str(text_path),
            sha256=sha256_text(usable["text"]),
            characters=len(usable["text"]),
            score=float(usable.get("score", 0)),
            identity_matches=list(usable.get("identity_matches", [])),
            candidates=[self._clean_candidate(item) for item in candidates],
            warnings=list(usable.get("warnings", [])),
        )
        write_json(record_path, record.to_dict())
        return record

    @staticmethod
    def _clean_candidate(item: dict) -> dict:
        return {key: value for key, value in item.items() if key != "text"}

    def _enrich_card_attachments(self, card: LawCard) -> LawCard:
        """Try the public card JSON export when the board export omitted attachments."""
        urls = [
            f"https://trello.com/c/{card.short_link}.json",
            f"https://trello.com/1/cards/{card.short_link}?fields=all&attachments=true&attachment_fields=all",
        ]
        for url in urls:
            try:
                response = self.session.get(url, timeout=60)
                if response.status_code != 200 or response.text.lstrip().startswith("<"):
                    continue
                payload = response.json()
                raw_items = payload.get("attachments", []) if isinstance(payload, dict) else []
                if not raw_items:
                    continue
                existing = {item.url for item in card.attachments}
                for raw in raw_items:
                    item = Attachment(
                        id=str(raw.get("id", "")),
                        name=str(raw.get("name", "")),
                        url=str(raw.get("url", "")),
                        mime_type=str(raw.get("mimeType", "") or ""),
                        date=str(raw.get("date", "")),
                        is_upload=bool(raw.get("isUpload", False)),
                        source="card-json",
                    )
                    if item.url and item.url not in existing:
                        card.attachments.append(item)
                        existing.add(item.url)
                if card.attachments:
                    return card
            except Exception:
                continue
        return card

    def _rank_attachments(self, card: LawCard) -> list[Attachment]:
        def score(item: Attachment) -> tuple[int, str]:
            value = f"{item.name} {item.url}".lower()
            points = 0
            for term, weight in {
                "enrolled": 20,
                "signed": 18,
                "public law": 18,
                "final": 12,
                "act": 5,
                "bill": 3,
                "document": 2,
                "revised": 3,
                "draft": -12,
                "old": -8,
                "veto": -8,
                "amendment": -2,
                "image": -15,
            }.items():
                if term in value:
                    points += weight
            ext = Path(urlparse(item.url).path).suffix.lower()
            if ext in TEXT_EXTENSIONS:
                points += 8
            if ext in SKIP_EXTENSIONS:
                points -= 30
            if "docs.google.com/document" in value or "drive.google.com/file" in value:
                points += 10
            if item.source == "board":
                points += 2
            return points, item.date

        return sorted(card.attachments, key=score, reverse=True)

    def _download_attachment(
        self,
        card: LawCard,
        attachment: Attachment,
        output: Path,
        index: int,
    ) -> list[tuple[Path, str]]:
        url = attachment.url.strip()
        if not url:
            return []
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        if ext in SKIP_EXTENSIONS:
            return []
        if "trello.com/c/" in url and attachment.source == "description":
            return []

        if "docs.google.com/document/" in url and "/d/" in url:
            match = re.search(r"/document/(?:u/\d+/)?d/([A-Za-z0-9_-]+)", url)
            if not match:
                return []
            doc_id = match.group(1)
            results = []
            errors = []
            for fmt in ("txt", "docx"):
                export_url = f"https://docs.google.com/document/d/{doc_id}/export?format={fmt}"
                path = output / f"{index:03d}-{safe_slug(attachment.name or 'google-doc')}.{fmt}"
                try:
                    downloaded = self._download_url(export_url, path)
                    results.append((downloaded, url))
                except Exception as exc:
                    errors.append(f"{fmt}: {exc}")
            if results:
                return results
            raise RuntimeError("Google Document export failed: " + "; ".join(errors))

        if "docs.google.com/spreadsheets/" in url and "/d/" in url:
            match = re.search(r"/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)", url)
            if not match:
                return []
            export_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=pdf"
            path = output / f"{index:03d}-{safe_slug(attachment.name or 'spreadsheet')}.pdf"
            self._download_url(export_url, path)
            return [(path, url)]

        drive_match = re.search(r"drive\.google\.com/(?:file/d/|open\?id=)([A-Za-z0-9_-]+)", url)
        if drive_match:
            file_id = drive_match.group(1)
            path = output / f"{index:03d}-{safe_slug(attachment.name or file_id)}"
            return [(self._download_drive_file(file_id, path), url)]

        path_name = safe_slug(attachment.name or Path(parsed.path).name or f"attachment-{index}")
        path = output / f"{index:03d}-{path_name}"
        try:
            return [(self._download_url(url, path, infer_extension=True), url)]
        except Exception:
            if attachment.is_upload and attachment.id and card.card_id:
                filename = quote(attachment.name or f"attachment-{attachment.id}")
                direct = (
                    f"https://trello.com/1/cards/{card.card_id}/attachments/"
                    f"{attachment.id}/download/{filename}"
                )
                return [(self._download_url(direct, path, infer_extension=True), url)]
            raise

    def _download_drive_file(self, file_id: str, path: Path) -> Path:
        urls = [
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
            f"https://drive.google.com/uc?export=download&id={file_id}",
        ]
        errors = []
        for url in urls:
            try:
                response = self.session.get(url, timeout=120, allow_redirects=True)
                response.raise_for_status()
                data = response.content
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type or data.lstrip().startswith(b"<"):
                    page = data.decode("utf-8", errors="replace")
                    token_match = re.search(r'name="confirm"\s+value="([^"]+)"', page)
                    if not token_match:
                        token_match = re.search(r"confirm=([0-9A-Za-z_-]+)", page)
                    if token_match:
                        confirm = token_match.group(1)
                        confirm_url = (
                            f"https://drive.usercontent.google.com/download?id={file_id}"
                            f"&export=download&confirm={quote(confirm)}"
                        )
                        response = self.session.get(confirm_url, timeout=120, allow_redirects=True)
                        response.raise_for_status()
                        data = response.content
                        content_type = response.headers.get("content-type", "").lower()
                    if "text/html" in content_type or data.lstrip().startswith(b"<"):
                        if "sign in" in data[:12000].decode("utf-8", errors="ignore").lower():
                            raise RuntimeError("Google Drive file is not publicly accessible")
                        raise RuntimeError("Google Drive returned an HTML confirmation page without a usable token")
                final = path
                if not path.suffix:
                    final = path.with_suffix(self._extension(response, data))
                final.write_bytes(data)
                time.sleep(self.delay)
                return final
            except Exception as exc:
                errors.append(str(exc))
                time.sleep(1)
        raise RuntimeError("Google Drive download failed: " + "; ".join(errors[-3:]))

    def _download_url(self, url: str, path: Path, infer_extension: bool = False) -> Path:
        if path.exists() and path.stat().st_size > 0:
            return path
        errors = []
        for attempt in range(5):
            try:
                response = self.session.get(url, timeout=120, allow_redirects=True)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                data = response.content
                if len(data) < 20:
                    raise RuntimeError("download was implausibly short")
                final = path
                if infer_extension and not path.suffix:
                    extension = self._extension(response, data)
                    final = path.with_suffix(extension)
                final.parent.mkdir(parents=True, exist_ok=True)
                final.write_bytes(data)
                time.sleep(self.delay)
                return final
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                time.sleep(min(16, 2 ** attempt))
        raise RuntimeError(f"download failed after retries: {'; '.join(errors[-3:])}")

    @staticmethod
    def _extension(response: requests.Response, data: bytes) -> str:
        disposition = response.headers.get("content-disposition", "")
        match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.IGNORECASE)
        if match:
            ext = Path(unquote(match.group(1))).suffix
            if ext:
                return ext.lower()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        mapping = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/rtf": ".rtf",
            "text/rtf": ".rtf",
            "text/plain": ".txt",
            "text/html": ".html",
            "application/vnd.oasis.opendocument.text": ".odt",
        }
        if content_type in mapping:
            return mapping[content_type]
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            return guessed
        if data[:4] == b"%PDF":
            return ".pdf"
        if data[:2] == b"PK":
            return ".docx"
        if data.lstrip().startswith(b"<"):
            return ".html"
        return ".bin"

    def extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        data = path.read_bytes()
        if suffix in {".txt", ".md", ".xml"}:
            return data.decode("utf-8-sig", errors="replace")
        if suffix in {".html", ".htm"}:
            return self._extract_html(data.decode("utf-8", errors="replace"))
        if suffix == ".rtf":
            return self._extract_rtf(data.decode("latin-1", errors="replace"))
        if suffix == ".docx" or (data[:2] == b"PK" and self._looks_like_docx(data)):
            return self._extract_docx(path)
        if suffix == ".odt":
            return self._extract_odt(path)
        if suffix == ".pdf" or data[:4] == b"%PDF":
            return self._extract_pdf(path)
        if data.lstrip().startswith(b"<"):
            return self._extract_html(data.decode("utf-8", errors="replace"))

        # Last-resort external converters for legacy .doc files.
        for command in (["antiword", str(path)], ["libreoffice", "--headless", "--convert-to", "txt:Text", "--outdir", str(path.parent), str(path)]):
            if shutil.which(command[0]):
                proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if command[0] == "antiword" and proc.returncode == 0 and len(proc.stdout) > 100:
                    return proc.stdout
                if command[0] == "libreoffice" and proc.returncode == 0:
                    txt = path.with_suffix(".txt")
                    if txt.exists():
                        return txt.read_text(encoding="utf-8", errors="replace")
        raise RuntimeError(f"unsupported or unreadable source format: {path.name}")

    @staticmethod
    def _looks_like_docx(data: bytes) -> bool:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return "word/document.xml" in archive.namelist()
        except Exception:
            return False

    @staticmethod
    def _extract_docx(path: Path) -> str:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = []
        for paragraph in root.iter(W + "p"):
            pieces = []
            for node in paragraph.iter():
                if node.tag == W + "t" and node.text:
                    pieces.append(node.text)
                elif node.tag == W + "tab":
                    pieces.append("\t")
                elif node.tag == W + "br":
                    pieces.append("\n")
            value = "".join(pieces).strip()
            if value:
                paragraphs.append(value)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _extract_odt(path: Path) -> str:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        paragraphs = []
        for node in root.iter():
            if node.tag in {ODT_TEXT + "p", ODT_TEXT + "h"}:
                value = "".join(node.itertext()).strip()
                if value:
                    paragraphs.append(value)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            value = page.extract_text() or ""
            if value.strip():
                pages.append(value)
        text = "\n\n".join(pages)
        if len(text.strip()) < 100:
            pdftotext = shutil.which("pdftotext")
            if pdftotext:
                proc = subprocess.run([pdftotext, "-layout", str(path), "-"], capture_output=True, text=True, timeout=180)
                if proc.returncode == 0 and len(proc.stdout) > len(text):
                    text = proc.stdout
        if len(text.strip()) < 80:
            raise RuntimeError("PDF contains too little extractable text; it may be image-only")
        return text

    @staticmethod
    def _extract_html(value: str) -> str:
        value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
        value = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", value)
        value = re.sub(r"(?s)<[^>]+>", " ", value)
        return html.unescape(value)

    @staticmethod
    def _extract_rtf(value: str) -> str:
        value = re.sub(r"\\par[d]?\b", "\n", value)
        value = re.sub(r"\\'[0-9a-fA-F]{2}", " ", value)
        value = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", value)
        value = value.replace("{", "").replace("}", "")
        return value

    @staticmethod
    def score_text(card: LawCard, text: str, attachment: Attachment, path: Path) -> tuple[float, list[str], list[str]]:
        score = 0.0
        matches: list[str] = []
        warnings: list[str] = []
        lower = text.lower()
        if len(text) >= 500:
            score += 10
        elif len(text) >= 180:
            score += 4
        else:
            score -= 12

        if card.congress is not None and card.law_number is not None:
            patterns = [
                f"public law {card.congress}-{card.law_number}",
                f"public law {card.congress}–{card.law_number}",
                f"pub. l. {card.congress}-{card.law_number}",
                f"pl {card.congress}-{card.law_number}",
            ]
            if any(pattern in lower for pattern in patterns):
                score += 25
                matches.append("public-law number")

        title_tokens = [token for token in tokenize(card.title) if len(token) >= 4]
        present = [token for token in title_tokens if token in lower]
        if title_tokens:
            ratio = len(present) / len(set(title_tokens))
            score += ratio * 30
            if ratio >= 0.5:
                matches.append("law title")
            elif ratio < 0.2:
                warnings.append("few title words found in source")

        for phrase, points in {
            "be it enacted": 12,
            "section 1": 4,
            "short title": 4,
            "effective date": 3,
            "united states code": 4,
        }.items():
            if phrase in lower:
                score += points
                matches.append(phrase)

        name = f"{attachment.name} {path.name}".lower()
        for term, points in {
            "enrolled": 8,
            "signed": 8,
            "final": 5,
            "draft": -8,
            "old": -5,
            "veto": -8,
        }.items():
            if term in name:
                score += points

        if "access denied" in lower or "sign in" in lower[:1000] or "javascript is disabled" in lower[:1000]:
            score -= 60
            warnings.append("download appears to be an access or login page")
        if len(set(text.split())) < 20:
            score -= 20
            warnings.append("source has very little lexical variety")
        return score, unique_preserve(matches), warnings
