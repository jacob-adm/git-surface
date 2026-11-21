# SPDX-License-Identifier: Apache-2.0
"""The classes git surface reports, as pure functions of paths, modes and content.

Nothing here runs git. docs/classes.md lists every rule below in prose; keep them together.
"""

import json
import re

# --- Path rules -------------------------------------------------------------------------

# ci: files a CI service runs.
CI_PREFIXES = (b".github/workflows/", b".github/actions/", b".gitea/workflows/",
               b".forgejo/workflows/", b".gitlab/ci/", b".circleci/", b".buildkite/",
               b".woodpecker/", b".azure-pipelines/")
CI_ROOT_FILES = {b".gitlab-ci.yml", b".travis.yml", b"azure-pipelines.yml",
                 b"azure-pipelines.yaml", b"bitbucket-pipelines.yml", b".drone.yml",
                 b".woodpecker.yml", b"appveyor.yml", b".appveyor.yml", b"cloudbuild.yaml",
                 b"cloudbuild.yml", b"action.yml", b"action.yaml"}
CI_NAMES = {b"Jenkinsfile"}

# hook: files a git hook manager runs on a developer's machine.
HOOK_PREFIXES = (b".githooks/", b".husky/")
HOOK_ROOT_FILES = {b".pre-commit-config.yaml", b".pre-commit-hooks.yaml", b"lefthook.yml",
                   b"lefthook.yaml", b".lefthook.yml", b".lefthook.yaml",
                   b"lefthook-local.yml"}

# agent: files a coding agent or an editor runs, or reads as instructions.
AGENT_PREFIXES = (b".claude/", b".cursor/", b".devcontainer/")
AGENT_ROOT_FILES = {b".mcp.json", b".cursorrules", b".windsurfrules", b".devcontainer.json",
                    b".vscode/tasks.json", b".vscode/mcp.json",
                    b".github/copilot-instructions.md"}
AGENT_NAMES = {b"AGENTS.md", b"CLAUDE.md", b"GEMINI.md"}

# install: code that runs when the project is installed or built as a dependency, or when
# Python starts.
INSTALL_NAMES = {b"setup.py", b"sitecustomize.py", b"usercustomize.py", b"binding.gyp",
                 b"build.rs"}
INSTALL_SUFFIXES = (b".pth",)
# npm runs these scripts on install, or when a package is installed from git.
NPM_LIFECYCLE = ("preinstall", "install", "postinstall", "prepare", "prepack", "postpack",
                 "prepublish")

# deps: dependency manifests and lockfiles.
DEPS_NAMES = {b"package.json", b"package-lock.json", b"npm-shrinkwrap.json", b"yarn.lock",
              b"pnpm-lock.yaml", b"bun.lock", b"bun.lockb", b"Pipfile", b"Pipfile.lock",
              b"poetry.lock", b"uv.lock", b"pdm.lock", b"pyproject.toml", b"setup.cfg",
              b"constraints.txt", b"Cargo.toml", b"Cargo.lock", b"go.mod", b"go.sum",
              b"Gemfile", b"Gemfile.lock", b"composer.json", b"composer.lock", b"pom.xml",
              b"build.gradle", b"build.gradle.kts", b"gradle.lockfile",
              b"packages.lock.json"}
DEPS_SUFFIXES = (b".gemspec",)

# exec: build and shell files that run commands.
EXEC_NAMES = {b"Makefile", b"makefile", b"GNUmakefile", b"Dockerfile", b"Containerfile",
              b"justfile", b"Justfile", b".envrc", b"docker-compose.yml",
              b"docker-compose.yaml", b"compose.yml", b"compose.yaml"}
EXEC_SUFFIXES = (b".sh", b".bash", b".zsh", b".ps1", b".bat", b".cmd", b".mk", b".dockerfile")
EXEC_MODE = b"100755"

# hidden: Markdown files get the HTML check; every text file gets the character check.
MARKDOWN_SUFFIXES = (b".md", b".markdown", b".mdx")
HTML = re.compile(rb"<!--|<\s*/?\s*(img|picture|source|svg|script|style|iframe|object|embed"
                  rb"|link|meta|base|form|input|details)(?![A-Za-z0-9-])", re.I)

