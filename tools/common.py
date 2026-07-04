from __future__ import annotations
import hashlib, json, re
from pathlib import Path

NS_URI = "http://xml.house.gov/schemas/uslm/1.0"
X = f"{{{NS_URI}}}"

def package_root() -> Path:
    return Path(__file__).resolve().parents[1]

def registry_path(repo: Path) -> Path:
    installed = repo / "codification" / "round3" / "source_registry.json"
    return installed if installed.exists() else package_root() / "payload" / "source_registry.json"

def load_registry(repo: Path):
    return json.loads(registry_path(repo).read_text(encoding="utf-8"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")

def element_span(xml: str, identifier: str):
    ident = re.escape(identifier)
    start_match = re.search(
        rf'<(?P<tag>[A-Za-z0-9_:.-]+)\b(?=[^>]*\bidentifier="{ident}")[^>]*>',
        xml, flags=re.DOTALL
    )
    if not start_match:
        raise ValueError(f"Identifier not found: {identifier}")
    tag = start_match.group("tag")
    token_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.DOTALL)
    depth = 0
    for token in token_re.finditer(xml, start_match.start()):
        value = token.group(0)
        if value.startswith(f"</{tag}"):
            depth -= 1
            if depth == 0:
                return start_match.start(), token.end(), tag
        elif value.endswith("/>"):
            if depth == 0:
                return start_match.start(), token.end(), tag
        else:
            depth += 1
    raise ValueError(f"Could not find closing tag for {identifier}")

def get_element(xml: str, identifier: str) -> str:
    a, b, _ = element_span(xml, identifier)
    return xml[a:b]

def make_id(law_id: str, target: str, suffix: str) -> str:
    digest = hashlib.sha1(f"{law_id}|{target}|{suffix}".encode()).hexdigest()[:20]
    return f"rp-{digest}"
