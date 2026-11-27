# Running git-surface in CI

## GitHub Actions

Copy this file to `.github/workflows/git-surface.yml`. On every pull request it runs
`git surface` on the pull request against its base branch, and fails when anything is reported:
a change to CI, hooks, agent instructions, install scripts, dependencies, executables or hidden
content (see [Classes](classes.md)). The output names each file and class.

It fails on every pull request that changes one of those files, dependency upgrades included, by
design: those are the changes that need a second look. Use it as a required status check where
such pull requests are merged by someone allowed to bypass the rule after reviewing them, or keep
it as an optional check and read its output on each pull request.

```yaml
# Report changes in the pull request to what runs or is trusted: CI, hooks, agent
# instructions, install scripts, dependencies, executables and hidden content.
# Fails when anything is reported, so that a person reviews those files.
name: git-surface
on:
  pull_request:
permissions:
  contents: read
jobs:
  surface:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.13"
      - run: python -m pip install git-surface==0.4.0
      - name: Report changes to what runs or is trusted
        env:
          BASE_REF: ${{ github.base_ref }}
        run: echo HEAD | git surface "origin/$BASE_REF"
```

## pre-commit

The hook runs before `git push` and checks `HEAD` against `origin/main`; set `GIT_SURFACE_BASE`
to use another base. Install it with `pre-commit install --hook-type pre-push`. The push that
first adds `.pre-commit-config.yaml` fails, because that file is itself reported as a `hook`
change. Add it to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: git-surface
        name: git-surface
        language: python
        additional_dependencies: [git-surface==0.4.0]
        stages: [pre-push]
        pass_filenames: false
        always_run: true
        entry: sh -c 'echo HEAD | git surface "${GIT_SURFACE_BASE:-origin/main}"'
```

## Tested

Tested on 27 November 2026 in a test repository on GitHub, with git-surface 0.4.0 and, beside
it, the trust-path and release-drift recipes:

| Pull request | Check |
| --- | --- |
| Adds a `.pth` file, the file type of the LiteLLM 1.82.8 attack (the test file held no code) | Fails: `install A litellm_init.pth` |
| Edits `README.md` | Passes |
| Adds a workflow (two pull requests) | Fails: `ci A .github/workflows/greet.yml` and `ci A .github/workflows/lint.yml` |
| Upgrades a package in `package-lock.json` (two pull requests) | Fails: `deps M package-lock.json`, and `ci M named-in .github/workflows/release-drift.yml`, because the release-drift workflow names the lockfile |

With pre-commit 4.7.0, the pre-push hook stopped a push of the `.pth` commit and let the
`README.md` commit through.

## Notes

- Pin the version, as above, and raise it on purpose. A new release can add records, and a check
  that changes under you is not a reviewed check.
- The actions are pinned to a commit, with the release as a comment. Update the commit and the
  comment together.
- A `pull_request` workflow runs the copy of the workflow file in the pull request, so a pull
  request can change or remove the check. Require review of changes under `.github/`, for example
  with a `CODEOWNERS` entry; git-surface reports such changes as `ci`.
- The workflow needs no secret and only `contents: read`. It reads the repository and, where
  stated, downloads packages from the registry; it installs or runs nothing from them.
