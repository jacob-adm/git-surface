# Contributing

## Tests

```sh
python3 -m unittest discover -s tests
```

The suite builds real git repositories in temporary directories and runs `git surface` on their
branches: each class of change, pipeline use, and the error cases. It also checks that the
README's example output, the version it shows and the class list in [Classes](docs/classes.md)
match what the command does. It needs git 2.38 or later on `PATH`.

## Contributing

Changes reach `main` only through pull requests.

1. Fork the repository and create a branch.
2. Make the change with a test that fails without it, then run `python3 -m unittest discover -s tests`.
3. Open a pull request against `main`. CI runs the tests on Linux, macOS and Windows with Python
   3.8 and 3.13, and builds the package; the required checks must pass before merging. Pull requests
   are merged with a merge commit.

Keep git-surface standard-library-only, and keep it running nothing but `git`.