# Invisible and bidirectional characters, as (first, last, label). A range is reported once
# under its label; a single character under its own code point.
HIDDEN_CHARS = (
    (0x200B, 0x200F, None),  # zero-width space, ZWNJ, ZWJ, LRM, RLM
    (0x2060, 0x2064, None),  # word joiner and invisible operators
    (0xFEFF, 0xFEFF, None),  # zero-width no-break space (BOM) after the start of a file
    (0x061C, 0x061C, None),  # Arabic letter mark
    (0x202A, 0x202E, None),  # bidi embeddings and overrides
    (0x2066, 0x2069, None),  # bidi isolates
    (0xE0000, 0xE007F, "U+E0000..U+E007F"),  # tag characters
    (0xE0100, 0xE01EF, "U+E0100..U+E01EF"),  # supplementary variation selectors
)
_HIDDEN_RE = re.compile("[%s]" % "".join(
    "\\U%08x-\\U%08x" % (first, last) for first, last, _ in HIDDEN_CHARS))


def _basename(path):
    """Return the last component of a slash-separated path."""
    return path.rsplit(b"/", 1)[-1]


def path_classes(path):
    """Return the set of classes a changed path is in by its name alone.

    Args:
        path: The path relative to the repository root, bytes.

    Returns:
        A set drawn from "ci", "hook", "agent", "install", "deps", "exec".
    """
    name = _basename(path)
    lower = name.lower()
    found = set()
    if path.startswith(CI_PREFIXES) or path in CI_ROOT_FILES or name in CI_NAMES:
        found.add("ci")
    if path.startswith(HOOK_PREFIXES) or path in HOOK_ROOT_FILES:
        found.add("hook")
    if path.startswith(AGENT_PREFIXES) or path in AGENT_ROOT_FILES or name in AGENT_NAMES:
        found.add("agent")
    if name in INSTALL_NAMES or lower.endswith(INSTALL_SUFFIXES):
        found.add("install")
    if (name in DEPS_NAMES or lower.endswith(DEPS_SUFFIXES)
            or (lower.startswith(b"requirements") and lower.endswith(b".txt"))):
        found.add("deps")
    if (name in EXEC_NAMES or name.startswith(b"Dockerfile.")
            or lower.endswith(EXEC_SUFFIXES)):
        found.add("exec")
    return found


def became_executable(old_mode, new_mode):
    """Return True if a file's mode is executable now and was not before (or is new)."""
    return new_mode == EXEC_MODE and old_mode != EXEC_MODE


def is_markdown(path):
    """Return True if the path names a Markdown file, by extension, case-insensitively."""
    return path.lower().endswith(MARKDOWN_SUFFIXES)


# --- Content rules ----------------------------------------------------------------------

def hidden_findings(path, added):
    """Return {kind: first line number} for hidden content on added lines.

    Args:
        path: The path, bytes; Markdown files also get the HTML check.
        added: [(new line number, line bytes)] in line order.

    Returns:
        A dict from a kind ("<img", "<!--", "U+202E", or a range label) to the line number
        of its first occurrence.
    """
    found = {}
    markdown = is_markdown(path)
    for number, line in added:
        if markdown:
            for match in HTML.finditer(line):
                tag = match.group(1)
                kind = "<" + tag.decode("ascii").lower() if tag else "<!--"
                found.setdefault(kind, number)
        text = line.decode("utf-8", "replace")
        for match in _HIDDEN_RE.finditer(text):
            code = ord(match.group(0))
            # A byte-order mark as the very first character of a file is ordinary.
            if code == 0xFEFF and number == 1 and match.start() == 0:
                continue
            found.setdefault(_char_kind(code), number)
    return found


def _char_kind(code):
    """Return the report label for a hidden character: its code point or its range."""
    for first, last, label in HIDDEN_CHARS:
        if first <= code <= last and label:
            return label
    return "U+%04X" % code


