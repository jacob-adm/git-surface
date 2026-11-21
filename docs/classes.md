# Classes

The list is fixed. A path is in a class because of its name, its mode or the lines a branch
adds to it; nothing is guessed from what the code does. Path rules match the path relative to
the repository root; "anywhere" means the file name in any directory.

## ci: what a CI service runs

- Anything under `.github/workflows/`, `.github/actions/`, `.gitea/workflows/`,
  `.forgejo/workflows/`, `.gitlab/ci/`, `.circleci/`, `.buildkite/`, `.woodpecker/`,
  `.azure-pipelines/`.
- At the root: `.gitlab-ci.yml`, `.travis.yml`, `azure-pipelines.yml`, `azure-pipelines.yaml`,
  `bitbucket-pipelines.yml`, `.drone.yml`, `.woodpecker.yml`, `appveyor.yml`, `.appveyor.yml`,
  `cloudbuild.yaml`, `cloudbuild.yml`, `action.yml`, `action.yaml`.
- Anywhere: `Jenkinsfile`.

Detail: the status letter.

## hook: what a git hook manager runs on a developer's machine

- Anything under `.githooks/` or `.husky/`.
- At the root: `.pre-commit-config.yaml`, `.pre-commit-hooks.yaml`, `lefthook.yml`,
  `lefthook.yaml`, `.lefthook.yml`, `.lefthook.yaml`, `lefthook-local.yml`.

Detail: the status letter.

## agent: what a coding agent or an editor runs, or reads as instructions

- Anything under `.claude/` (settings, hooks, commands, subagents, skills), `.cursor/` (rules and
  MCP servers) or `.devcontainer/` (commands run when the container is created).
- At the root: `.mcp.json`, `.cursorrules`, `.windsurfrules`, `.devcontainer.json`,
  `.vscode/tasks.json` (tasks can run when the folder is opened), `.vscode/mcp.json`,
  `.github/copilot-instructions.md`.
- Anywhere: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`.

Detail: the status letter.

## repo: what git fetches or runs, and who reviews

- At the root: `.gitmodules` (where each submodule is fetched from).
- `CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS` (who must review), and
  `.github/dependabot.yml`, `.github/dependabot.yaml` (what is updated automatically).
  Detail: the status letter.
- `.gitattributes`, anywhere, when an added line sets a `diff`, `filter` or `merge` attribute to a
  driver (`*.py filter=x`): git runs the command configured for that driver on the matching
  files. Lines that start with `#` are not read. Drivers that run no command from the
  repository's configuration are left out: `lfs` (Git LFS) and git's own drivers (`python`,
  `golang`, `cpp` and the other built-in diff drivers, and `text`, `binary`, `union`). Detail: the status letter and each attribute
  set, for example `M filter`.

## install: what runs when the project is installed or built, or when Python starts

- Anywhere: `setup.py`, `sitecustomize.py`, `usercustomize.py`, `binding.gyp` (npm builds it on
  install), `build.rs` (Cargo runs it on build), and any `*.pth` file.
  Detail: the status letter.
- `pyproject.toml` when an added line is inside its `[build-system]` table (the build backend
  and its requirements). Detail: `M [build-system]` (or `A`).
- `package.json` when one of the npm scripts `preinstall`, `install`, `postinstall`, `prepare`,
  `prepack`, `postpack` or `prepublish` is added, changed or removed. Detail: the status letter
  and each such script, for example `M scripts.postinstall`.
- `package.json` when either version is not a JSON object (or is nested too deeply for Python's
  JSON parser), so its scripts cannot be compared. A submodule at a manifest path has no content
  to read and counts as an empty file.
  Detail: the status letter and `unparsed`, for example `M unparsed`.

## deps: dependency manifests and lockfiles

- Anywhere: `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
  `pnpm-lock.yaml`, `bun.lock`, `bun.lockb`, `Pipfile`, `Pipfile.lock`, `poetry.lock`,
  `uv.lock`, `pdm.lock`, `pyproject.toml`, `setup.cfg`, `constraints.txt`, `Cargo.toml`,
  `Cargo.lock`, `go.mod`, `go.sum`, `Gemfile`, `Gemfile.lock`, `composer.json`,
  `composer.lock`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradle.lockfile`,
  `packages.lock.json`, any `*.gemspec`, and any `requirements*.txt`.

Detail: the status letter, then, where the file is cheap to read, one word for each added or
removed dependency and two for each version change:

- `+NAME`: a dependency the old version did not have (every one, for a new file);
- `-NAME`: a dependency the new version no longer has (every one, for a deleted file);
- `NAME OLD->NEW`: a dependency both versions have, whose version changed.

They come in that order, `+` words, then `-` words, then version changes, each group sorted by
name, for example `M +left-pad -lodash express 4.18.2->4.19.2`. Which files are read:

