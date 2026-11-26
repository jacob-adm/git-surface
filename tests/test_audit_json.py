# SPDX-License-Identifier: Apache-2.0
"""git surface --audit-json: one audit result object built from the --json records."""

import json
import os
import re
import unittest

from fixtures import Repo, example_repo

from git_surface import __version__, audit

TOP = {"format", "tool", "target", "exit", "findings", "errors"}
FINDING = {"rule", "severity", "message", "evidence", "record"}


def check_shape(test, doc):
    """The rules of format audit-result/1 that a git surface result can break."""
    test.assertEqual(set(doc), TOP)
    test.assertEqual(doc["format"], "audit-result/1")
    test.assertEqual(doc["tool"], {"name": "git-surface", "version": __version__})
    test.assertEqual(doc["target"]["kind"], "repository")
    for f in doc["findings"]:
        test.assertEqual(set(f), FINDING)
        test.assertRegex(f["rule"], r"\Agit-surface\.[a-z]+\Z")
        test.assertIn(f["severity"], ("high", "medium", "low"))
        test.assertTrue(f["message"])
        test.assertRegex(f["evidence"]["commit"], r"\A[0-9a-f]{40}([0-9a-f]{24})?\Z")
        test.assertEqual(f["evidence"]["ref"], f["record"]["ref"])
        test.assertEqual(f["evidence"]["path"], f["record"]["path"])
    for e in doc["errors"]:
        test.assertEqual(set(e), {"message"})
    want = 2 if doc["errors"] else (1 if doc["findings"] else 0)
    test.assertEqual(doc["exit"], want)


class ExampleTest(unittest.TestCase):

    def setUp(self):
        self.repo = example_repo()
        self.addCleanup(self.repo.cleanup)
        self.refs = self.repo.git("for-each-ref", "--format=%(refname:short)",
                                  "refs/heads/agent/")

    def run_audit(self, *args, data=None):
        code, out, err = self.repo.surface("--audit-json", *args,
                                           data=self.refs if data is None else data)
        doc = json.loads(out)
        check_shape(self, doc)
        self.assertEqual(doc["exit"], code)
        self.assertTrue(out.endswith(b"}\n"))
        return doc, err

    def test_records_and_exit_match_json(self):
        jcode, jout, jerr = self.repo.surface("--json", "main", data=self.refs)
        doc, err = self.run_audit("main")
        self.assertEqual([f["record"] for f in doc["findings"]], json.loads(jout))
        self.assertEqual((doc["exit"], err), (jcode, jerr))

    def test_default_and_json_output_unchanged(self):
        # The new flag must not change what the other modes write.
        code, out, err = self.repo.surface("main", data=self.refs)
        self.assertEqual((code, err), (1, b""))
        self.assertEqual(out.decode("ascii").splitlines()[0],
                         "agent/ci\tci\tM\t.github/workflows/test.yml")
        self.assertNotIn(b"audit", out)
        self.assertNotIn(b"severity", self.repo.surface("--json", "main", data=self.refs)[1])

    def test_messages_severities_and_lines(self):
        doc, _ = self.run_audit("main")
        got = [(f["rule"], f["severity"], f["message"], f["evidence"].get("line"))
               for f in doc["findings"]]
        self.assertEqual(got, [
            ("git-surface.ci", "high",
             "agent/ci modifies CI file .github/workflows/test.yml", None),
            ("git-surface.exec", "medium",
             "agent/ci adds build or shell file scripts/release.sh and makes it executable",
             None),
            ("git-surface.deps", "medium",
             "agent/deps modifies dependency file package.json: +left-pad", None),
            ("git-surface.install", "high",
             "agent/deps modifies install file package.json (scripts.postinstall)", None),
            ("git-surface.hidden", "high",
             "agent/docs adds an HTML comment to README.md at line 4", 4),
            ("git-surface.hidden", "high",
             "agent/docs adds an <img> tag to README.md at line 5", 5),
        ])

    def test_commit_is_the_ref_tip(self):
        doc, _ = self.run_audit("main")
        for f in doc["findings"]:
            tip = self.repo.git("rev-parse", f["record"]["ref"]).strip().decode("ascii")
            self.assertEqual(f["evidence"]["commit"], tip)

    def test_target(self):
        doc, _ = self.run_audit("main")
        self.assertEqual(doc["target"], {"kind": "repository", "base": "main",
                                         "name": os.path.basename(self.repo.path)})
        doc, _ = self.run_audit("main", data="agent/ci\n")
        self.assertEqual(doc["target"]["ref"], "agent/ci")

    def test_nothing_found(self):
        doc, err = self.run_audit("main", data="agent/fix\n")
        self.assertEqual((doc["exit"], doc["findings"], doc["errors"], err), (0, [], [], b""))

    def test_unknown_base_still_writes_the_object(self):
        doc, err = self.run_audit("nope")
        self.assertEqual(doc["findings"], [])
        self.assertEqual(doc["errors"], [{"message": "unknown ref or not a commit: nope"}])
        self.assertEqual(err, b"git-surface: unknown ref or not a commit: nope\n")
        self.assertEqual(doc["target"]["base"], "nope")

    def test_unknown_ref_still_writes_the_object(self):
        doc, err = self.run_audit("main", data="agent/ci\nnope\n")
        self.assertEqual(doc["errors"], [{"message": "record 2: unknown ref or not a commit: nope"}])
        self.assertEqual(err, b"git-surface: record 2: unknown ref or not a commit: nope\n")

    def test_json_together_is_a_usage_error(self):
        doc, err = self.run_audit("--json", "main")
        self.assertEqual(doc["errors"],
                         [{"message": "--json and --audit-json cannot be used together"}])
        self.assertEqual(doc["findings"], [])

    def test_missing_base_is_a_usage_error(self):
        doc, _ = self.run_audit()
        self.assertEqual(doc["errors"], [{"message": "expected exactly one BASE argument (see -h)"}])
        self.assertNotIn("base", doc["target"])

    def test_no_merge_base_keeps_the_other_findings(self):
        self.repo.git("checkout", "-q", "--orphan", "lone")
        self.repo.commit("unrelated")
        self.repo.git("checkout", "-q", "-f", "main")
        doc, err = self.run_audit("main", data="agent/ci\nlone\n")
        self.assertEqual(len(doc["findings"]), 2)
        self.assertEqual(doc["errors"], [{"message": "lone: no merge base with main"}])
        self.assertEqual(err, b"git-surface: lone: no merge base with main\n")


