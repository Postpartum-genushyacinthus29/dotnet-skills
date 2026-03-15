#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


USER_AGENT = "dotnet-skills-upstream-watch"
MARKER_RE = re.compile(r"<!-- upstream-watch:id=(?P<watch_id>[^>]+) -->")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


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

    if len(parts) < 2:
        raise ValueError(f"GitHub repository reference must be owner/repo or a GitHub repo URL: {reference}")

    owner, repo = parts[:2]
    return owner, repo


def is_http_url(reference: str) -> bool:
    return reference.startswith("https://") or reference.startswith("http://")


def classify_source(reference: str) -> str:
    if not is_http_url(reference):
        return "github_release"

    parsed = urlparse(reference)
    if parsed.netloc.lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return "github_release"

    return "http_document"


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
    repo_reference = watch.get("source") or watch.get("repo")
    if not isinstance(repo_reference, str) or not repo_reference.strip():
        raise ValueError("github_release watch requires a non-empty source field")

    owner, repo = parse_github_repo_reference(repo_reference)
    normalized: dict[str, Any] = {
        "id": watch.get("id") or f"{slugify(owner)}-{slugify(repo)}-release",
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
    url = watch.get("source") or watch.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("http_document watch requires a non-empty source field")

    return {
        "id": watch.get("id") or default_http_watch_id(url),
        "kind": "http_document",
        "name": watch.get("name") or default_http_watch_name(url),
        "url": url,
        "notes": watch.get("notes") or f"Review the linked skills when {url} changes.",
        "skills": watch.get("skills"),
    }


def validate_labels(labels: list[dict[str, Any]]) -> None:
    names: set[str] = set()
    for label in labels:
        name = label.get("name")
        if not name:
            raise ValueError("Label without name in upstream-watch config")
        if name in names:
            raise ValueError(f"Duplicate label name {name!r} in upstream-watch config")
        names.add(name)


def validate_skills(watch: dict[str, Any]) -> None:
    skills = watch.get("skills")
    if not isinstance(skills, list) or not skills or not all(isinstance(skill, str) and skill for skill in skills):
        raise ValueError(f"Watch {watch.get('id', '<unknown>')} must define a non-empty skills list")


def normalize_human_watch(watch: dict[str, Any], kind: str) -> dict[str, Any]:
    if not isinstance(watch, dict):
        raise ValueError(f"{kind} entries must be JSON objects")
    normalized = normalize_github_release_watch(watch) if kind == "github_release" else normalize_http_document_watch(watch)
    validate_skills(normalized)
    return normalized


def normalize_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    labels = raw_config.get("labels", [])
    if not isinstance(labels, list):
        raise ValueError("labels must be a list")
    validate_labels(labels)

    github_releases = raw_config.get("github_releases", [])
    documentation = raw_config.get("documentation", [])
    if not isinstance(github_releases, list) or not isinstance(documentation, list):
        raise ValueError("github_releases and documentation must both be lists")

    watches: list[dict[str, Any]] = []
    watch_ids: set[str] = set()

    for watch in github_releases:
        normalized = normalize_human_watch(watch, "github_release")
        if normalized["id"] in watch_ids:
            raise ValueError(f"Duplicate watch id {normalized['id']!r} in upstream-watch config")
        watch_ids.add(normalized["id"])
        watches.append(normalized)

    for watch in documentation:
        normalized = normalize_human_watch(watch, "http_document")
        if normalized["id"] in watch_ids:
            raise ValueError(f"Duplicate watch id {normalized['id']!r} in upstream-watch config")
        watch_ids.add(normalized["id"])
        watches.append(normalized)

    return {
        "watch_issue_label": raw_config.get("watch_issue_label", "upstream-update"),
        "labels": labels,
        "watches": watches,
    }


def run_curl(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> tuple[dict[str, str], bytes]:
    headers = headers or {}

    with tempfile.TemporaryDirectory() as tmp:
        headers_path = Path(tmp) / "headers.txt"
        body_path = Path(tmp) / "body.bin"

        cmd = [
            "curl",
            "-fsSL",
            "-A",
            USER_AGENT,
            "-X",
            method,
            "-D",
            str(headers_path),
            "-o",
            str(body_path),
        ]

        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])

        if data is not None:
            cmd.extend(["-H", "Content-Type: application/json", "--data", json.dumps(data)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"curl failed for {url}")

        return parse_headers(headers_path.read_text()), body_path.read_bytes()


def parse_headers(raw_headers: str) -> dict[str, str]:
    blocks = re.split(r"\r?\n\r?\n", raw_headers.strip())
    for block in reversed(blocks):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        parsed: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parsed[key.strip().lower()] = value.strip()
        if parsed:
            return parsed
    return {}


def decode_json(body: bytes) -> Any:
    return json.loads(body.decode("utf-8"))


def gh_api(
    path: str,
    *,
    token: str | None,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> Any:
    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token

    cmd = [
        "gh",
        "api",
        path.lstrip("/"),
        "--method",
        method,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
    ]

    payload = None
    if data is not None:
        cmd.extend(["--input", "-"])
        payload = json.dumps(data)

    result = subprocess.run(cmd, capture_output=True, text=True, input=payload, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh api failed for {path}")

    stdout = result.stdout.strip()
    if not stdout:
        return {}
    return json.loads(stdout)


def human_release(release: dict[str, Any]) -> str:
    tag = release.get("tag_name") or release.get("name") or str(release.get("id"))
    published_at = release.get("published_at")
    if published_at:
        return f"{tag} ({published_at})"
    return tag


def fetch_github_release(watch: dict[str, Any], token: str | None) -> dict[str, Any]:
    releases = gh_api(
        f"/repos/{watch['owner']}/{watch['repo']}/releases?per_page=10",
        token=token,
    )
    if not isinstance(releases, list):
        raise RuntimeError(f"Unexpected release payload for {watch['id']}")

    include_prereleases = bool(watch.get("include_prereleases", False))
    match_tag_regex = watch.get("match_tag_regex")
    exclude_tag_regex = watch.get("exclude_tag_regex")
    selected = None
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prereleases:
            continue
        tag_name = release.get("tag_name") or ""
        if match_tag_regex and not re.search(match_tag_regex, tag_name):
            continue
        if exclude_tag_regex and re.search(exclude_tag_regex, tag_name):
            continue
        selected = release
        break

    if selected is None:
        raise RuntimeError(f"No matching release found for {watch['owner']}/{watch['repo']}")

    return {
        "kind": "github_release",
        "value": selected.get("tag_name") or selected.get("name") or str(selected.get("id")),
        "human": human_release(selected),
        "source_url": selected.get("html_url") or watch.get("source_url"),
        "published_at": selected.get("published_at"),
    }


def extract_title(body: bytes) -> str | None:
    match = re.search(rb"<title>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"\s+", " ", html.unescape(match.group(1).decode("utf-8", errors="ignore"))).strip()
    return title or None


def fetch_http_document(watch: dict[str, Any]) -> dict[str, Any]:
    headers, body = run_curl(watch["url"])
    sha256 = hashlib.sha256(body).hexdigest()
    etag = headers.get("etag")
    last_modified = headers.get("last-modified")
    identifier = etag or last_modified or sha256
    title = extract_title(body)

    detail = []
    if title:
        detail.append(title)
    if etag:
        detail.append(f"ETag {etag}")
    elif last_modified:
        detail.append(f"Last-Modified {last_modified}")
    else:
        detail.append(f"SHA {sha256[:12]}")

    return {
        "kind": "http_document",
        "value": identifier,
        "human": " | ".join(detail),
        "source_url": watch["url"],
        "etag": etag,
        "last_modified": last_modified,
        "title": title,
    }


def fetch_snapshot(watch: dict[str, Any], token: str | None) -> dict[str, Any]:
    kind = watch["kind"]
    if kind == "github_release":
        return fetch_github_release(watch, token)
    if kind == "http_document":
        return fetch_http_document(watch)
    raise RuntimeError(f"Unsupported watch kind: {kind}")


def issue_title(watch: dict[str, Any], snapshot: dict[str, Any]) -> str:
    if watch["kind"] == "github_release":
        return f"Upstream update: {watch['name']} -> {snapshot['value']}"
    return f"Upstream update: {watch['name']} documentation changed"


def issue_body(watch: dict[str, Any], old_snapshot: dict[str, Any] | None, new_snapshot: dict[str, Any]) -> str:
    lines = [
        f"Automation detected an upstream change for **{watch['name']}**.",
        "",
        f"- Watch id: `{watch['id']}`",
        f"- Kind: `{watch['kind']}`",
        f"- Source: {new_snapshot['source_url']}",
        f"- Current value: `{new_snapshot['value']}`",
    ]

    if old_snapshot:
        lines.append(f"- Previous value: `{old_snapshot['value']}`")

    if new_snapshot.get("published_at"):
        lines.append(f"- Published at: `{new_snapshot['published_at']}`")

    lines.extend(
        [
            "",
            "Observed detail:",
            f"- {new_snapshot['human']}",
        ]
    )

    if watch.get("notes"):
        lines.extend(["", "Why this matters:", f"- {watch['notes']}"])

    if watch.get("skills"):
        lines.extend(["", "Likely skills to review:"])
        lines.extend(f"- `{skill}`" for skill in watch["skills"])

    lines.extend(
        [
            "",
            "Suggested follow-up:",
            "- [ ] Review the upstream release notes or documentation diff",
            "- [ ] Update the affected files under `skills/`",
            "- [ ] Update `README.md` if framework coverage or guidance changed",
            "- [ ] Close this issue after the catalog has been refreshed",
            "",
            f"<!-- upstream-watch:id={watch['id']} -->",
            f"<!-- upstream-watch:value={new_snapshot['value']} -->",
        ]
    )
    return "\n".join(lines)


def refresh_comment(watch: dict[str, Any], old_snapshot: dict[str, Any], new_snapshot: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Automation detected another upstream change for this watch.",
            "",
            f"- Watch id: `{watch['id']}`",
            f"- Previous value: `{old_snapshot['value']}`",
            f"- Current value: `{new_snapshot['value']}`",
            f"- Source: {new_snapshot['source_url']}",
        ]
    )


def ensure_labels(repo: str, token: str, labels: list[dict[str, str]], dry_run: bool) -> None:
    if dry_run or not labels:
        return

    existing = gh_api(f"/repos/{repo}/labels?per_page=100", token=token)
    names = {label["name"] for label in existing if isinstance(label, dict)}

    for label in labels:
        if label["name"] in names:
            continue
        gh_api(
            f"/repos/{repo}/labels",
            token=token,
            method="POST",
            data=label,
        )


def find_open_issues(repo: str, token: str, watch_label: str) -> dict[str, dict[str, Any]]:
    issues = gh_api(
        f"/repos/{repo}/issues?state=open&labels={watch_label}&per_page=100",
        token=token,
    )
    indexed: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if issue.get("pull_request"):
            continue
        match = MARKER_RE.search(issue.get("body") or "")
        if match:
            indexed[match.group("watch_id")] = issue
    return indexed


def upsert_issue(
    *,
    repo: str,
    token: str,
    labels: list[str],
    watch: dict[str, Any],
    old_snapshot: dict[str, Any] | None,
    new_snapshot: dict[str, Any],
    open_issues: dict[str, dict[str, Any]],
    dry_run: bool,
) -> str:
    title = issue_title(watch, new_snapshot)
    body = issue_body(watch, old_snapshot, new_snapshot)
    existing = open_issues.get(watch["id"])

    if dry_run:
        action = "update" if existing else "create"
        print(f"[dry-run] Would {action} issue for {watch['id']}: {title}")
        return action

    if existing:
        gh_api(
            f"/repos/{repo}/issues/{existing['number']}/comments",
            token=token,
            method="POST",
            data={"body": refresh_comment(watch, old_snapshot or {"value": "unknown"}, new_snapshot)},
        )
        updated = gh_api(
            f"/repos/{repo}/issues/{existing['number']}",
            token=token,
            method="PATCH",
            data={"title": title, "body": body},
        )
        open_issues[watch["id"]] = updated
        return "update"

    created = gh_api(
        f"/repos/{repo}/issues",
        token=token,
        method="POST",
        data={"title": title, "body": body, "labels": labels},
    )
    open_issues[watch["id"]] = created
    return "create"


def write_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    Path(summary_path).write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor upstream frameworks and docs, then open refresh issues.")
    parser.add_argument("--config", default=".github/upstream-watch.json")
    parser.add_argument("--state", default=".github/upstream-watch-state.json")
    parser.add_argument("--validate-config", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync-state-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    state_path = Path(args.state)

    raw_config = load_json(config_path, default={})
    config = normalize_config(raw_config)
    if args.validate_config:
        summary = [
            "# Upstream Watch Config",
            "",
            f"- Config: `{config_path}`",
            f"- GitHub release watches: `{sum(1 for watch in config['watches'] if watch['kind'] == 'github_release')}`",
            f"- Documentation watches: `{sum(1 for watch in config['watches'] if watch['kind'] == 'http_document')}`",
            f"- Total watches: `{len(config['watches'])}`",
        ]
        print("\n".join(summary))
        write_summary(summary)
        return 0

    state = load_json(state_path, default={"watches": {}})
    prior_watches = state.get("watches", {})

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    watch_label = config.get("watch_issue_label", "upstream-update")
    issue_labels = [label["name"] for label in config.get("labels", [])]

    summary = [
        "# Upstream Watch",
        "",
        f"- Config: `{config_path}`",
        f"- State: `{state_path}`",
        f"- Dry run: `{args.dry_run}`",
        f"- Sync state only: `{args.sync_state_only}`",
    ]

    if (token and repo) and not args.dry_run:
        ensure_labels(repo, token, config.get("labels", []), dry_run=False)
        open_issues = find_open_issues(repo, token, watch_label)
    else:
        open_issues = {}

    next_state: dict[str, Any] = {"watches": {}}
    bootstrapped = 0
    changed = 0
    created = 0
    updated = 0
    errors: list[str] = []

    for watch in config.get("watches", []):
        try:
            snapshot = fetch_snapshot(watch, token)
            next_state["watches"][watch["id"]] = snapshot
            previous = prior_watches.get(watch["id"])

            if previous is None:
                bootstrapped += 1
                summary.append(f"- Bootstrapped `{watch['id']}` with `{snapshot['value']}`")
                continue

            if previous.get("value") == snapshot.get("value"):
                summary.append(f"- No change for `{watch['id']}`")
                continue

            changed += 1
            summary.append(
                f"- Change detected for `{watch['id']}`: `{previous.get('value')}` -> `{snapshot.get('value')}`"
            )

            if args.sync_state_only:
                summary.append(f"- Skipped issue action for `{watch['id']}` because sync-state-only mode is enabled")
                continue

            if not args.dry_run and not repo:
                raise RuntimeError("GITHUB_REPOSITORY is required to create or update issues")

            action = upsert_issue(
                repo=repo or "",
                token=token or "",
                labels=issue_labels,
                watch=watch,
                old_snapshot=previous,
                new_snapshot=snapshot,
                open_issues=open_issues,
                dry_run=args.dry_run,
            )
            if action == "create":
                created += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            message = f"{watch.get('id', 'unknown-watch')}: {exc}"
            errors.append(message)
            summary.append(f"- Error for `{watch.get('id', 'unknown-watch')}`: {exc}")

    if not args.dry_run:
        dump_json(state_path, next_state)

    summary.extend(
        [
            "",
            "## Result",
            "",
            f"- Bootstrapped watches: `{bootstrapped}`",
            f"- Changed watches: `{changed}`",
            f"- Issues created: `{created}`",
            f"- Issues updated: `{updated}`",
            f"- Errors: `{len(errors)}`",
        ]
    )

    write_summary(summary)
    print("\n".join(summary))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
