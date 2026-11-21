# SPDX-License-Identifier: Apache-2.0
"""git surface BASE: report which refs change what runs or is trusted.

Reads refs on stdin (the first field of each record, so `git footprint BASE` output pipes
straight in), diffs each against its merge base with BASE, and writes
`ref TAB class TAB detail TAB path` records. It reports; it never blocks anything.
"""

import json
import re
import sys

from . import classify
from ._common import (EXIT_ERROR, EXIT_FOUND, EXIT_NOTHING, Fail, check_safe, error, git,
                      git_error, parse_args, read_records, resolve, run, show,
                      usage_and_version, write_record, write_stdout)

USAGE = """usage: git surface [-z] [--json] BASE < refs

For each ref on stdin (the first TAB-separated field of each record), report the changes
since its merge base with BASE that touch what runs or is trusted:
  ref TAB class TAB detail TAB path
  class: agent, ci, deps, exec, hidden, hook, install or repo

Exit status: 0 nothing reported, 1 something reported, 2 error. A ref that shares
no history with BASE is named on stderr and skipped; the others are still reported.

  -z          records end with NUL instead of LF, on input and output
  --json      write the same records as a JSON array of objects with the keys
              ref, class, detail and path
  -h          show this help
  --version   show the version"""

# Flags shared by both diffs; each overrides a setting that could change what is compared.
_DIFF_PINS = ["--no-renames", "--no-ext-diff", "--no-textconv", "--no-relative",
              "--ignore-submodules=none"]

_NULL_OID = re.compile(rb"\A0+\Z")
_HUNK = re.compile(rb"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_C_ESCAPES = {ord("a"): 7, ord("b"): 8, ord("t"): 9, ord("n"): 10, ord("v"): 11,
              ord("f"): 12, ord("r"): 13, ord('"'): 34, ord("\\"): 92}


def merge_base(base_sha, sha, ref):
    """Return the merge base of BASE and a ref, or None if the two share no history.

    Raises:
        Fail: git fails.
    """
    code, out, err = git(["merge-base", base_sha, sha])
    if code == 1 and not out.strip():
        return None
    if code != 0:
        raise Fail("git merge-base failed for %s: %s" % (show(ref), git_error(err, code)))
    return out.split(b"\n")[0].strip()


def raw_changes(mb, sha):
    """Return [(old mode, new mode, old oid, new oid, status, path)] from `git diff --raw`.

    Raises:
        Fail: git fails or prints something that is not raw records.
    """
    code, out, err = git(["diff", "--raw", "-z", "--no-abbrev"] + _DIFF_PINS + [mb, sha])
    if code != 0:
        raise Fail("git diff failed: %s" % git_error(err, code))
    parts = out.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) % 2:
        raise Fail("unexpected git diff output")
    changes = []
    for i in range(0, len(parts), 2):
        # ":100644 100755 OLDOID NEWOID M", then the path as its own field.
        fields = parts[i].lstrip(b":").split(b" ")
        if len(fields) != 5:
            raise Fail("unexpected git diff output")
        changes.append(tuple(fields) + (parts[i + 1],))
    return changes


