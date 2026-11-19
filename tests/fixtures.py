# SPDX-License-Identifier: Apache-2.0
"""Real git repositories in temporary directories, and a runner for git surface.

Nothing is mocked: every test builds a repository with git and runs the command as a
subprocess, the way git runs it.
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Repo(object):
    """A git repository in a temporary directory, with a hermetic environment."""

    def __init__(self):
        self.path = os.path.realpath(tempfile.mkdtemp(prefix="git-surface-test-"))
        self.home = os.path.join(self.path, ".home")
        os.mkdir(self.home)
        config = os.path.join(self.home, "gitconfig")
        open(config, "wb").close()
        env = {}
        for key, value in os.environ.items():
            # The caller's git, Python and locale settings must not reach the tests.
            if key.startswith(("GIT_", "PYTHON", "LC_")) or key in ("LANG", "LANGUAGE"):
                continue
            env[key] = value
        env.update({
            "HOME": self.home,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": config,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+0000",
            "PYTHONPATH": ROOT,
        })
        self.env = env
        self.git("init", "-q", "-b", "main")
        # The .home directory lives inside the worktree; keep it out of every commit.
        with open(os.path.join(self.path, ".git", "info", "exclude"), "a") as handle:
            handle.write(".home/\n")

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def git(self, *args):
        """Run git in the repository; return stdout bytes, failing loudly on error."""
        proc = subprocess.run(["git"] + list(args), cwd=self.path, env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise AssertionError("git %r failed: %r" % (args, proc.stderr))
        return proc.stdout

    def write(self, path, content, executable=False):
        """Write a file (str or bytes) in the worktree and stage it."""
        full = os.path.join(self.path, path)
        if os.path.dirname(full):
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        self.git("add", "--", path)
        if executable:
            self.git("update-index", "--chmod=+x", "--", path)

    def remove(self, path):
        self.git("rm", "-q", "--", path)

    def commit(self, message="change"):
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def branch(self, name, start="main"):
        self.git("checkout", "-q", "-f", "-b", name, start)

    def surface(self, *args, data=b"", cwd=None):
        """Run git surface; return (exit code, stdout bytes, stderr bytes)."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        proc = subprocess.run([sys.executable, "-m", "git_surface"] + list(args),
                              cwd=cwd or self.path, env=self.env, input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout, proc.stderr


def example_repo():
    """The repository the README's Quick start runs in: four agent branches off main."""
    repo = Repo()
    repo.write("README.md", "# demo\n\nUsage notes.\n")
    repo.write("package.json", '{\n  "name": "demo",\n  "dependencies": {"express": "4"}\n}\n')
    repo.write(".github/workflows/test.yml", "on: push\njobs: {}\n")
    repo.write("src/app.js", "console.log('hi');\n")
    repo.commit("init")
    # A documentation change carrying a hidden image and an HTML comment.
    repo.branch("agent/docs")
    repo.write("README.md", "# demo\n\nUsage notes.\n"
               "<!-- reviewers: nothing to see -->\n"
               "<img src=\"https://example.invalid/p.png?d=x\" width=\"0\">\n")
    repo.commit("docs")
    # A new dependency with an install script.
    repo.branch("agent/deps", "main")
    repo.write("package.json", '{\n  "name": "demo",\n  "dependencies": {"express": "4", '
               '"left-pad": "1"},\n  "scripts": {"postinstall": "node setup.js"}\n}\n')
    repo.commit("deps")
    # A change to the CI workflow and a new executable script.
    repo.branch("agent/ci", "main")
    repo.write(".github/workflows/test.yml", "on: push\njobs: {}\n# tweak\n")
    repo.write("scripts/release.sh", "#!/bin/sh\necho release\n", executable=True)
    repo.commit("ci")
    # An ordinary code change.
    repo.branch("agent/fix", "main")
    repo.write("src/app.js", "console.log('hello');\n")
    repo.commit("fix")
    repo.git("checkout", "-q", "-f", "main")
    return repo
