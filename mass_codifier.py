#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from lib.apply_engine import MassApplier  # noqa: E402
from lib.codebase import CodeIndex, validate_xml  # noqa: E402
from lib.common import law_sort_key, parse_law_id, read_json, relative, write_json  # noqa: E402
from lib.legal_analysis import LegalAnalyzer, apply_dependency_overrides  # noqa: E402
from lib.model import LawAnalysis, LawCard, SourceRecord  # noqa: E402
from lib.reports import write_all_reports  # noqa: E402
from lib.sources import SourceManager  # noqa: E402
from lib.trello import canonicalize_cards, download_board, parse_cards, save_card_inventory  # noqa: E402


PRIOR_PACKAGE_FILES = [
    "FINISH_PUBLIC_LAWS.bat",
    "finish_public_laws.py",
    "SHA256SUMS.txt",
    "README-FIRST.md",
    "ROUND3-IMPLEMENTATION-MAP.md",
    "install_round2_plans.bat",
    "install_round2_plans.py",
    "install_round3_push.bat",
    "install_round3_push.py",
    "run_round3_pipeline.bat",
    "PACKAGE-MANIFEST.json",
    "VALIDATION-REPORT.md",
]

GITIGNORE_LINES = [
    "",
    "# Local mass public-law codification workbench",
    "/MASS_CODIFY_ALL_PUBLIC_LAWS.bat",
    "/MASS_CODIFY_PREVIEW.bat",
    "/POST_TRELLO_COMMENTS.bat",
    "/mass_codifier.py",
    "/post_trello_comments.py",
    "/usar-mass-codification/",
    "/codification/",
]


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Inventory, analyze, and codify the entire NARA public-law Trello corpus."
    )
    ap.add_argument("--repo", required=True, help="Path to the us-code repository")
    ap.add_argument("--board-json", help="Optional saved Trello board JSON export")
    ap.add_argument("--preview-only", action="store_true", help="Generate plans and reports without changing the repository")
    ap.add_argument("--apply", action="store_true", help="Apply planned Code changes transactionally")
    ap.add_argument("--refresh-sources", action="store_true", help="Redownload and re-extract source documents")
    ap.add_argument("--minimum-decisions", type=int, default=100, help="Minimum active remaining laws that must receive actionable dispositions")
    ap.add_argument("--max-source-holds", type=int, default=10, help="Maximum active source-unavailable holds permitted before application is refused")
    ap.add_argument("--repair-repo", action="store_true", help="Restore the repository README and remove prior package files")
    return ap


def validate_repo(repo: Path) -> None:
    if not (repo / "usc").is_dir() or not (repo / "usc" / "usc18.xml").exists():
        raise SystemExit(f"Not a U.S. Code repository: {repo}")
    validate_xml(repo / "usc" / "usc18.xml")
    title42 = repo / "usc" / "usc42.xml"
    if title42.exists():
        first = title42.read_bytes()[:200]
        if b"version https://git-lfs.github.com/spec" in first:
            raise SystemExit(
                "usc/usc42.xml is still a Git LFS pointer. Run `git lfs pull` in the repository before mass codification."
            )


def git_snapshot(repo: Path) -> dict:
    if not (repo / ".git").exists() or not shutil.which("git"):
        return {"available": False}
    result = {"available": True}
    for key, command in {
        "head": ["git", "rev-parse", "HEAD"],
        "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "tracked_changes": ["git", "status", "--porcelain", "--untracked-files=no"],
    }.items():
        proc = subprocess.run(command, cwd=repo, text=True, capture_output=True)
        result[key] = proc.stdout.strip() if proc.returncode == 0 else ""
    return result


def repair_repository(repo: Path, workspace: Path) -> dict:
    backup = workspace / "repair-backup" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    changed = []
    removed = []

    readme = repo / "README.md"
    template = PACKAGE_ROOT / "templates" / "README.repository.md"
    if readme.exists():
        current = readme.read_text(encoding="utf-8", errors="replace")
        if current.lstrip().startswith("# Final Public-Law Implementation"):
            destination = backup / "README.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(readme, destination)
            readme.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
            changed.append("README.md")

    for relative_path in PRIOR_PACKAGE_FILES:
        path = repo / relative_path
        if not path.exists():
            continue
        destination = backup / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copy2(path, destination)
            path.unlink()
        else:
            shutil.copytree(path, destination, dirs_exist_ok=True)
            shutil.rmtree(path)
        removed.append(relative_path)

    gitignore = repo / ".gitignore"
    current_ignore = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing = [line for line in GITIGNORE_LINES if line and line not in current_ignore]
    if missing:
        destination = backup / ".gitignore"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if gitignore.exists():
            shutil.copy2(gitignore, destination)
        with gitignore.open("a", encoding="utf-8") as handle:
            if current_ignore and not current_ignore.endswith("\n"):
                handle.write("\n")
            handle.write("\n# Local mass public-law codification workbench\n")
            for line in missing:
                if line.startswith("#"):
                    continue
                handle.write(line + "\n")
        changed.append(".gitignore")

    return {"backup": str(backup), "changed": changed, "removed": removed}


