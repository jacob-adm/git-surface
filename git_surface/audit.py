# SPDX-License-Identifier: Apache-2.0
"""--audit-json: one audit result object (format audit-result/1) for a git surface run.

Each finding keeps the --json record unchanged under "record" and adds a rule id, a fixed
severity for its class, a one-sentence message and the evidence a reader needs to check it.
"""

import re

from . import __version__

FORMAT = "audit-result/1"

# Fixed per class; see docs/commands.md. Nothing here depends on what the change contains.
SEVERITY = {
    "agent": "high", "ci": "high", "hidden": "high", "hook": "high", "install": "high",
    "deps": "medium", "exec": "medium", "repo": "medium",
}

NOUN = {
    "agent": "agent file", "ci": "CI file", "deps": "dependency file",
    "exec": "build or shell file", "hook": "git hook file", "install": "install file",
    "repo": "repository file",
}

VERB = {"A": "adds", "M": "modifies", "D": "deletes", "T": "changes the type of"}

_HIDDEN = re.compile(r"\A(.+) line ([1-9][0-9]*)\Z")


def _what(found):
    """Name a hidden-content kind as reported in the detail, e.g. "<img" or "U+202E"."""
    if found == "<!--":
        return "an HTML comment"
    if found.startswith("</"):
        return "a closing <%s> tag" % found[2:]
    if found.startswith("<"):
        return "an <%s> tag" % found[1:]
    return "the invisible character %s" % found if ".." not in found else \
        "invisible characters in %s" % found


def message(ref, cls, detail, path):
    """Return one sentence that says what the record means."""
    if cls == "hidden":
        match = _HIDDEN.match(detail)
        if match:
            return "%s adds %s to %s at line %s" % (ref, _what(match.group(1)), path,
                                                    match.group(2))
        return "%s adds hidden content to %s: %s" % (ref, path, detail)
    letter, _, rest = detail.partition(" ")
    verb = VERB.get(letter, "changes")
    if rest.startswith("named-in "):
        return "%s %s %s, named in %s %s" % (ref, verb, path, NOUN[cls],
                                             ", ".join(rest.split(" ")[1:]))
    text = "%s %s %s %s" % (ref, verb, NOUN.get(cls, cls + " file"), path)
    if rest == "+x":
        return text + " and makes it executable"
    if rest:
        return text + (": " if cls == "deps" else " (") + rest + ("" if cls == "deps" else ")")
    return text


def finding(row, commit):
    """Return the audit finding for one --json record; COMMIT is the ref's tip commit id."""
    evidence = {"path": row["path"], "ref": row["ref"], "commit": commit}
    if row["class"] == "hidden":
        match = _HIDDEN.match(row["detail"])
        if match:
            evidence["line"] = int(match.group(2))
    return {
        "rule": "git-surface." + row["class"],
        "severity": SEVERITY.get(row["class"], "high"),
        "message": message(row["ref"], row["class"], row["detail"], row["path"]),
        "evidence": evidence,
        "record": row,
    }


def result(name, base, refs, findings, errors):
    """Return the audit result object.

    Args:
        name: The repository's name (its top-level directory).
        base: BASE as given, or None if it was never read.
        refs: The refs given, in order; the target names the ref when there is exactly one.
        findings: Audit findings, in the order of the records.
        errors: Error messages, in the order they were written to stderr.
    """
    target = {"kind": "repository", "name": name}
    if base is not None:
        target["base"] = base
    if len(refs) == 1:
        target["ref"] = refs[0]
    code = 2 if errors else (1 if findings else 0)
    return {
        "format": FORMAT,
        "tool": {"name": "git-surface", "version": __version__},
        "target": target,
        "exit": code,
        "findings": findings,
        "errors": [{"message": m} for m in errors],
    }
