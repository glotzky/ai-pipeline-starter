"""Every YAML file in the template must parse. GitHub rejects an invalid workflow file outright (the run shows
the file path as its name and fails in 0 seconds), and nothing else in the pipeline would notice."""
import re
import unittest

from helpers import REPO

FILES = sorted((REPO / "template" / ".github").rglob("*.yml"))
KEYLIKE = re.compile(r"""^\s*(- )?(["'][^"']+["']|[\w.\-/]+):(\s|$)|^\s*- |^\s*#""")


def block_scalar_problems(text):
    """Dependency-free check: after a `run: |` block ends (a line indented less than the block), the next line must
    look like a YAML key, list item or comment. Text left at a lower indent is the classic way to break a workflow."""
    problems, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:- )?[\w-]+:\s*[|>][+-]?\s*$", lines[i])
        if not m:
            i += 1
            continue
        key_indent = len(m.group(1))
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            break
        block_indent = len(lines[j]) - len(lines[j].lstrip())
        k = j
        while k < len(lines) and (not lines[k].strip() or len(lines[k]) - len(lines[k].lstrip()) >= block_indent):
            k += 1
        if k < len(lines) and lines[k].strip() and not KEYLIKE.match(lines[k]):
            problems.append(f"line {k + 1}: {lines[k][:60]!r} ends the block scalar that started on line {i + 1}")
        i = k
    return problems


class YamlTests(unittest.TestCase):
    def test_there_are_files_to_check(self):
        self.assertGreater(len(FILES), 10)

    def test_no_run_block_is_broken_by_text_at_a_lower_indent(self):
        for f in FILES:
            self.assertEqual(block_scalar_problems(f.read_text()), [], f.name)

    def test_the_check_itself_catches_the_bug_that_broke_update_check(self):
        broken = "jobs:\n  a:\n    steps:\n      - run: |\n          echo hi\n          gh issue create --body \"x\n\nTo update (your edits are kept):\n\n\"\n"
        self.assertTrue(block_scalar_problems(broken))

    def test_every_file_parses_with_a_real_yaml_parser_when_one_is_installed(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed (pip install pyyaml to run this check)")
        for f in FILES:
            with self.subTest(file=f.name):
                yaml.safe_load(f.read_text())


if __name__ == "__main__":
    unittest.main()
