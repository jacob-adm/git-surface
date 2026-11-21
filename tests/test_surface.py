# SPDX-License-Identifier: Apache-2.0
"""Behaviour of git surface on real repositories."""

import os
import unittest

from fixtures import Repo, example_repo


def records(out):
    """Split LF output into lists of fields."""
    return [line.split(b"\t") for line in out.splitlines()]


class SurfaceTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()
        self.repo.write("README.md", "# x\n\ntext\n")
        self.repo.write("src/a.py", "print(1)\n")
        self.repo.commit("init")
        self.addCleanup(self.repo.cleanup)

    def on_branch(self, name, files, executable=()):
        """Make branch NAME off main that writes FILES ({path: content})."""
        self.repo.branch(name)
        for path, content in sorted(files.items()):
            self.repo.write(path, content, executable=path in executable)
        self.repo.commit(name)
        self.repo.git("checkout", "-q", "-f", "main")

    def run_one(self, ref):
        code, out, err = self.repo.surface("main", data=ref + "\n")
        self.assertEqual(err, b"")
        return code, records(out)

    def test_clean_branch_reports_nothing(self):
        self.on_branch("clean", {"src/a.py": "print(2)\n", "docs/guide.md": "# Guide\n"})
        self.assertEqual(self.run_one("clean"), (0, []))

    def test_ci_workflow(self):
        self.on_branch("b", {".github/workflows/x.yml": "on: push\n", ".gitlab-ci.yml": "a:\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"ci", b"A", b".github/workflows/x.yml"],
            [b"b", b"ci", b"A", b".gitlab-ci.yml"]]))

    def test_hook_files(self):
        self.on_branch("b", {".pre-commit-config.yaml": "repos: []\n",
                             ".husky/pre-commit": "npm test\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"hook", b"A", b".husky/pre-commit"],
            [b"b", b"hook", b"A", b".pre-commit-config.yaml"]]))

    def test_exec_by_name_and_by_mode(self):
        self.on_branch("b", {"Makefile": "all:\n", "tools/run": "#!/bin/sh\n",
                             "x.sh": "echo\n"}, executable=("tools/run",))
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"exec", b"A", b"Makefile"],
            [b"b", b"exec", b"A +x", b"tools/run"],
            [b"b", b"exec", b"A", b"x.sh"]]))

    def test_mode_change_alone(self):
        self.repo.branch("b")
        self.repo.git("update-index", "--chmod=+x", "--", "src/a.py")
        self.repo.commit("chmod")
        self.repo.git("checkout", "-q", "-f", "main")
        self.assertEqual(self.run_one("b"), (1, [[b"b", b"exec", b"M +x", b"src/a.py"]]))

    def test_npm_dependency_and_lifecycle_script(self):
        self.repo.write("package.json", '{"dependencies": {"a": "1"}}\n')
        self.repo.commit("pkg")
        self.on_branch("b", {
            "package.json": '{"dependencies": {"a": "2", "evil": "1"},'
                            ' "devDependencies": {"@scope/x": "1"},'
                            ' "scripts": {"postinstall": "sh x", "test": "t"}}\n',
            "package-lock.json": "{}\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"A", b"package-lock.json"],
            [b"b", b"deps", b"M +@scope/x +evil a 1->2", b"package.json"],
            [b"b", b"install", b"M scripts.postinstall", b"package.json"]]))

    def test_unparsable_package_json(self):
        self.on_branch("b", {"package.json": "{not json\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"A", b"package.json"],
            [b"b", b"install", b"A unparsed", b"package.json"]]))

    def test_deeply_nested_package_json_is_unparsed(self):
        self.on_branch("b", {"package.json": "[" * 100000 + "]" * 100000 + "\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"A", b"package.json"],
            [b"b", b"install", b"A unparsed", b"package.json"]]))

    def test_submodule_at_a_manifest_path_does_not_abort(self):
        commit = self.repo.git("rev-parse", "HEAD").strip().decode("ascii")
        self.repo.branch("b")
        for path in ("requirements.txt", "pyproject.toml", "package.json"):
            self.repo.git("update-index", "--add", "--cacheinfo", "160000", commit, path)
        self.repo.commit("b")
        self.repo.git("checkout", "-q", "-f", "main")
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"A", b"package.json"],
            [b"b", b"deps", b"A", b"pyproject.toml"],
            [b"b", b"deps", b"A", b"requirements.txt"]]))

    def test_pyproject_dependencies_named(self):
        self.repo.write("pyproject.toml", '[project]\nname = "x"\ndependencies = [\n'
                        '  "requests==2.31.0",\n  "six",\n]\n')
        self.repo.commit("base")
        self.on_branch("b", {"pyproject.toml":
                             '[project]\nname = "x"\ndependencies = [\n'
                             '  "requests==2.32.0",  # pin [bumped]\n  "evil-pkg==1.0",\n]\n\n'
                             '[project.optional-dependencies]\ntest = ["pytest"]\n\n'
                             '[dependency-groups]\ndev = [{include-group = "test"}]\n'})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"M +evil-pkg +pytest -six requests 2.31.0->2.32.0",
             b"pyproject.toml"]]))

    def test_pyproject_poetry_tables(self):
        self.repo.write("pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.9"\n'
                        'click = "^8.1"\n')
        self.repo.commit("base")
        self.on_branch("b", {"pyproject.toml":
                             '[tool.poetry.dependencies]\npython = "^3.10"\nclick = "^8.2"\n'
                             'rich = {version = "13.7.0", optional = true}\n\n'
                             '[tool.poetry.group.docs.dependencies]\nmkdocs = "1.6"\n'})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"M +mkdocs +rich click ^8.1->^8.2", b"pyproject.toml"]]))

    def test_requirements_added_removed_and_pinned(self):
        self.repo.write("requirements.txt", "requests==2.0\nsix==1.16.0\nidna>=2\n"
                                            "Old.Pkg==1\nflask==1.0\nattrs==22 --hash=sha256:aa\n")
        self.repo.commit("req")
        self.on_branch("b", {"requirements.txt":
                             "requests == 3.0 ; python_version >= '3.8'\nsix==1.16.0\n"
                             "idna>=3\nFoo_Bar>=1  # new\nflask>=1.0\n-r other.txt\n"
                             "attrs[tests]==23 \\\n    --hash=sha256:bb\n"
                             "git+https://example.invalid/x.git\n"})
        # A bump is reported only between two == pins; idna and flask are not pins on both
        # sides, so they show no change.
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"M +foo-bar -old-pkg attrs 22->23 requests 2.0->3.0",
             b"requirements.txt"]]))

    def test_package_json_removed_and_bumped(self):
        self.repo.write("package.json", '{"dependencies": {"a": "^1.0.0", "gone": "1",'
                                        ' "same": "2"}, "devDependencies": {"b": "1"},'
                                        ' "peerDependencies": {"a": "1"}}\n')
        self.repo.commit("pkg")
        self.on_branch("b", {"package.json":
                             '{"dependencies": {"a": "^1.2.0", "same": "2"},'
                             ' "devDependencies": {"b": "2.0.0-beta.1"},'
                             ' "peerDependencies": {"a": "9"}}\n'})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"M -gone a ^1.0.0->^1.2.0 b 1->2.0.0-beta.1", b"package.json"]]))

    def test_unsafe_names_and_versions_are_left_out(self):
        self.repo.write("package.json", '{"dependencies": {"a": "1", "b": "1", "c": "1",'
                                        ' "d": "1"}}\n')
        self.repo.commit("pkg")
        self.on_branch("b", {"package.json":
                             '{"dependencies": {"a": ">=1 <2", "b": "1->2", "c": {"x": 1},'
                             ' "d": "2", "-e": "1", "f g": "1"}}\n'})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"M d 1->2", b"package.json"]]))

    def test_deleted_manifest_names_removed_dependencies(self):
        self.repo.write("requirements-dev.txt", "pytest==8\n")
        self.repo.commit("req")
        self.repo.branch("b")
        self.repo.remove("requirements-dev.txt")
        self.repo.commit("b")
        self.repo.git("checkout", "-q", "-f", "main")
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"deps", b"D -pytest", b"requirements-dev.txt"]]))

    def test_install_files(self):
        self.on_branch("b", {"setup.py": "import os\n", "pkg/evil.pth": "import os\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"install", b"A", b"pkg/evil.pth"],
            [b"b", b"install", b"A", b"setup.py"]]))

    def test_pyproject_build_system_only_when_touched(self):
        self.repo.write("pyproject.toml", '[build-system]\nrequires = ["setuptools"]\n\n'
                        '[project]\nname = "x"\n')
        self.repo.commit("pyproject")
        self.on_branch("deps-only", {"pyproject.toml": '[build-system]\nrequires = '
                                     '["setuptools"]\n\n[project]\nname = "y"\n'})
        self.on_branch("backend", {"pyproject.toml": '[build-system]\nrequires = '
                                   '["setuptools", "evil-backend"]\n\n[project]\nname = "x"\n'})
        self.assertEqual(self.run_one("deps-only"), (1, [
            [b"deps-only", b"deps", b"M", b"pyproject.toml"]]))
        self.assertEqual(self.run_one("backend"), (1, [
            [b"backend", b"deps", b"M", b"pyproject.toml"],
            [b"backend", b"install", b"M [build-system]", b"pyproject.toml"]]))

    def test_hidden_html_in_markdown(self):
        self.on_branch("b", {"README.md": "# x\n\ntext\n<IMG src=x>\n<!-- hi -->\n"
                             "<details><summary>s</summary></details>\n<imgx>\n",
                             "page.html": "<img src=x>\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"hidden", b"<!-- line 5", b"README.md"],
            [b"b", b"hidden", b"<details line 6", b"README.md"],
            [b"b", b"hidden", b"<img line 4", b"README.md"]]))

    def test_hidden_characters_in_any_text_file(self):
        self.on_branch("b", {
            "src/a.py": "print(1)\nif ok:\u202e  # \u2066x\u2069\n",
            "docs/n.md": "a\u200bb\n" + "".join(chr(0xE0000 + ord(c)) for c in "hi") + "\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"hidden", b"U+200B line 1", b"docs/n.md"],
            [b"b", b"hidden", b"U+E0000..U+E007F line 2", b"docs/n.md"],
            [b"b", b"hidden", b"U+202E line 2", b"src/a.py"],
            [b"b", b"hidden", b"U+2066 line 2", b"src/a.py"],
            [b"b", b"hidden", b"U+2069 line 2", b"src/a.py"]]))

    def test_leading_bom_is_not_reported(self):
        self.on_branch("b", {"docs/bom.md": "\ufeff# Title\n"})
        self.assertEqual(self.run_one("b"), (0, []))

    def test_only_added_lines_are_checked(self):
        self.repo.write("docs/old.md", "<img src=x>\nkeep\n")
        self.repo.commit("old")
        # Removing the tag and adding an ordinary line reports nothing.
        self.on_branch("b", {"docs/old.md": "keep\nmore\n"})
        self.assertEqual(self.run_one("b"), (0, []))

    def test_gitattributes_cannot_hide_content(self):
        self.repo.write(".gitattributes", "*.md -diff\n")
        self.repo.commit("attrs")
        self.on_branch("b", {"README.md": "# x\n\ntext\n<script>x</script>\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"hidden", b"<script line 4", b"README.md"]]))

    def test_binary_file_content_is_skipped(self):
        self.on_branch("b", {"img.bin": b"\x00\xe2\x80\xae\n"})
        self.assertEqual(self.run_one("b"), (0, []))

    def test_deleted_workflow_is_reported(self):
        self.repo.write(".github/workflows/sec.yml", "on: push\n")
        self.repo.commit("wf")
        self.repo.branch("b")
        self.repo.remove(".github/workflows/sec.yml")
        self.repo.commit("rm")
        self.repo.git("checkout", "-q", "-f", "main")
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"ci", b"D", b".github/workflows/sec.yml"]]))

    def test_changes_on_base_after_fork_are_not_the_branch(self):
        self.on_branch("b", {"src/a.py": "print(3)\n"})
        self.repo.write("Makefile", "all:\n")
        self.repo.commit("base moves on")
        self.assertEqual(self.run_one("b"), (0, []))

    def test_user_config_does_not_change_output(self):
        self.on_branch("b", {"README.md": "# x\n\ntext\n<img src=x>\n", "run.sh": "x\n"})
        before = self.repo.surface("main", data="b\n")
        for key, value in (("color.ui", "always"), ("diff.noprefix", "true"),
                           ("diff.algorithm", "patience"), ("diff.relative", "true"),
                           ("diff.submodule", "log"), ("core.quotePath", "false")):
            self.repo.git("config", key, value)
        self.assertEqual(self.repo.surface("main", data="b\n"), before)

    def test_inter_hunk_context_config_keeps_line_numbers(self):
        self.repo.write("pyproject.toml", '[project]\nname = "x"\n# a\n# b\n'
                        '[build-system]\nrequires = ["setuptools"]\n')
        self.repo.commit("pyproject")
        self.on_branch("b", {"pyproject.toml": '[project]\nname = "y"\n# a\n# b\n'
                             '[build-system]\nrequires = ["evil"]\n'})
        before = self.run_one("b")
        self.repo.git("config", "diff.interHunkContext", "10")
        self.assertEqual(self.run_one("b"), before)
        self.assertIn([b"b", b"install", b"M [build-system]", b"pyproject.toml"], before[1])

    def test_quoted_path_is_matched(self):
        self.on_branch("b", {"d\u00e9j\u00e0 vu/notes.md": "<img src=x>\n"})
        self.assertEqual(self.run_one("b"), (1, [
            [b"b", b"hidden", b"<img line 1", "d\u00e9j\u00e0 vu/notes.md".encode("utf-8")]]))

    def test_subdirectory_paths_are_root_relative(self):
        self.on_branch("b", {".github/workflows/x.yml": "on: push\n"})
        code, out, _ = self.repo.surface("main", data="b\n",
                                         cwd=self.repo.path + "/src")
        self.assertEqual((code, out), (1, b"b\tci\tA\t.github/workflows/x.yml\n"))