class DocsTest(unittest.TestCase):

    def test_documented_example_is_real_output(self):
        repo = example_repo()
        self.addCleanup(repo.cleanup)
        _, out, _ = repo.surface("--audit-json", "main", data="agent/docs\n")
        got = json.loads(out)
        got["target"]["name"] = "demo"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "docs", "commands.md"), encoding="utf-8") as handle:
            text = handle.read()
        block = text.split("### Audit result output", 1)[1].split("```json\n", 1)[1]
        documented = json.loads(block.split("```", 1)[0])
        # The page shows the version the flag ships in; the rest must match exactly.
        documented["tool"]["version"] = got["tool"]["version"]
        self.assertEqual(documented, got)


class MessageTest(unittest.TestCase):
    """Every class and detail shape gets one plain sentence."""

    def test_messages(self):
        cases = [
            ("hook", "D", ".husky/pre-commit", "r deletes git hook file .husky/pre-commit"),
            ("agent", "A", "CLAUDE.md", "r adds agent file CLAUDE.md"),
            ("repo", "M filter", ".gitattributes",
             "r modifies repository file .gitattributes (filter)"),
            ("install", "M [build-system]", "pyproject.toml",
             "r modifies install file pyproject.toml ([build-system])"),
            ("deps", "M -lodash express 4.18.2->4.19.2", "package.json",
             "r modifies dependency file package.json: -lodash express 4.18.2->4.19.2"),
            ("exec", "T", "run", "r changes the type of build or shell file run"),
            ("ci", "M named-in .github/workflows/a.yml .github/workflows/b.yml",
             "scripts/helper.py", "r modifies scripts/helper.py, named in CI file "
             ".github/workflows/a.yml, .github/workflows/b.yml"),
            ("hidden", "U+202E line 40", "a.py",
             "r adds the invisible character U+202E to a.py at line 40"),
            ("hidden", "U+E0000..U+E007F line 2", "a.md",
             "r adds invisible characters in U+E0000..U+E007F to a.md at line 2"),
            ("hidden", "</script line 9", "a.md", "r adds a closing <script> tag to a.md at line 9"),
        ]
        for cls, detail, path, want in cases:
            with self.subTest(detail):
                self.assertEqual(audit.message("r", cls, detail, path), want)

    def test_every_class_has_a_severity_and_noun(self):
        for cls in ("agent", "ci", "deps", "exec", "hidden", "hook", "install", "repo"):
            self.assertIn(cls, audit.SEVERITY)
        self.assertEqual(set(audit.NOUN) | {"hidden"}, set(audit.SEVERITY))

    def test_line_only_for_hidden(self):
        f = audit.finding({"ref": "r", "class": "deps", "detail": "M x line 3", "path": "p"},
                          "a" * 40)
        self.assertNotIn("line", f["evidence"])
        f = audit.finding({"ref": "r", "class": "hidden", "detail": "<img line 3", "path": "p"},
                          "a" * 40)
        self.assertEqual(f["evidence"]["line"], 3)


if __name__ == "__main__":
    unittest.main()
