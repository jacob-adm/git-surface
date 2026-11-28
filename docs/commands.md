# Commands

## git surface [-z] [--json | --audit-json] BASE

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

- `class` is one of `agent`, `ci`, `deps`, `exec`, `hidden`, `hook`, `install`, `repo`; see
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

### JSON output

`--json` writes the same records, in the same order, as one JSON array of objects with the keys
`ref`, `class`, `detail` and `path`, followed by LF. Nothing found is `[]`. For example:

```json
[
  {
    "class": "ci",
    "detail": "M",
    "path": ".github/workflows/test.yml",
    "ref": "agent/ci"
  }
]
```

- JSON escapes TAB, LF and CR, so a ref or path that LF mode refuses is written.
- The output is ASCII. Control characters are escaped (`\t`, `\n`, `\u001b`) and every
  character outside ASCII is written as a `\uXXXX` escape, so the output is safe on a terminal.
- A ref or path that is not valid UTF-8 keeps every byte: each byte that is not part of valid
  UTF-8 is written as `\udc80` to `\udcff` (Python's `surrogateescape`). In Python,
  `path.encode("utf-8", "surrogateescape")` gives back the original bytes.
- `-z` still means NUL-separated input; the output is JSON either way.
- The exit status is the same as without `--json`. With a ref that has no merge base, the array
  holds the other refs' records and the exit status is 2. On any other error nothing is
  written to standard output.

### Audit result output

`--audit-json` writes one JSON object in the audit result format (`audit-result/1`), for a CI
job or an agent that runs several audit tools and reads their results the same way. Each
finding is a `--json` record with what a reader needs to act on it: a rule id, a severity, one
sentence that says what changed, and the evidence to check it. For the `agent/docs` branch of the
[Quick start](../README.md#quick-start), in a repository directory named `demo`
(`echo agent/docs | git surface --audit-json main`):

```json
{
  "errors": [],
  "exit": 1,
  "findings": [
    {
      "evidence": {
        "commit": "ed92b7402339cde08b373e34919b010ead8666c8",
        "line": 4,
        "path": "README.md",
        "ref": "agent/docs"
      },
      "message": "agent/docs adds an HTML comment to README.md at line 4",
      "record": {
        "class": "hidden",
        "detail": "<!-- line 4",
        "path": "README.md",
        "ref": "agent/docs"
      },
      "rule": "git-surface.hidden",
      "severity": "high"
    },
    {
      "evidence": {
        "commit": "ed92b7402339cde08b373e34919b010ead8666c8",
        "line": 5,
        "path": "README.md",
        "ref": "agent/docs"
      },
      "message": "agent/docs adds an <img> tag to README.md at line 5",
      "record": {
        "class": "hidden",
        "detail": "<img line 5",
        "path": "README.md",
        "ref": "agent/docs"
      },
      "rule": "git-surface.hidden",
      "severity": "high"
    }
  ],
  "format": "audit-result/1",
  "target": {
    "base": "main",
    "kind": "repository",
    "name": "demo",
    "ref": "agent/docs"
  },
  "tool": {
    "name": "git-surface",
    "version": "0.4.0"
  }
}
```

| Key | Value |
| --- | --- |
| `format` | `audit-result/1`. |
| `tool` | `git-surface` and its version. |
| `target` | `kind` `repository`; `name`, the name of the repository's top-level directory; `base`, BASE as given; `ref`, only when exactly one ref was read. |
| `exit` | The exit status of the run, 0, 1 or 2. |
| `findings` | One object per record, in the same order as the other outputs. |
| `errors` | One object per error, with the `message` also written to standard error. |

Each finding has:

- `rule`: `git-surface.` and the class, for example `git-surface.ci`.
- `severity`: fixed by the class, never by what the change contains. `high` for `agent`, `ci`,
  `hidden`, `hook` and `install`, which run code or instruct an agent or hide text from a
  reviewer; `medium` for `deps`, `exec` and `repo`. One exception: a `ci` or `hook` record for a
  file named in a CI or hook file (`named-in`) takes its severity from what the named file is:
  `medium` for a dependency file (the parts of it that run on install are reported as `install`,
  `high`), `low` for a documentation or image file (`.md`, `.markdown`, `.mdx`, `.rst`, `.txt`,
  `.adoc`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.ico`), and `high` for anything
  else, an install or build or shell file included. In `hidden`, an `<img local` record is
  `low` and an `<img external` record `medium`; every other hidden kind is `high`.
- `message`: the ref, what it does to the file (`adds`, `modifies`, `deletes` or `changes the
  type of`), the kind of file and its path, then what the detail adds: the dependency words for
  `deps`, `and makes it executable` for `+x`, the files that name it for `named-in`, or the
  attributes and scripts in parentheses. For `hidden`, what was added and its line.
- `evidence`: `path` and `ref` from the record; `commit`, the full id of the commit the ref named
  when it was read; and, for `hidden`, `line`, the line in the new file.
- `record`: the `--json` record, unchanged.

The object is written on every run, also on an error, so a reader always gets one object:

- A ref with no merge base is an entry in `errors`; the other refs' findings are kept and the
  exit status is 2.
- Any other error (an unknown BASE or ref, a name that cannot be written, a usage error such as
  `--json` with `--audit-json`) stops the run: `findings` is empty, `errors` holds the message
  and the exit status is 2.

Names are written as in [JSON output](#json-output): ASCII with `\uXXXX` escapes, and bytes that
are not UTF-8 kept as `\udc80` to `\udcff`.

### Options

- `-z`: records end with NUL instead of LF, on input and output. With `--json` or
  `--audit-json`, input only.
- `--json`: write the records as a JSON array; see [JSON output](#json-output).
- `--audit-json`: write one audit result object; see [Audit result output](#audit-result-output).
- `-h`: show usage.
- `--version`: show the version.

Any other argument, even one starting with `-`, is BASE. `--` ends option parsing.

### Exit status

Like `grep`: 0 ran and reported nothing, 1 ran and reported something, 2 error. Errors are one
line on standard error, `git-surface: <message>`; an error about an input record starts with
`record N: `. Errors include an unknown BASE or ref and a missing or extra BASE. A reader that
closes the pipe early (`| head`) is not an error.

A ref that shares no history with BASE (an orphan branch, say) has nothing to diff against. It
does not stop the run: it is named on standard error as `git-surface: REF: no merge base with
BASE`, escaped like every other error, and the other refs are still reported. The exit status
is then 2, whatever else was reported, so a script cannot mistake a partial report for a whole
one.

### The diff

Both diffs `git surface` runs are pinned so that user configuration cannot change the result:
renames off (a rename is a deletion and an addition), no external diff or textconv, paths
relative to the root, submodule changes included, no colour, fixed prefixes, the default diff
algorithm, no context lines between hunks. `--text` is passed, so a `.gitattributes` entry that marks a file `binary` or `-diff`
does not hide its added lines. git runs without a shell and with `LC_ALL=C`.
