from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from .common import URL_RE, extract_law_number, law_sort_key, title_from_card_name, unique_preserve, write_json
from .model import Attachment, LawCard


BOARD_URLS = [
    "https://trello.com/b/IeLG19O4/nara-public-law-database.json",
    "https://trello.com/b/IeLG19O4.json",
]

NEGATIVE_STATUS = {
    "repealed": "repealed",
    "rescinded": "rescinded",
    "expired": "expired",
    "failed": "failed",
    "vetoed": "failed",
    "rejected": "failed",
    "withdrawn": "withdrawn",
    "superseded": "superseded",
    "invalid": "invalid",
    "void": "invalid",
    "denied": "failed",
}

ACTIVE_TERMS = {
    "active", "current", "in effect", "public law", "signed", "enacted",
    "passed", "law database", "effective",
}


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36 "
                "USAR-Codification-Workbench/2.0"
            ),
            "Accept": "application/json,text/plain,*/*",
        }
    )
    return session


def download_board(output: Path, supplied: Path | None = None) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if supplied:
        data = json.loads(supplied.read_text(encoding="utf-8-sig"))
        output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    session = _session()
    errors: list[str] = []
    for attempt in range(4):
        for url in BOARD_URLS:
            try:
                response = session.get(url, timeout=120)
                if response.status_code != 200:
                    errors.append(f"{url}: HTTP {response.status_code}")
                    continue
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower() and response.text.lstrip().startswith("<"):
                    errors.append(f"{url}: returned HTML instead of JSON")
                    continue
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("cards"), list):
                    errors.append(f"{url}: JSON did not contain a cards array")
                    continue
                output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")
        time.sleep(2 ** attempt)

    raise RuntimeError(
        "Could not download the public Trello JSON export. "
        "Open the board in a browser, append `.json` to its URL, save the result, "
        "and rerun with --board-json PATH. Attempts:\n- " + "\n- ".join(errors[-10:])
    )


def _attachment_from(raw: dict[str, Any], source: str = "board") -> Attachment:
    return Attachment(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        url=str(raw.get("url", "")),
        mime_type=str(raw.get("mimeType", raw.get("mime_type", "")) or ""),
        date=str(raw.get("date", "")),
        is_upload=bool(raw.get("isUpload", False)),
        source=source,
    )


def infer_status(card: LawCard) -> tuple[str, list[str]]:
    evidence: list[str] = []

    # Board list and label placement are authoritative status metadata.  A word
    # such as "expired" or "invalid" may also occur innocently in an Act's
    # title, so do not treat an unmarked title word as dispositive.
    metadata = " | ".join([card.list_name, *card.labels]).lower()
    for term, status in NEGATIVE_STATUS.items():
        if term in metadata:
            evidence.append(f"status keyword `{term}` in list or label")
            return status, evidence

    marked_name = card.name.lower()
    for term, status in NEGATIVE_STATUS.items():
        if re.search(
            rf"(?:^|[\[(|:—-]\s*)(?:status\s*[:=-]\s*)?{re.escape(term)}(?:\s*[\])|:—-]|$)",
            marked_name,
        ):
            evidence.append(f"marked status keyword `{term}` in card name")
            return status, evidence

    # Description language is weaker because a current law may repeal another law.
    heading = "\n".join(card.description.splitlines()[:8]).lower()
    for term, status in NEGATIVE_STATUS.items():
        if re.search(rf"\bstatus\s*[:=-]\s*{re.escape(term)}\b", heading):
            evidence.append(f"explicit status `{term}` near top of card description")
            return status, evidence

    for term in ACTIVE_TERMS:
        if term in metadata:
            evidence.append(f"active keyword `{term}` in list or label")
            return "active", evidence

    # Congressional archive lists usually carry only a Congress number. An enacted
    # card without an adverse status is treated as active, but this assumption is
    # recorded for review.
    evidence.append("no adverse list, label, or explicit status marker; treated as active")
    return "active", evidence