def build_system_touched(new_text, added_numbers):
    """Return True if an added line of pyproject.toml lies in its [build-system] table.

    Tables are tracked line by line from their `[name]` headers; this is not a TOML parser.

    Args:
        new_text: The new file content, bytes.
        added_numbers: The set of added line numbers.
    """
    table = b""
    for number, line in enumerate(new_text.split(b"\n"), 1):
        header = re.match(rb"\s*\[\[?\s*([^\]\s]+)\s*\]", line)
        if header:
            table = header.group(1)
        if number in added_numbers and (table == b"build-system"
                                        or table.startswith(b"build-system.")):
            return True
    return False


# Names and versions printed in a detail field: printable, no spaces, so each stays one word.
# A name starts with a letter, digit or @, so "-name" (removed) cannot be misread; a version
# may not contain "->", which separates the old version from the new.
_SAFE_NAME = re.compile(r"\A[A-Za-z0-9@][A-Za-z0-9@/._~-]*\Z")
_SAFE_VERSION = re.compile(r"\A(?!.*->)[A-Za-z0-9@/._~^<>=*+:!-]+\Z")
# One == pin, optionally followed by an environment marker, a line continuation or options
# such as --hash.
_PIN = re.compile(r"\A==\s*([^\s,;=\\]+)\s*(?:[;\\].*|--.*)?\Z")


def dependency_changes(old, new):
    """Return the detail words for two {name: version or None} maps.

    "+name" for each added name, "-name" for each removed one, then "name old->new" for each
    name whose version changed while both versions are known. Each group is sorted. A name or
    version with characters outside the safe sets is left out.
    """
    names = sorted(name for name in set(old) | set(new) if _SAFE_NAME.match(name))
    words = ["+" + name for name in names if name not in old]
    words += ["-" + name for name in names if name not in new]
    for name in names:
        before, after = old.get(name), new.get(name)
        if (name in old and name in new and before != after
                and all(isinstance(v, str) and _SAFE_VERSION.match(v) for v in (before, after))):
            words.append("%s %s->%s" % (name, before, after))
    return words


def _load_json(text):
    """Return the JSON object in TEXT, {} for an absent file, or None if it is not one."""
    if text is None:
        return {}
    try:
        data = json.loads(text.decode("utf-8"))
    except (ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def package_json_changes(old_text, new_text):
    """Compare two versions of a package.json.

    Args:
        old_text: The old content (bytes), or None if the file is new.
        new_text: The new content (bytes), or None if the file was deleted.

    Returns:
        (dependency detail words, changed lifecycle script keys), both sorted lists; or
        (None, None) if either side is not a JSON object.
    """
    old, new = _load_json(old_text), _load_json(new_text)
    if old is None or new is None:
        return None, None

    def deps(data):
        # A name in several sections takes its version from the first section listing it.
        found = {}
        for key in ("dependencies", "devDependencies", "optionalDependencies",
                    "peerDependencies"):
            section = data.get(key)
            if isinstance(section, dict):
                for name, version in section.items():
                    found.setdefault(name, version)
        return found

    def scripts(data):
        section = data.get("scripts")
        return section if isinstance(section, dict) else {}

    old_scripts, new_scripts = scripts(old), scripts(new)
    changed = [key for key in NPM_LIFECYCLE if old_scripts.get(key) != new_scripts.get(key)]
    return dependency_changes(deps(old), deps(new)), sorted(changed)


def _requirements(text):
    """Return {normalised project name: == pin or None} for a requirements file.

    The first line naming a project wins.
    """
    found = {}
    if text is None:
        return found
    for line in text.decode("utf-8", "replace").splitlines():
        line = line.split("#", 1)[0].strip()
        # Options (-r, -e, --hash, ...) and URLs are not names.
        match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*", line)
        if match and not line.startswith("-") and not re.match(r"[A-Za-z0-9+.-]+://", line):
            # PEP 503 normalisation, so "Foo_Bar" and "foo-bar" are the same project.
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            pin = _PIN.match(line[match.end():])
            found.setdefault(name, pin.group(1) if pin else None)
    return found


def requirements_changes(old_text, new_text):
    """Return the dependency detail words for two versions of a requirements file.

    A version change is reported only when both versions pin the project with one `==`.
    """
    return dependency_changes(_requirements(old_text), _requirements(new_text))
