# Limitations and security

## What it does not do

- **It does not enforce.** Exit 1 means "something was reported", not "something is wrong". A
  script may stop on it; that is the caller's choice.
- **It does not judge.** There is no score and no model. A reported workflow change may be a
  routine version bump; an unreported change may still be harmful.
- **Rules are by name.** A script under an unlisted name (say `tools/deploy` without the
  executable bit), a CI system not in the list, or a build step defined inside an unlisted file
  is not reported. A file that a listed file calls, such as a script a workflow runs, is
  reported only if it matches a rule itself.
- **Dependencies are named for `package.json` and `requirements*.txt` only.** Other manifests
  report that they changed, not what was added, removed or re-versioned. In
  `requirements*.txt` only `==` pins give a version change. `pyproject.toml` is read for its
  `[build-system]` table only, line by line, not with a TOML parser. Lockfiles are never read.
- **Hidden HTML is checked in Markdown only**, and only for the tags listed in
  [Classes](classes.md). HTML entities, Markdown link titles, white-on-white styling and
  homoglyphs (look-alike letters) are not checked.
- **Added lines only.** Content that was already on BASE is not reported, even if a branch
  moves it. A deleted file has no added lines, but its path rules still apply (a deleted
  workflow is reported).
- **Renames are not detected.** A renamed file is a deletion and an addition, so its every line
  counts as added.
- **Binary files are skipped** for the content checks, by the presence of a NUL byte on an added
  line. A file that is binary but has no NUL byte is checked as text.
- **Case.** Path rules are case-sensitive except where [Classes](classes.md) says otherwise.

## What it reads and runs

- It runs only `git` (`rev-parse`, `merge-base`, `diff`, `cat-file`), without a shell, with
  `LC_ALL=C`, in the current repository. It never writes to the repository and never runs code
  from it: no hooks, no build, no install.
- It reads blobs only for `package.json`, `pyproject.toml` and `requirements*.txt`, and parses
  `package.json` with Python's `json` module.
- Repository content reaches the output only as paths and as the ASCII detail field; dependency
  names in the detail are limited to a safe character set. On a terminal, control bytes in a
  ref or path are escaped so a crafted name cannot move the cursor or recolour the screen.
- Git configuration that could change which lines count as added (diff algorithm, prefixes,
  colour, submodule format, inter-hunk context, `.gitattributes` diff settings) is overridden on the command line.