def parse_cards(board: dict[str, Any]) -> list[LawCard]:
    lists = {str(item.get("id", "")): str(item.get("name", "")) for item in board.get("lists", [])}
    cards: list[LawCard] = []

    action_attachments: dict[str, list[Attachment]] = {}
    for action in board.get("actions", []) or []:
        if action.get("type") != "addAttachmentToCard":
            continue
        data = action.get("data", {}) or {}
        card = data.get("card", {}) or {}
        attachment = data.get("attachment", {}) or {}
        card_id = str(card.get("id", ""))
        if card_id and attachment:
            action_attachments.setdefault(card_id, []).append(_attachment_from(attachment, "action"))

    for raw in board.get("cards", []) or []:
        card_id = str(raw.get("id", ""))
        labels = [str(label.get("name", "")).strip() for label in raw.get("labels", []) or []]
        attachments = [_attachment_from(item) for item in raw.get("attachments", []) or []]
        attachments.extend(action_attachments.get(card_id, []))

        # URLs in card descriptions are legitimate source candidates even when the
        # board export omits attachment bodies.
        for index, url in enumerate(URL_RE.findall(str(raw.get("desc", "")))):
            attachments.append(
                Attachment(
                    id=f"desc-{index}",
                    name=Path(url.split("?", 1)[0]).name or "description-link",
                    url=url.rstrip(".,;"),
                    source="description",
                )
            )

        unique: dict[str, Attachment] = {}
        for attachment in attachments:
            if attachment.url and attachment.url not in unique:
                unique[attachment.url] = attachment

        card = LawCard(
            card_id=card_id,
            short_link=str(raw.get("shortLink", "")),
            name=str(raw.get("name", "")).strip(),
            description=str(raw.get("desc", "")),
            list_name=lists.get(str(raw.get("idList", "")), "UNKNOWN"),
            labels=[label for label in labels if label],
            url=str(raw.get("url", "")) or (
                f"https://trello.com/c/{raw.get('shortLink')}" if raw.get("shortLink") else ""
            ),
            closed=bool(raw.get("closed", False)),
            last_activity=str(raw.get("dateLastActivity", "")),
            attachments=list(unique.values()),
        )
        law_id, congress, number = extract_law_number(card.name, card.description, card.list_name)
        card.law_id = law_id or f"CARD-{card.short_link or card.card_id[:8]}"
        card.congress = congress
        card.law_number = number
        card.title = title_from_card_name(card.name)
        card.status, card.status_evidence = infer_status(card)
        cards.append(card)

    return cards


def canonicalize_cards(cards: list[LawCard]) -> tuple[list[LawCard], dict[str, list[LawCard]]]:
    groups: dict[str, list[LawCard]] = {}
    for card in cards:
        groups.setdefault(card.law_id, []).append(card)

    canonical: list[LawCard] = []
    duplicates: dict[str, list[LawCard]] = {}
    status_rank = {
        "active": 8,
        "unknown": 7,
        "expired": 4,
        "superseded": 3,
        "repealed": 2,
        "rescinded": 2,
        "withdrawn": 1,
        "failed": 0,
        "invalid": 0,
    }

    for law_id, group in groups.items():
        ordered = sorted(
            group,
            key=lambda card: (
                status_rank.get(card.status, 5),
                len(card.attachments),
                len(card.description),
                card.last_activity,
            ),
            reverse=True,
        )
        selected = ordered[0]
        selected.duplicate_card_ids = [card.card_id for card in ordered[1:]]
        selected.duplicate_card_records = [
            {
                "card_id": duplicate.card_id,
                "short_link": duplicate.short_link,
                "card_url": duplicate.url,
                "card_name": duplicate.name,
                "list_name": duplicate.list_name,
                "status": duplicate.status,
            }
            for duplicate in ordered[1:]
        ]
        if len(group) > 1:
            duplicates[law_id] = ordered
            # Pool source links from duplicate cards without changing the selected
            # card's status evidence.
            by_url = {item.url: item for item in selected.attachments if item.url}
            for duplicate in ordered[1:]:
                for item in duplicate.attachments:
                    if item.url and item.url not in by_url:
                        by_url[item.url] = item
            selected.attachments = list(by_url.values())
            selected.alternate_descriptions = [
                {
                    "card_id": duplicate.card_id,
                    "card_url": duplicate.url,
                    "card_name": duplicate.name,
                    "description": duplicate.description,
                }
                for duplicate in ordered[1:]
                if duplicate.description.strip()
            ]
        canonical.append(selected)

    canonical.sort(key=lambda card: law_sort_key(card.law_id))
    return canonical, duplicates


def save_card_inventory(path: Path, cards: list[LawCard], duplicates: dict[str, list[LawCard]]) -> None:
    write_json(
        path,
        {
            "card_count": len(cards),
            "duplicate_law_count": len(duplicates),
            "cards": [card.to_dict() for card in cards],
            "duplicates": {
                law_id: [card.to_dict() for card in group]
                for law_id, group in duplicates.items()
            },
        },
    )