def restore_repository_repair(repo: Path, repair_result: dict | None) -> None:
    if not repair_result:
        return
    backup = Path(repair_result.get("backup", ""))
    if not backup.exists():
        return
    for relative_path in [*repair_result.get("changed", []), *repair_result.get("removed", [])]:
        source = backup / relative_path
        if not source.exists():
            continue
        destination = repo / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)


def load_sources(
    cards: list[LawCard],
    workspace: Path,
    refresh: bool,
) -> dict[str, SourceRecord]:
    manager = SourceManager(workspace)
    sources: dict[str, SourceRecord] = {}
    total = len(cards)
    for index, card in enumerate(cards, 1):
        # Failed and withdrawn records still receive a source record when a source
        # is readily available, but no download failure for a nonoperative card can
        # block current-law codification.
        print(f"[SOURCE {index}/{total}] {card.law_id} — {card.title}")
        try:
            sources[card.law_id] = manager.process(card, refresh=refresh)
        except Exception as exc:  # noqa: BLE001
            sources[card.law_id] = SourceRecord(law_id=card.law_id, error=str(exc))
            print(f"  warning: {exc}")
    return sources


def analyze_all(
    repo: Path,
    cards: list[LawCard],
    sources: dict[str, SourceRecord],
) -> list[LawAnalysis]:
    code_index = CodeIndex(repo)
    analyzer = LegalAnalyzer(repo, PACKAGE_ROOT, code_index)
    analyses = []
    for index, card in enumerate(cards, 1):
        analysis = analyzer.analyze(card, sources[card.law_id])
        analyses.append(analysis)
        print(
            f"[ANALYZE {index}/{len(cards)}] {card.law_id}: "
            f"{analysis.disposition} ({analysis.confidence})"
        )
    apply_dependency_overrides(analyses)
    return analyses


def completeness_gate(
    analyses: list[LawAnalysis],
    minimum_decisions: int,
    max_source_holds: int,
    suspected_unparsed: list[LawCard] | None = None,
) -> dict:
    active_remaining = [
        item
        for item in analyses
        if item.status == "active" and item.disposition != "ALREADY_INCORPORATED"
    ]
    actionable = [item for item in active_remaining if item.disposition != "SOURCE_UNAVAILABLE"]
    source_holds = [item for item in active_remaining if item.disposition == "SOURCE_UNAVAILABLE"]
    required = min(minimum_decisions, len(active_remaining))
    suspected_unparsed = suspected_unparsed or []
    result = {
        "active_remaining": len(active_remaining),
        "actionable": len(actionable),
        "source_holds": len(source_holds),
        "required": required,
        "suspected_unparsed_law_cards": len(suspected_unparsed),
        "suspected_unparsed_card_urls": [card.url for card in suspected_unparsed],
        "passed": (
            len(actionable) >= required
            and len(source_holds) <= max_source_holds
            and not suspected_unparsed
        ),
        "source_hold_laws": [item.law_id for item in source_holds],
    }
    return result


