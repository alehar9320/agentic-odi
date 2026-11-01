# Vendored files and their ledger

A copied component is a dependency nobody chose deliberately. It arrives with a
licence, an upstream revision, and whatever the copier changed on the way in. The
ledger at `apps/studio/vendor.lock.json` records all three, and
`scripts/vendor_policy.py` fails when the record and the tree disagree.

## What counts as vendored

Any TypeScript source under `apps/studio/src/vendor/components/` — the surface
copy-in commands write to — plus any other source in that tree that carries a
`// vendored:` header. Tests and the tree's own helpers are not copies, so they
are not audited: an entry for a file nobody copied would be a provenance record
no reviewer could check.

## The header

The first line of every copied file states where it came from:

```
// vendored: <upstream url>@<revision> — <SPDX> — local edits: <none|what>
```

The revision is whatever the copy tool pinned: a commit hash for a git checkout,
the CLI version for a registry fetch. `latest` and `unknown` are refused — a
record that cannot be re-fetched is not a record. `local edits` says what the
copier changed after the copy; `none` is a valid answer, an empty field is not.

## The ledger

```
{
  "files": [
    {"path", "upstream", "commit", "copied_at", "spdx", "local_edits"}
  ],
  "packages": [{"name", "spdx", "why"}]
}
```

`path` is relative to `apps/studio/src/vendor`, and entries are sorted by path so
that adding one file changes one line. The policy test checks six things: every
audited file has an entry, every entry has a file, no path appears twice, the
list is sorted, each `spdx` is on the allowlist (MIT, Apache-2.0, BSD-2-Clause,
ISC, 0BSD), and each header's upstream, revision, and licence match its entry.

`packages` covers the dependencies the copying pulled in rather than the files it
wrote. Each one has to be a real dependency of the Studio and say why it is here:
the class-merging helpers the copied components call, the variant builder, the
Radix primitives a copied button reads through, and the Tailwind compiler and its
Vite plugin. The boundary rules for the same tree live in the vendor-tree doc that
issue #386 introduces.

## Refreshing a copy

```bash
cd apps/studio
npx --yes shadcn@latest add button   # writes to src/vendor/components/ui/
uv run python scripts/vendor_policy.py
```

Change the header and the ledger entry in the same commit as the file; the policy
test names whichever one went stale.
