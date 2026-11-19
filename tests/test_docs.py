# SPDX-License-Identifier: Apache-2.0
"""The README example and the class list in docs/ match what the command does."""

import os
import re
import unittest

from fixtures import ROOT, example_repo
from git_surface import __version__, classify


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


class ReadmeTest(unittest.TestCase):

    def test_quick_start_output(self):
        readme = read("README.md")
        section = readme[readme.index("## Quick start"):]
        command = re.search(r"```sh\n(.*?)\n```", section, re.S).group(1)
        expected = re.search(r"```text\n(.*?)```", section, re.S).group(1)
        self.assertEqual(command, "git for-each-ref --format='%(refname:short)' "
                                  "refs/heads/agent/ | git surface main")
        repo = example_repo()
        self.addCleanup(repo.cleanup)
        refs = repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads/agent/")
        code, out, err = repo.surface("main", data=refs)
        self.assertEqual((code, out.decode("utf-8"), err), (1, expected, b""))

    def test_version_shown(self):
        self.assertIn("git-surface %s\n" % __version__, read("README.md"))


class ClassesDocTest(unittest.TestCase):

    def test_every_rule_is_documented(self):
        doc = read(os.path.join("docs", "classes.md"))
        names = set()
        for group in (classify.CI_PREFIXES, classify.CI_ROOT_FILES, classify.CI_NAMES,
                      classify.HOOK_PREFIXES, classify.HOOK_ROOT_FILES,
                      classify.INSTALL_NAMES, classify.DEPS_NAMES, classify.EXEC_NAMES):
            names.update(name.decode("ascii") for name in group)
        for suffix in (classify.INSTALL_SUFFIXES + classify.DEPS_SUFFIXES
                       + classify.EXEC_SUFFIXES + classify.MARKDOWN_SUFFIXES):
            names.add(suffix.decode("ascii"))
        names.update(classify.NPM_LIFECYCLE)
        for name in sorted(names):
            self.assertIn("`%s" % name.lstrip("."), doc.replace("`.", "`").replace("`*.", "`"),
                          name)
        for tag in classify.HTML.pattern.decode("ascii").split("(")[1].split(")")[0].split("|"):
            self.assertIn("`%s`" % tag, doc)
        for first, last, _ in classify.HIDDEN_CHARS:
            self.assertIn("U+%04X" % first, doc)
            self.assertIn("U+%04X" % last, doc)


class WorkflowTest(unittest.TestCase):

    def test_suite_runs_on_the_oldest_git(self):
        # README promises git 2.38 or later; CI must run the suite on a git that old, or the
        # nearest a pinned image ships (Debian bookworm: 2.39).
        self.assertIn("git 2.38 or later", read("README.md"))
        workflow = read(os.path.join(".github", "workflows", "test.yml"))
        job = workflow[workflow.index("\n  old-git:\n"):]
        self.assertIn("python:3.8-slim-bookworm", job)
        self.assertIn("apt-get install -y -qq --no-install-recommends git", job)
        self.assertIn("python -m unittest discover -s tests", job)


if __name__ == "__main__":
    unittest.main()
