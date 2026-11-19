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

## install: what runs when the project is installed or built, or when Python starts

- Anywhere: `setup.py`, `sitecustomize.py`, `usercustomize.py`, `binding.gyp` (npm builds it on
  install), `build.rs` (Cargo runs it on build), and any `*.pth` file.
  Detail: the status letter.
- `pyproject.toml` when an added line is inside its `[build-system]` table (the build backend
  and its requirements). Detail: `M [build-system]` (or `A`).
- `package.json` when one of the npm scripts `preinstall`, `install`, `postinstall`, `prepare`,
  `prepack`, `postpack` or `prepublish` is added, changed or removed. Detail: the status letter
  and each such script, for example `M scripts.postinstall`.
- `package.json` when either version is not a JSON object, so its scripts cannot be compared.
  Detail: the status letter and `unparsed`, for example `M unparsed`.

## deps: dependency manifests and lockfiles

- Anywhere: `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
  `pnpm-lock.yaml`, `bun.lock`, `bun.lockb`, `Pipfile`, `Pipfile.lock`, `poetry.lock`,
  `uv.lock`, `pdm.lock`, `pyproject.toml`, `setup.cfg`, `constraints.txt`, `Cargo.toml`,
  `Cargo.lock`, `go.mod`, `go.sum`, `Gemfile`, `Gemfile.lock`, `composer.json`,
  `composer.lock`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradle.lockfile`,
  `packages.lock.json`, any `*.gemspec`, and any `requirements*.txt`.

Detail: the status letter, then `+NAME` for each new dependency where the file is cheap to read:

- `package.json`: names in `dependencies`, `devDependencies`, `optionalDependencies` and
  `peerDependencies` that the old version did not have. A name with characters outside
  `A-Z a-z 0-9 @ / . _ ~ -` is left out of the detail.
- `requirements*.txt`: project names (normalised: lower case, runs of `-_.` as `-`) that the old
  version did not list. Option lines (`-r`, `-e`, ...) and URL lines are skipped.

A version change of an existing dependency shows as the status letter alone. Other manifests
and every lockfile report the status letter only.

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
    `U+E0100..U+E01EF`.

Detail: what was found and the line, in the new file, of its first occurrence, for example
`<img line 12`, `<!-- line 3` or `U+202E line 40`. A file has one line per kind found.

U+200D (zero-width joiner) is part of many emoji, so an added emoji can be reported. That is
expected: the report says what is there, not whether it is harmful.
