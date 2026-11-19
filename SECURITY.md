# Security

`git surface` runs only `git` (`rev-parse`, `merge-base`, `diff`, `cat-file`), without a shell, in
the current repository. It never writes to the repository and never runs code from it: no hooks,
no build, no install. It reads file contents only for `package.json`, `pyproject.toml` and
`requirements*.txt`, and repository content reaches its output only as paths and a restricted
detail field, with control bytes escaped on a terminal. See
[Limitations and security](docs/limitations-and-security.md).

## Reporting a vulnerability

Please report security problems privately, through GitHub's "Report a vulnerability" button on the
repository's Security tab. Please do not open a public issue. You can expect a reply within a week.