def main() -> int:
    args = parser().parse_args()
    if not args.preview_only and not args.apply:
        raise SystemExit("Choose --preview-only or --apply")
    repo = Path(args.repo).resolve()
    validate_repo(repo)

    workspace = repo / "codification" / "mass_migration" / "latest"
    workspace.mkdir(parents=True, exist_ok=True)
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    failure_report = reports / f"FAILURE-{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    before = git_snapshot(repo)
    write_json(workspace / "repository-before.json", before)
    repair_result = None
    applier = None

    try:
        board_path = workspace / "board" / "trello-board.json"
        board = download_board(
            board_path,
            Path(args.board_json).resolve() if args.board_json else None,
        )
        raw_cards = parse_cards(board)
        public_law_cards = [card for card in raw_cards if parse_law_id(card.law_id)]
        non_law_cards = [card for card in raw_cards if not parse_law_id(card.law_id)]
        suspected_unparsed = [
            card for card in non_law_cards
            if "public law" in f"{card.name}\n{card.description}".lower()
            or "be it enacted" in card.description.lower()
            or re.search(r"^\s*\d{1,3}\s*[\-–—]\s*\d{1,4}", card.name)
        ]
        cards, duplicates = canonicalize_cards(public_law_cards)
        save_card_inventory(workspace / "board" / "canonical-card-inventory.json", cards, duplicates)
        write_json(
            workspace / "board" / "non-public-law-cards.json",
            {
                "count": len(non_law_cards),
                "suspected_unparsed_law_count": len(suspected_unparsed),
                "suspected_unparsed_law_cards": [card.to_dict() for card in suspected_unparsed],
                "cards": [card.to_dict() for card in non_law_cards],
            },
        )
        print(
            f"[BOARD] {len(raw_cards)} cards, {len(cards)} canonical public laws, "
            f"{len(duplicates)} duplicate law numbers, {len(non_law_cards)} non-law cards excluded, "
            f"{len(suspected_unparsed)} suspected law cards require number repair"
        )
        if not cards:
            raise RuntimeError("The board export contained no recognizable public-law records.")

        sources = load_sources(cards, workspace, args.refresh_sources)
        analyses = analyze_all(repo, cards, sources)
        card_map = {card.law_id: card for card in cards}

        gate = completeness_gate(
            analyses, args.minimum_decisions, args.max_source_holds, suspected_unparsed
        )
        write_json(reports / "COMPLETENESS-GATE.json", gate)
        write_all_reports(workspace, card_map, sources, analyses)

        print(
            f"[GATE] actionable={gate['actionable']} required={gate['required']} "
            f"source-holds={gate['source_holds']} allowed={args.max_source_holds}"
        )

        if args.preview_only:
            print(f"PREVIEW COMPLETE: {reports / 'MASTER-CODIFICATION-REPORT.md'}")
            return 0

        if not gate["passed"]:
            raise RuntimeError(
                "Completeness gate failed before any Code write. "
                f"Actionable {gate['actionable']}/{gate['required']}; "
                f"source holds {gate['source_holds']}/{args.max_source_holds}; "
                f"suspected unparsed law cards {gate['suspected_unparsed_law_cards']}. "
                "Review UNRESOLVED-REGISTER.md, non-public-law-cards.json, or supply a complete board export/source set."
            )

        if args.repair_repo:
            repair_result = repair_repository(repo, workspace)
            write_json(reports / "REPOSITORY-REPAIR.json", repair_result)
            print(
                f"[REPAIR] changed={len(repair_result['changed'])} "
                f"removed={len(repair_result['removed'])}"
            )

        applier = MassApplier(
            repo,
            workspace,
            CodeIndex(repo),
            card_map,
            sources,
            analyses,
        )
        manifest = applier.apply()
        final_paths = write_all_reports(workspace, card_map, sources, analyses, manifest)
        after = git_snapshot(repo)
        write_json(workspace / "repository-after.json", after)

        summary = {
            "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "board_cards": len(raw_cards),
            "canonical_laws": len(cards),
            "completeness_gate": gate,
            "dispositions": dict(Counter(item.disposition for item in analyses)),
            "laws_applied": sum(1 for item in analyses if item.applied),
            "changed_files": manifest.get("changed_files", []),
            "reports": final_paths,
            "repository_repair": repair_result,
        }
        write_json(reports / "FINAL-SUMMARY.json", summary)
        print("\nMASS CODIFICATION COMPLETE")
        print(f"Canonical laws analyzed: {len(cards)}")
        print(f"Laws changing Code: {summary['laws_applied']}")
        print(f"Master report: {final_paths['master_report']}")
        print(f"Trello comments: {final_paths['comments']}")
        print(f"Dashboard: {final_paths['dashboard']}")
        return 0

    except Exception as exc:  # noqa: BLE001
        if applier is not None:
            try:
                applier.restore()
            except Exception as apply_restore_exc:  # noqa: BLE001
                print(f"Warning: Code/state restoration failed: {apply_restore_exc}", file=sys.stderr)
        try:
            restore_repository_repair(repo, repair_result)
        except Exception as repair_exc:  # noqa: BLE001
            print(f"Warning: repository-repair restoration failed: {repair_exc}", file=sys.stderr)
        failure = (
            f"Mass codification failed at {dt.datetime.now(dt.timezone.utc).isoformat()}\n\n"
            f"{exc}\n\n{traceback.format_exc()}"
        )
        failure_report.write_text(failure, encoding="utf-8")
        print(failure, file=sys.stderr)
        print(f"Failure report: {failure_report}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
