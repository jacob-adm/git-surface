# SPDX-License-Identifier: Apache-2.0
"""Inputs real repositories produce that the main suite does not build: symlinks, CRLF
files, LFS pointers, non-ASCII ref names, large diffs, closed pipes and terminal output."""

import os
import subprocess
import sys
import unittest

from fixtures import Repo
from git_surface._common import for_terminal

RLO = "‮"


class AdversarialTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()
        self.repo.write("README.md", "# x\n")
        self.repo.commit("init")
        self.addCleanup(self.repo.cleanup)

    def branch_with(self, name, files):
        self.repo.branch(name)
        for path, content in sorted(files.items()):
            self.repo.write(path, content)
        self.repo.commit(name)
        self.repo.git("checkout", "-q", "-f", "main")

    def run_lines(self, data, *args):
        code, out, err = self.repo.surface("main", *args, data=data)
        self.assertEqual(err, b"")
        return code, out.splitlines()

    def test_symlink_is_classed_by_its_name(self):
        self.repo.branch("b")
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.repo.path,
                              env=self.repo.env, input=b"README.md", stdout=subprocess.PIPE,
                              check=True).stdout.strip().decode("ascii")
        self.repo.git("update-index", "--add", "--cacheinfo", "120000", blob, "run.sh")
        self.repo.commit("b")
        self.repo.git("checkout", "-q", "-f", "main")
        self.assertEqual(self.run_lines("b\n"), (1, [b"b\texec\tA\trun.sh"]))

    def test_crlf_markdown_keeps_line_numbers(self):
        self.branch_with("b", {"notes.md": b"a\r\nb\r\n<img src=x>\r\n" + RLO.encode() + b"\r\n"})
        self.assertEqual(self.run_lines("b\n"), (1, [
            b"b\thidden\t<img line 3\tnotes.md",
            b"b\thidden\tU+202E line 4\tnotes.md"]))

    def test_lfs_pointer_is_plain_text(self):
        pointer = ("version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64
                   + "\nsize 12345\n")
        self.branch_with("b", {".gitattributes": "*.bin filter=lfs diff=lfs merge=lfs -text\n",
                               "model.bin": pointer})
        self.assertEqual(self.run_lines("b\n"), (0, []))

    def test_non_ascii_ref_name(self):
        name = "agent/café-日本"
        self.branch_with(name, {"setup.py": "x = 1\n"})
        self.assertEqual(self.run_lines(name + "\n"),
                         (1, [name.encode("utf-8") + b"\tinstall\tA\tsetup.py"]))

    def test_large_diff_reports_the_right_line(self):
        body = "".join("line %d\n" % n for n in range(200000)) + "x" + RLO + "\n"
        self.branch_with("b", {"big.txt": body})
        self.assertEqual(self.run_lines("b\n"),
                         (1, [b"b\thidden\tU+202E line 200001\tbig.txt"]))

    def test_unknown_ref_is_escaped_in_the_message(self):
        code, out, err = self.repo.surface("main", data=b"bad\x01\x1b[2J\n")
        self.assertEqual((code, out), (2, b""))
        self.assertEqual(err, b"git-surface: record 1: unknown ref or not a commit: "
                              b"bad\\x01\\x1b[2J\n")

    def test_double_dash_ends_options(self):
        self.branch_with("b", {"setup.py": "x = 1\n"})
        self.assertEqual(self.repo.surface("--", "main", data="b\n"),
                         (1, b"b\tinstall\tA\tsetup.py\n", b""))

    def test_closed_pipe_is_a_quiet_exit(self):
        self.branch_with("b", {"setup.py": "x = 1\n"})
        proc = subprocess.Popen([sys.executable, "-m", "git_surface", "main"],
                                cwd=self.repo.path, env=self.repo.env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # The reader is gone before anything is written.
        proc.stdout.close()
        _, err = proc.communicate(b"b\n")
        self.assertEqual((proc.returncode, err), (0, b""))

    @unittest.skipUnless(os.name == "posix", "needs a pseudo-terminal")
    def test_terminal_output_escapes_control_bytes(self):
        import pty
        self.branch_with("b", {"x\x1b[31m.sh": "x\n"})
        master, slave = pty.openpty()
        proc = subprocess.Popen([sys.executable, "-m", "git_surface", "main"],
                                cwd=self.repo.path, env=self.repo.env, stdin=subprocess.PIPE,
                                stdout=slave, stderr=subprocess.PIPE)
        _, err = proc.communicate(b"b\n")
        # The slave stays open until the output is read: some systems drop what is
        # buffered once the last slave descriptor closes.
        os.set_blocking(master, False)
        out = b""
        while True:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        os.close(slave)
        os.close(master)
        self.assertEqual((proc.returncode, err), (1, b""))
        self.assertEqual(out.replace(b"\r\n", b"\n"), b"b\texec\tA\tx\\x1b[31m.sh\n")


class ForTerminalTest(unittest.TestCase):

    def test_escapes(self):
        self.assertEqual(for_terminal(b"a\\b"), b"a\\\\b")
        self.assertEqual(for_terminal(b"\x1b[2J\x7f"), b"\\x1b[2J\\x7f")
        self.assertEqual(for_terminal("\u0085".encode("utf-8")), b"\\xc2\\x85")
        self.assertEqual(for_terminal(b"\xff\xfe"), b"\\xff\\xfe")
        self.assertEqual(for_terminal("café".encode("utf-8")), "café".encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