class PipelineTest(unittest.TestCase):

    def setUp(self):
        self.repo = example_repo()
        self.addCleanup(self.repo.cleanup)
        self.refs = b"agent/ci\nagent/deps\nagent/docs\nagent/fix\n"

    def test_deterministic(self):
        first = self.repo.surface("main", data=self.refs)
        second = self.repo.surface("main", data=self.refs)
        self.assertEqual(first, second)
        self.assertEqual(first[0], 1)

    def test_footprint_records_pipe_in(self):
        # `git footprint main` output: ref TAB status TAB path, a ref repeated per file.
        footprint = (b"agent/ci\tM\t.github/workflows/test.yml\nagent/ci\tA\tscripts/release.sh\n"
                     b"agent/deps\tM\tpackage.json\nagent/docs\tM\tREADME.md\n"
                     b"agent/fix\tM\tsrc/app.js\n")
        self.assertEqual(self.repo.surface("main", data=footprint),
                         self.repo.surface("main", data=self.refs))

    def test_refs_keep_input_order(self):
        _, docs, _ = self.repo.surface("main", data=b"agent/docs\n")
        _, ci, _ = self.repo.surface("main", data=b"agent/ci\n")
        _, both, _ = self.repo.surface("main", data=b"agent/docs\nagent/ci\nagent/docs\n")
        self.assertEqual(both, docs + ci)

    def test_z_mode(self):
        code, out, _ = self.repo.surface("-z", "main", data=b"agent/ci\0")
        self.assertEqual(code, 1)
        self.assertEqual(out, b"agent/ci\tci\tM\t.github/workflows/test.yml\0"
                              b"agent/ci\texec\tA +x\tscripts/release.sh\0")

    def test_crlf_input(self):
        self.assertEqual(self.repo.surface("main", data=b"agent/ci\r\n"),
                         self.repo.surface("main", data=b"agent/ci\n"))


