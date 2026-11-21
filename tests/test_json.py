# SPDX-License-Identifier: Apache-2.0
"""git surface --json: the same records as the default output, as a JSON array."""

import json
import os
import unittest

from fixtures import Repo, example_repo

KEYS = ["class", "detail", "path", "ref"]


class JsonTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()
        self.repo.write("README.md", "# x\n")
        self.repo.commit("init")
        self.addCleanup(self.repo.cleanup)

    def add_by_name(self, name, content=b"on: push\n"):
        """Stage a file under NAME (bytes) without creating it on disk."""
        full = os.path.join(self.repo.path, "blob.tmp")
        with open(full, "wb") as handle:
            handle.write(content)
        oid = self.repo.git("hash-object", "-w", full).strip()
        os.remove(full)
        self.repo.git("update-index", "--add", "--cacheinfo", "100644", oid, name)

    def test_same_records_as_default_output(self):
        repo = example_repo()
        self.addCleanup(repo.cleanup)
        refs = repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads/agent/")
        code, out, err = repo.surface("main", data=refs)
        jcode, jout, jerr = repo.surface("--json", "main", data=refs)
        self.assertEqual((jcode, jerr), (code, err))
        self.assertEqual(code, 1)
        expected = [dict(zip(["ref", "class", "detail", "path"], line.split("\t")))
                    for line in out.decode("utf-8").splitlines()]
        self.assertEqual(json.loads(jout), expected)
        self.assertTrue(jout.endswith(b"]\n"))

    def test_nothing_reported_is_an_empty_array(self):
        self.repo.branch("clean")
        self.repo.write("src/a.py", "print(1)\n")
        self.repo.commit("clean")
        code, out, err = self.repo.surface("--json", "main", data="clean\n")
        self.assertEqual((code, out, err), (0, b"[]\n", b""))

    def test_path_lf_mode_refuses_is_written(self):
        self.repo.branch("tab")
        self.add_by_name(b".github/workflows/a\tb\x1b.yml")
        self.repo.commit("tab")
        code, _, err = self.repo.surface("main", data="tab\n")
        self.assertEqual(code, 2)
        self.assertIn(b"-z", err)
        code, out, err = self.repo.surface("--json", "main", data="tab\n")
        self.assertEqual((code, err), (1, b""))
        self.assertEqual(json.loads(out), [{"class": "ci", "detail": "A",
                                            "path": ".github/workflows/a\tb\x1b.yml",
                                            "ref": "tab"}])
        # Control bytes are escaped, so the output is safe on a terminal.
        self.assertFalse(any(byte < 0x20 and byte != 0x0A for byte in out))

    def test_name_that_is_not_utf8_is_recoverable(self):
        self.repo.branch("raw")
        self.add_by_name(b".github/workflows/\xff.yml")
        self.repo.commit("raw")
        code, out, err = self.repo.surface("--json", "main", data="raw\n")
        self.assertEqual((code, err), (1, b""))
        out.decode("ascii")
        path = json.loads(out)[0]["path"]
        self.assertEqual(path.encode("utf-8", "surrogateescape"), b".github/workflows/\xff.yml")

    def test_ref_without_merge_base_still_writes_the_others(self):
        self.repo.branch("ci")
        self.add_by_name(b".github/workflows/t.yml")
        self.repo.commit("ci")
        self.repo.git("checkout", "-q", "--orphan", "lone")
        self.repo.commit("lone")
        self.repo.git("checkout", "-q", "-f", "main")
        code, out, err = self.repo.surface("--json", "main", data="lone\nci\n")
        self.assertEqual(code, 2)
        self.assertIn(b"lone: no merge base with main", err)
        self.assertEqual([row["ref"] for row in json.loads(out)], ["ci"])
        self.assertEqual(sorted(json.loads(out)[0]), KEYS)

    def test_documented_example_is_real_output(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "docs", "commands.md"), encoding="utf-8") as handle:
            doc = handle.read()
        section = doc[doc.index("### JSON output"):]
        example = json.loads(section.split("```json\n", 1)[1].split("```", 1)[0])
        repo = example_repo()
        self.addCleanup(repo.cleanup)
        code, out, _ = repo.surface("--json", "main", data="agent/ci\n")
        self.assertEqual(code, 1)
        for row in example:
            self.assertIn(row, json.loads(out))


if __name__ == "__main__":
    unittest.main()
