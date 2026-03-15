# Two-List Upstream Watch Plan

## Scope

- replace the old fragmented watch config approach with one obvious config file
- keep exactly two human-maintained lists in `.github/upstream-watch.json`: `github_releases` and `documentation`
- let `scripts/upstream_watch.py` normalize the two lists directly at runtime
- remove the generator and fragment files
- update docs, CI, and scheduled automation to match the new shape
- preserve stable watch ids where existing state depends on them

## Out Of Scope

- changing issue formats or scheduling policy
- changing unrelated release or catalog automation

## Steps

1. Move watch normalization logic into `scripts/upstream_watch.py`.
2. Rewrite `.github/upstream-watch.json` to use `github_releases` and `documentation`.
3. Remove fragment files and the old generator.
4. Rewrite README, CONTRIBUTING, AGENTS, and workflows around the two-list model.
5. Run validation, dry-run, and sync-state verification.
6. Commit and push only the relevant changes.