def _unquote(data, start):
    """Decode the C-quoted string at data[start] (a '"'); return (bytes, index after it)."""
    out = bytearray()
    i = start + 1
    while i < len(data) and data[i] != 0x22:
        byte = data[i]
        if byte == 0x5C and i + 1 < len(data):
            nxt = data[i + 1]
            if 0x30 <= nxt <= 0x37:
                out.append(int(data[i + 1:i + 4], 8))
                i += 4
                continue
            out.append(_C_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(byte)
        i += 1
    return bytes(out), i + 1


def _header_path(line):
    """Return the path named by a `diff --git a/P b/P` header (no renames: both P equal)."""
    rest = line[len(b"diff --git "):]
    if rest.startswith(b'"'):
        path, _ = _unquote(rest, 0)
        return path[2:]
    # Unquoted: "a/P b/P", so P is half of what remains after the prefixes.
    length = (len(rest) - len(b"a/ b/")) // 2
    return rest[2:2 + length]


def added_lines(mb, sha):
    """Return {path: [(new line number, line bytes)]} for every line the diff adds.

    --text makes git show every file's lines whatever .gitattributes says, so marking a file
    binary or -diff cannot hide its content. A typechange may give a path two sections;
    their lines are combined.

    Raises:
        Fail: git fails.
    """
    code, out, err = git(["diff", "-p", "-U0", "--text", "--no-color", "--submodule=short",
                          "--src-prefix=a/", "--dst-prefix=b/", "--diff-algorithm=myers",
                          "--indent-heuristic", "--inter-hunk-context=0"] + _DIFF_PINS + [mb, sha])
    if code != 0:
        raise Fail("git diff failed: %s" % git_error(err, code))
    result = {}
    lines = None
    number = 0
    in_hunk = False
    for line in out.split(b"\n"):
        if line.startswith(b"diff --git "):
            lines = result.setdefault(_header_path(line), [])
            in_hunk = False
            continue
        if lines is None:
            continue
        hunk = _HUNK.match(line)
        if hunk:
            number = int(hunk.group(1))
            in_hunk = True
        elif in_hunk and line.startswith(b"+"):
            lines.append((number, line[1:]))
            number += 1
    return result


def blob(oid, mode):
    """Return a blob's content, or None for an absent file or a submodule (mode 160000)."""
    if _NULL_OID.match(oid) or mode == b"160000":
        return None
    code, out, err = git(["cat-file", "blob", oid])
    if code != 0:
        raise Fail("git cat-file failed: %s" % git_error(err, code))
    return out


def config_files(commit):
    """Return {path: text} for the CI and hook files at a commit.

    Raises:
        Fail: git fails.
    """
    code, out, err = git(["ls-tree", "-r", "-z", "--full-tree", commit])
    if code != 0:
        raise Fail("git ls-tree failed: %s" % git_error(err, code))
    found = {}
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        if kind == b"blob" and classify.path_classes(path) & {"ci", "hook"}:
            found[path] = blob(oid, mode) or b""
    return found


def findings(mb, sha, zero):
    """Return the sorted (class, detail, path) findings for one ref.

    Raises:
        Fail: git fails, or a path cannot be written in LF mode.
    """
    added = added_lines(mb, sha)
    found = set()
    # The CI and hook files at the merge base and at the ref, so a file named by either
    # version is reported.
    configs = config_files(mb)
    for path, text in config_files(sha).items():
        configs[path] = configs.get(path, b"") + b"\n" + text
    for old_mode, new_mode, old_oid, new_oid, status, path in raw_changes(mb, sha):
        check_safe(path, zero, "path")
        status = status.decode("ascii", "replace")
        classes = classify.path_classes(path)
        name = path.rsplit(b"/", 1)[-1]
        lines = added.get(path, [])
        for cls in ("ci", "hook", "agent", "repo", "install"):
            if cls in classes:
                found.add((cls, status, path))
        if not classes & {"ci", "hook"}:
            for cls, names in classify.named_by(path, configs).items():
                found.add((cls, status + " named-in " + " ".join(names), path))
        if name == classify.GITATTRIBUTES:
            drivers = classify.attribute_drivers(lines)
            if drivers:
                found.add(("repo", status + "".join(" " + d for d in drivers), path))
        if "exec" in classes or classify.became_executable(old_mode, new_mode):
            plus_x = " +x" if classify.became_executable(old_mode, new_mode) else ""
            found.add(("exec", status + plus_x, path))
        deps_detail = status
        if name == b"package.json":
            names, scripts = classify.package_json_changes(blob(old_oid, old_mode),
                                                         blob(new_oid, new_mode))
            if names is None:
                found.add(("install", status + " unparsed", path))
            else:
                deps_detail += "".join(" " + word for word in names)
                if scripts:
                    found.add(("install", status + "".join(" scripts." + k for k in scripts),
                               path))
        elif name.lower().startswith(b"requirements") and name.lower().endswith(b".txt"):
            words = classify.requirements_changes(blob(old_oid, old_mode),
                                                  blob(new_oid, new_mode))
            deps_detail += "".join(" " + word for word in words)
        elif name == b"pyproject.toml":
            new_text = blob(new_oid, new_mode)
            words = classify.pyproject_changes(blob(old_oid, old_mode), new_text)
            deps_detail += "".join(" " + word for word in words)
            numbers = set(n for n, _ in lines)
            if numbers and classify.build_system_touched(new_text or b"", numbers):
                found.add(("install", status + " [build-system]", path))
        if "deps" in classes:
            found.add(("deps", deps_detail, path))
        # A NUL byte on an added line marks a binary file: no text checks on it.
        if not any(b"\0" in text for _, text in lines):
            for kind, number in classify.hidden_findings(path, lines).items():
                found.add(("hidden", "%s line %d" % (kind, number), path))
    return sorted(found, key=lambda f: (f[0], f[2], f[1].encode("ascii")))


def _text(name):
    """Decode a ref or path for JSON; bytes that are not UTF-8 become \\udc80-\\udcff.

    surrogateescape keeps every byte, so a reader can recover the original name.
    """
    return name.decode("utf-8", "surrogateescape")


def surface(argv):
    """Run git surface; return the exit code.

    Raises:
        Fail: A usage error, an unknown BASE or ref, or an unsafe name.
    """
    opts, positionals = parse_args(argv, ("-z", "--json", "-h", "--version"))
    if usage_and_version(opts, USAGE):
        return EXIT_NOTHING
    if len(positionals) != 1:
        raise Fail("expected exactly one BASE argument (see -h)")
    zero = bool(opts.get("-z"))
    as_json = bool(opts.get("--json"))
    # JSON escapes TAB, LF and CR, so names LF records cannot hold are written there.
    safe = zero or as_json
    base = positionals[0]
    base_sha = resolve(base)
    refs = []
    seen = set()
    for number, record in read_records(zero):
        # The ref is the first field; the rest (a footprint's status and path) is ignored.
        ref = record.split(b"\t", 1)[0]
        if not ref:
            raise Fail("record %d: empty ref" % number)
        if ref in seen:
            continue
        seen.add(ref)
        try:
            check_safe(ref, safe, "ref")
            refs.append((number, ref, resolve(ref)))
        except Fail as exc:
            raise Fail("record %d: %s" % (number, exc))
    code = EXIT_NOTHING
    skipped = False
    rows = []
    for number, ref, sha in refs:
        try:
            mb = merge_base(base_sha, sha, ref)
            if mb is None:
                # Not fatal: name the ref, report the others, and exit 2 at the end.
                error("%s: no merge base with %s" % (show(ref), show(base)))
                skipped = True
                continue
            for cls, detail, path in findings(mb, sha, safe):
                code = EXIT_FOUND
                if as_json:
                    rows.append({"ref": _text(ref), "class": cls, "detail": detail,
                                 "path": _text(path)})
                else:
                    write_record((ref, cls.encode("ascii"), detail.encode("ascii"), path),
                                 zero)
        except Fail as exc:
            raise Fail("record %d: %s" % (number, exc))
    if as_json:
        write_stdout(json.dumps(rows, indent=2, sort_keys=True).encode("ascii") + b"\n")
    return EXIT_ERROR if skipped else code


def main():
    """Console-script entry point."""
    run(lambda: surface(sys.argv[1:]))


if __name__ == "__main__":
    main()
