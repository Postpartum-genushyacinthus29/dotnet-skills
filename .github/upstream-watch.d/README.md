# upstream-watch fragments

This directory is the human-maintained source of truth for upstream monitoring.

Why the name ends with `.d`:

- `.d` is a common convention for a directory full of config fragments
- each file here is a small drop-in piece of the final generated config
- the repository then builds those pieces into `../upstream-watch.json`

Use it when you want this repository to notice:

- a new GitHub release for a framework or library
- a meaningful change to an official documentation page

Do not edit `../upstream-watch.json` directly.
That file is generated from the fragments in this folder.

## Which Fragment Should I Use?

Use these conventions:

- `00-metadata.json` for labels and shared watcher metadata
- `10-microsoft-releases.json` for Microsoft and official .NET GitHub release feeds
- `20-managedcode-releases.json` for ManagedCode repositories
- `30-docs.json` for documentation pages
- `40-<vendor>.json` for any other vendor or project family

If an existing fragment does not fit, create a new vendor-specific one instead of bloating another file.

## Watch Types

For GitHub release feeds, keep the human-authored fragment minimal:

```json
{
  "repo": "https://github.com/myvendor/MyProject",
  "skills": [
    "dotnet-myproject"
  ]
}
```

That is enough for automation.
`scripts/generate_upstream_watch.py` derives `id`, `kind`, `name`, `owner`, `repo`, and a default `notes` value.

Add extra fields only when needed:

- `match_tag_regex`
- `exclude_tag_regex`
- `include_prereleases`
- `notes`

Use `http_document` or a simple `url` entry for stable docs pages:

```json
{
  "url": "https://learn.microsoft.com/example/myproject/overview",
  "skills": [
    "dotnet-myproject"
  ]
}
```

For documentation watches, the generator can derive `id`, `kind`, `name`, and default `notes` too.
Keep explicit `name` or `notes` only when the default wording would be unclear.

Add `match_tag_regex` when a repo publishes multiple release streams and you only want one of them.

If the watch is for a specific library or project, map it to the dedicated project skill.
Do not point a concrete library watch at umbrella skills such as `dotnet` or `dotnet-architecture` just because the dedicated skill does not exist yet.

## Required Follow-Up Commands

After editing fragments:

```bash
python3 scripts/generate_upstream_watch.py
python3 scripts/generate_upstream_watch.py --check
python3 scripts/upstream_watch.py --sync-state-only
python3 scripts/upstream_watch.py --dry-run
```

Use them in this order:

1. regenerate the root config
2. verify it is in sync
3. record a fresh baseline without opening issues
4. preview what the next real watcher run would do
