# SPDX-License-Identifier: Apache-2.0
"""The source distribution carries everything its tests need."""

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from fixtures import ROOT

BUILD = ("import sys\nfrom setuptools import build_meta\n"
         "print(build_meta.build_sdist(sys.argv[1]))\n")


class SdistTest(unittest.TestCase):

    def test_sdist_has_tests_and_docs(self):
        try:
            import setuptools
        except ImportError:
            self.skipTest("setuptools is not installed")
        if int(setuptools.__version__.split(".")[0]) < 61:
            self.skipTest("setuptools is older than 61")
        out = tempfile.mkdtemp(prefix="git-surface-sdist-")
        self.addCleanup(shutil.rmtree, out, True)
        proc = subprocess.run([sys.executable, "-c", BUILD, out], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        name = proc.stdout.decode("ascii").strip().splitlines()[-1]
        with tarfile.open(os.path.join(out, name)) as archive:
            members = set(m.split("/", 1)[1] for m in archive.getnames() if "/" in m)
        wanted = set()
        for folder, suffix in (("tests", ".py"), ("docs", ".md")):
            for entry in os.listdir(os.path.join(ROOT, folder)):
                if entry.endswith(suffix):
                    wanted.add(folder + "/" + entry)
        self.assertEqual(sorted(wanted - members), [])


if __name__ == "__main__":
    unittest.main()