class ErrorTest(unittest.TestCase):

    def setUp(self):
        self.repo = Repo()
        self.repo.write("a", "a\n")
        self.repo.commit("init")
        self.addCleanup(self.repo.cleanup)

    def test_unknown_ref(self):
        self.assertEqual(self.repo.surface("main", data="nope\n"),
                         (2, b"", b"git-surface: record 1: unknown ref or not a commit: nope\n"))

    def test_unknown_base(self):
        self.assertEqual(self.repo.surface("nope", data=""),
                         (2, b"", b"git-surface: unknown ref or not a commit: nope\n"))

    def test_missing_base(self):
        code, _, err = self.repo.surface(data="main\n")
        self.assertEqual(code, 2)
        self.assertIn(b"expected exactly one BASE", err)

    def test_range_is_not_a_ref(self):
        code, _, _ = self.repo.surface("main", data="main..main\n")
        self.assertEqual(code, 2)

    def test_no_merge_base(self):
        self.repo.git("checkout", "-q", "--orphan", "other")
        self.repo.commit("unrelated")
        self.assertEqual(self.repo.surface("main", data="other\n"),
                         (2, b"", b"git-surface: other: no merge base with main\n"))

    def test_refs_without_merge_base_are_skipped(self):
        for name, path in (("a", "Makefile"), ("c", ".gitlab-ci.yml")):
            self.repo.branch(name)
            self.repo.write(path, "x\n")
            self.repo.commit(name)
        self.repo.git("checkout", "-q", "--orphan", "lone\u00e9")
        self.repo.write(".travis.yml", "x\n")
        self.repo.commit("unrelated")
        self.repo.git("checkout", "-q", "--orphan", "lone2")
        self.repo.commit("unrelated")
        self.repo.git("checkout", "-q", "-f", "main")
        code, out, err = self.repo.surface("main", data="a\nlone\u00e9\nc\nlone2\n")
        self.assertEqual(code, 2)
        self.assertEqual(records(out), [[b"a", b"exec", b"A", b"Makefile"],
                                        [b"c", b"ci", b"A", b".gitlab-ci.yml"]])
        self.assertEqual(err, b"git-surface: lone\\xc3\\xa9: no merge base with main\n"
                              b"git-surface: lone2: no merge base with main\n")

    def test_empty_input_is_nothing_found(self):
        self.assertEqual(self.repo.surface("main", data=""), (0, b"", b""))

    def test_help_and_version(self):
        code, out, _ = self.repo.surface("-h")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(b"usage: git surface"))
        code, out, _ = self.repo.surface("--version", "nope")
        self.assertEqual((code, out), (0, b"git-surface 0.1.0\n"))

    @unittest.skipIf(os.name == "nt", "Windows file names cannot hold a TAB")
    def test_tab_in_path_needs_z(self):
        self.repo.branch("b")
        self.repo.write("a\tb.sh", "x\n")
        self.repo.commit("tab")
        code, _, err = self.repo.surface("main", data="b\n")
        self.assertEqual(code, 2)
        self.assertIn(b"use -z", err)
        code, out, _ = self.repo.surface("-z", "main", data="b\0")
        self.assertEqual((code, out), (1, b"b\texec\tA\ta\tb.sh\0"))


if __name__ == "__main__":
    unittest.main()