- `package.json`: names in `dependencies`, `devDependencies`, `optionalDependencies` and
  `peerDependencies`. A name in several of them takes its version from the first in that
  order. Any change of the version string is a version change, so a range shows as written
  (`^1.0.0->^1.2.0`).
- `requirements*.txt`: project names, normalised (lower case, runs of `-_.` as `-`). A version
  change is reported only when both versions pin the project with a single `==` (an
  environment marker, a trailing `\` or options such as `--hash` may follow the pin); a change
  to or from a range shows no version words. The first line naming a project counts. Option
  lines (`-r`, `-e`, ...) and URL lines are skipped.
- `pyproject.toml`: `dependencies` in `[project]` and every list in
  `[project.optional-dependencies]` and `[dependency-groups]`, read as requirements are (an
  `include-group` entry is not a name); and Poetry's `[tool.poetry.dependencies]`,
  `[tool.poetry.dev-dependencies]` and `[tool.poetry.group.NAME.dependencies]`, where any change
  of a version string is a version change and the `python` key is not a dependency.

A name must start with a letter, a digit or `@` and contain only `A-Z a-z 0-9 @ / . _ ~ -`; a
version may contain only those and `^ < > = * + : !`, and not `->`. Other names, and version
changes with other versions (a range with spaces, a version that is not a string), are left out
of the detail, so every word is printable ASCII without spaces. Other manifests and every
lockfile report the status letter only.

To list the version changes as `NAME TAB OLD TAB NEW`, one per line, for a tool that fetches a
package by name and version (such as `release-drift fetch`):

```sh
git surface main < refs | awk -F'\t' '$2 == "deps" {
    n = split($3, w, " ")
    for (i = 2; i < n; i++) if (w[i] !~ /^[+-]/ && w[i+1] ~ /->/) {
        split(w[i+1], v, "->"); print w[i] "\t" v[1] "\t" v[2]; i++
    }
}'
```

A pinned requirement gives exact versions; a `package.json` range must be resolved to a version
first.

## exec: build and shell files, and files that become executable

- Anywhere: `Makefile`, `makefile`, `GNUmakefile`, `Dockerfile`, `Dockerfile.*`,
  `Containerfile`, `justfile`, `Justfile`, `.envrc`, `docker-compose.yml`,
  `docker-compose.yaml`, `compose.yml`, `compose.yaml`, and files ending in `.sh`, `.bash`,
  `.zsh`, `.ps1`, `.bat`, `.cmd`, `.mk` or `.dockerfile` (case-insensitive).
- Any file whose mode becomes `100755` (executable): a new executable file, or a mode change.

Detail: the status letter, then ` +x` if the file became executable, for example `A +x` or
`M +x`.

## hidden: content a human reader may not see

Only lines the branch adds are checked; a removed line is never reported. A file with a NUL
byte on an added line is treated as binary and not checked.

- In Markdown files (`*.md`, `*.markdown`, `*.mdx`, case-insensitive): an HTML comment `<!--`,
  or an opening or closing tag `img`, `picture`, `source`, `svg`, `script`, `style`, `iframe`,
  `object`, `embed`, `link`, `meta`, `base`, `form`, `input` or `details`, in any case. Tags in
  fenced code blocks count too.
- In every text file, these characters:
  - zero-width and directional marks: U+200B to U+200F, U+2060 to U+2064, U+FEFF (except as
    the first character of a file), U+061C;
  - bidirectional embeddings, overrides and isolates: U+202A to U+202E, U+2066 to U+2069;
  - tag characters U+E0000 to U+E007F, reported as one kind, `U+E0000..U+E007F`;
  - supplementary variation selectors U+E0100 to U+E01EF, reported as one kind,
    `U+E0100..U+E01EF`;
  - variation selectors U+FE00 to U+FE0F, reported as one kind, `U+FE00..U+FE0F`, when one
    follows an ASCII character or the start of a line, or when two or more stand together. A
    single selector after any other character, as in an emoji such as U+2764 U+FE0F, is
    ordinary text and is not reported;
  - other characters that show nothing: U+00AD soft hyphen, U+034F combining grapheme joiner,
    U+115F to U+1160 and U+3164 and U+FFA0 Hangul fillers, U+17B4 to U+17B5 Khmer inherent
    vowels, U+180B to U+180F Mongolian variation selectors and vowel separator, U+2028 to U+2029
    line and paragraph separators, U+206A to U+206F deprecated format characters, U+2800
    Braille pattern blank, U+FFF9 to U+FFFB interlinear annotation, U+1BCA0 to U+1BCA3
    shorthand format controls, U+1D173 to U+1D17A musical formatting characters.

Detail: what was found and the line, in the new file, of its first occurrence, for example
`<img line 12`, `<!-- line 3` or `U+202E line 40`. A file has one line per kind found.

U+200D (zero-width joiner) is part of many emoji, so an added emoji can be reported. That is
expected: the report says what is there, not whether it is harmful.
