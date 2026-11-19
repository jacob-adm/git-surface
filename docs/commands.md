# Commands

## git surface [-z] BASE

For each ref on standard input, reports the changes since its merge base with BASE that touch
what runs or is trusted. It runs in the repository of the current directory and never changes a
ref, the index, the worktree or the object store.

### Input

One record per line. The ref is everything before the first TAB; the rest of the record is
ignored. So both of these work:

```sh
git for-each-ref --format='%(refname:short)' refs/heads/agent/ | git surface main
git for-each-ref --format='%(refname:short)' refs/heads/agent/ | git footprint main | git surface main
```

The second form takes `git footprint` output (`ref TAB status TAB path`) as it is. `git surface`
does not use the paths in it: it runs its own diff for each ref, so the report is complete for
that ref even if the records were filtered.

- A ref is any commit-ish (`main`, `origin/x`, a commit id, `HEAD~2`), printed exactly as given.
  A ref repeated in the input is reported once, at its first occurrence.
- A trailing CR on a line is removed and empty lines are skipped.
- BASE and every ref are resolved before any diff runs. A range such as `a..b` is not a ref.

### Output

```
ref TAB class TAB detail TAB path
```

- `class` is one of `ci`, `deps`, `exec`, `hidden`, `hook`, `install`; see
  [Classes](classes.md).
- `detail` is printable ASCII and starts with git's status letter (`A` added, `M` modified, `D`
  deleted, `T` type changed) for every class except `hidden`, whose detail names what was found
  and the line it was first found on. [Classes](classes.md) lists every detail.
- `path` is relative to the repository root, whatever directory the command runs in. It is last,
  so in `-z` mode a path may itself contain TAB.
- A path can be in several classes and then has one line per class.
- Refs keep their input order. Within a ref, lines are sorted by class, then path, then detail,
  bytewise. The same repository and the same input give byte-identical output.
- In LF mode, a ref or path holding TAB, LF or CR cannot be written as a line: the command exits
  2 with a message naming `-z`. Output to a pipe or file is never quoted or escaped. On a
  terminal, control bytes and bytes that are not valid UTF-8 are shown as `\xHH`.

To keep only the ref, class and path: `cut -f1,2,4`. To count findings per branch:
`cut -f1 | uniq -c`.

### Options

- `-z`: records end with NUL instead of LF, on input and output.
- `-h`: show usage.
- `--version`: show the version.

Any other argument, even one starting with `-`, is BASE. `--` ends option parsing.

### Exit status

Like `grep`: 0 ran and reported nothing, 1 ran and reported something, 2 error. Errors are one
line on standard error, `git-surface: <message>`; an error about an input record starts with
`record N: `. Errors include an unknown BASE or ref, a missing or extra BASE, and a ref that
shares no history with BASE (`no merge base`). A reader that closes the pipe early (`| head`) is
not an error.

### The diff

Both diffs `git surface` runs are pinned so that user configuration cannot change the result:
renames off (a rename is a deletion and an addition), no external diff or textconv, paths
relative to the root, submodule changes included, no colour, fixed prefixes, the default diff
algorithm, no context lines between hunks. `--text` is passed, so a `.gitattributes` entry that marks a file `binary` or `-diff`
does not hide its added lines. git runs without a shell and with `LC_ALL=C`.
