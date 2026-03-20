#!/usr/bin/env python3
"""Generate catalog release notes from Git history and GitHub metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ISSUE_REF_PATTERN = re.compile(r"#(\d+)")
AUTO_REF_PATTERN = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)\b", re.IGNORECASE)


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr.strip()}")
    return completed.stdout


def load_git_commits(previous_tag: str | None, target_commit: str) -> list[dict[str, str]]:
    if previous_tag:
        revision_range = f"{previous_tag}..{target_commit}"
        command = ["git", "log", "--reverse", f"--format=%H%x1f%an%x1f%ae%x1f%s%x1f%b%x1e", revision_range]
    else:
        command = ["git", "log", "--reverse", "--max-count=25", f"--format=%H%x1f%an%x1f%ae%x1f%s%x1f%b%x1e", target_commit]

    raw_output = run(command)
    commits: list[dict[str, str]] = []
    for record in raw_output.split("\x1e"):
        if not record.strip():
            continue
        sha, author_name, author_email, subject, body = record.split("\x1f", maxsplit=4)
        commits.append(
            {
                "sha": sha.strip(),
                "author_name": author_name.strip(),
                "author_email": author_email.strip(),
                "subject": subject.strip(),
                "body": body.strip(),
            }
        )
    return commits


def load_compare_metadata(repo: str, previous_tag: str | None, target_commit: str) -> tuple[dict[str, str], list[str]]:
    if not previous_tag:
        return {}, []

    compare_json = json.loads(run(["gh", "api", f"repos/{repo}/compare/{previous_tag}...{target_commit}"]))
    authors_by_sha: dict[str, str] = {}
    contributors: list[str] = []

    for commit in compare_json.get("commits", []):
        sha = (commit.get("sha") or "").strip()
        author = commit.get("author")
        if author and author.get("login"):
            login = f"@{author['login']}"
            authors_by_sha[sha] = login
            if login not in contributors:
                contributors.append(login)
            continue

        commit_author = ((commit.get("commit") or {}).get("author") or {}).get("name")
        if commit_author:
            authors_by_sha[sha] = commit_author
            if commit_author not in contributors:
                contributors.append(commit_author)

    return authors_by_sha, contributors


def load_generated_notes(repo: str, tag: str, target_commit: str, previous_tag: str | None) -> str:
    command = [
        "gh",
        "api",
        f"repos/{repo}/releases/generate-notes",
        "-X",
        "POST",
        "-F",
        f"tag_name={tag}",
        "-F",
        f"target_commitish={target_commit}",
    ]
    if previous_tag:
        command.extend(["-F", f"previous_tag_name={previous_tag}"])

    payload = json.loads(run(command))
    return (payload.get("body") or "").strip()


def extract_issue_refs(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in AUTO_REF_PATTERN.findall(text):
            ref = f"#{match}"
            if ref not in found:
                found.append(ref)

    if found:
        return found

    for text in texts:
        for match in ISSUE_REF_PATTERN.findall(text):
            ref = f"#{match}"
            if ref not in found:
                found.append(ref)
    return found


def build_notes(
    *,
    repo: str,
    tag: str,
    catalog_version: str,
    package_version: str,
    target_commit: str,
    previous_tag: str | None,
) -> str:
    commits = load_git_commits(previous_tag, target_commit)
    authors_by_sha, contributors = load_compare_metadata(repo, previous_tag, target_commit)
    generated_notes = load_generated_notes(repo, tag, target_commit, previous_tag)

    if not contributors:
        for commit in commits:
            label = authors_by_sha.get(commit["sha"]) or commit["author_name"]
            if label not in contributors:
                contributors.append(label)

    lines: list[str] = [
        f"# Catalog {catalog_version}",
        "",
        "## Release Summary",
        f"- Release tag: `{tag}`",
        f"- Source commit: `{target_commit}`",
        f"- Tool package version: `{package_version}`",
        f"- Change window: `{previous_tag}` -> `{target_commit}`" if previous_tag else f"- Change window: initial release snapshot ending at `{target_commit}`",
        "- Assets: `dotnet-skills-manifest.json`, `dotnet-skills-catalog.zip`",
        "",
        "## Contributors In This Window",
    ]

    if contributors:
        lines.extend(f"- {contributor}" for contributor in contributors)
    else:
        lines.append("- No contributor metadata was resolved for this release window.")

    lines.extend(["", "## Merged Commits"])
    if commits:
        for commit in commits:
            sha = commit["sha"][:7]
            author = authors_by_sha.get(commit["sha"]) or commit["author_name"]
            refs = extract_issue_refs(commit["subject"], commit["body"])
            refs_suffix = f" | refs: {', '.join(refs)}" if refs else ""
            lines.append(f"- `{sha}` {commit['subject']} ({author}){refs_suffix}")
    else:
        lines.append("- No commits were detected in the release window.")

    if generated_notes:
        lines.extend(["", "## GitHub Generated Notes", "", generated_notes])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes for catalog-v* releases.")
    parser.add_argument("--repo", required=True, help="GitHub repository, for example managedcode/dotnet-skills")
    parser.add_argument("--tag", required=True, help="Release tag, for example catalog-v2026.3.20.7")
    parser.add_argument("--catalog-version", required=True, help="Catalog version, for example 2026.3.20.7")
    parser.add_argument("--package-version", required=True, help="NuGet package version")
    parser.add_argument("--target-commit", required=True, help="Target commit SHA for the release")
    parser.add_argument("--previous-tag", help="Previous catalog tag")
    parser.add_argument("--output", required=True, help="Markdown file to write")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_notes(
            repo=args.repo,
            tag=args.tag,
            catalog_version=args.catalog_version,
            package_version=args.package_version,
            target_commit=args.target_commit,
            previous_tag=args.previous_tag,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
