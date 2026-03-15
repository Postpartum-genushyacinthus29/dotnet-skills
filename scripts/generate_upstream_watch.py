#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def iter_fragment_paths(fragments_dir: Path) -> list[Path]:
    return sorted(path for path in fragments_dir.rglob("*.json") if path.is_file())


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def parse_github_repo_reference(reference: str) -> tuple[str, str]:
    cleaned = reference.strip().removesuffix(".git").rstrip("/")
    if cleaned.startswith("https://") or cleaned.startswith("http://"):
        parsed = urlparse(cleaned)
        if parsed.netloc.lower() != "github.com":
            raise ValueError(f"Unsupported GitHub repository URL: {reference}")
        parts = [part for part in parsed.path.split("/") if part]
    else:
        parts = [part for part in cleaned.split("/") if part]

    if len(parts) != 2:
        raise ValueError(f"GitHub repository reference must be owner/repo or a GitHub repo URL: {reference}")

    owner, repo = parts
    return owner, repo


def default_http_watch_id(url: str) -> str:
    parsed = urlparse(url)
    host = slugify(parsed.netloc)
    path = slugify(parsed.path.strip("/")) or "root"
    return f"{host}-{path}-docs"


def default_http_watch_name(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "/"
    return f"{parsed.netloc}{path} documentation"


def normalize_github_release_watch(watch: dict[str, Any]) -> dict[str, Any]:
    repo_reference = watch.get("repo")
    if not isinstance(repo_reference, str) or not repo_reference.strip():
        raise ValueError("github_release watch requires a non-empty repo field")

    owner, repo = parse_github_repo_reference(repo_reference)
    watch_id = watch.get("id") or f"{slugify(owner)}-{slugify(repo)}-release"

    normalized: dict[str, Any] = {
        "id": watch_id,
        "kind": "github_release",
        "name": watch.get("name") or f"{owner}/{repo} release",
        "owner": owner,
        "repo": repo,
        "notes": watch.get("notes") or f"Review the linked skills when {owner}/{repo} ships a new release.",
        "skills": watch.get("skills"),
    }

    for key in ("match_tag_regex", "exclude_tag_regex", "include_prereleases"):
        if key in watch:
            normalized[key] = watch[key]

    return normalized


def normalize_http_document_watch(watch: dict[str, Any]) -> dict[str, Any]:
    url = watch.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("http_document watch requires a non-empty url field")

    normalized: dict[str, Any] = {
        "id": watch.get("id") or default_http_watch_id(url),
        "kind": "http_document",
        "name": watch.get("name") or default_http_watch_name(url),
        "url": url,
        "notes": watch.get("notes") or f"Review the linked skills when {url} changes.",
        "skills": watch.get("skills"),
    }
    return normalized


def normalize_watch(watch: dict[str, Any], path: Path) -> dict[str, Any]:
    kind = watch.get("kind")

    if kind == "github_release":
        normalized = normalize_github_release_watch(watch)
    elif kind == "http_document":
        normalized = normalize_http_document_watch(watch)
    elif "repo" in watch:
        normalized = normalize_github_release_watch(watch)
    elif "url" in watch:
        normalized = normalize_http_document_watch(watch)
    else:
        raise ValueError(f"Watch in {path} must define either repo or url")

    skills = normalized.get("skills")
    if not isinstance(skills, list) or not skills or not all(isinstance(skill, str) and skill for skill in skills):
        raise ValueError(f"Watch {normalized.get('id', '<unknown>')} in {path} must define a non-empty skills list")

    return normalized


def merge_fragments(fragments_dir: Path) -> dict[str, Any]:
    watch_issue_label: str | None = None
    labels: list[dict[str, Any]] = []
    watches: list[dict[str, Any]] = []
    label_names: set[str] = set()
    watch_ids: set[str] = set()

    fragment_paths = iter_fragment_paths(fragments_dir)
    if not fragment_paths:
        raise ValueError(f"No upstream watch fragments found under {fragments_dir}")

    for path in fragment_paths:
        fragment = load_json(path)

        fragment_watch_issue_label = fragment.get("watch_issue_label")
        if fragment_watch_issue_label is not None:
            if watch_issue_label is not None and watch_issue_label != fragment_watch_issue_label:
                raise ValueError(
                    f"Conflicting watch_issue_label values: {watch_issue_label!r} versus {fragment_watch_issue_label!r} in {path}"
                )
            watch_issue_label = fragment_watch_issue_label

        for label in fragment.get("labels", []):
            name = label.get("name")
            if not name:
                raise ValueError(f"Label without name in {path}")
            if name in label_names:
                raise ValueError(f"Duplicate label name {name!r} in {path}")
            label_names.add(name)
            labels.append(label)

        for watch in fragment.get("watches", []):
            normalized_watch = normalize_watch(watch, path)
            watch_id = normalized_watch.get("id")
            if not watch_id:
                raise ValueError(f"Watch without id in {path}")
            if watch_id in watch_ids:
                raise ValueError(f"Duplicate watch id {watch_id!r} in {path}")
            watch_ids.add(watch_id)
            watches.append(normalized_watch)

    if watch_issue_label is None:
        raise ValueError("No watch_issue_label defined in upstream watch fragments")

    return {
        "watch_issue_label": watch_issue_label,
        "labels": labels,
        "watches": watches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate .github/upstream-watch.json from fragment files.")
    parser.add_argument("--fragments-dir", default=".github/upstream-watch.d")
    parser.add_argument("--output", default=".github/upstream-watch.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    fragments_dir = Path(args.fragments_dir)
    output_path = Path(args.output)
    generated = merge_fragments(fragments_dir)
    rendered = json.dumps(generated, indent=2) + "\n"

    if args.check:
        current = output_path.read_text() if output_path.exists() else ""
        if current != rendered:
            print(f"{output_path} is out of date.", file=sys.stderr)
            return 1
        return 0

    dump_json(output_path, generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
