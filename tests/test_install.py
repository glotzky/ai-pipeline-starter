"""The installer: copies the template, skips junk, fills in CODEOWNERS, never overwrites your own files."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import REPO

INSTALL = REPO / "install" / "install.sh"


def make_repo(remote=None):
    d = Path(tempfile.mkdtemp(prefix="install-test-"))
    subprocess.run(["git", "init", "-q", "-b", "main", str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)
    return d


def install(target, *extra):
    return subprocess.run(["bash", str(INSTALL), str(target), *extra], capture_output=True, text=True)


class InstallerTests(unittest.TestCase):
    def test_installs_the_expected_files(self):
        d = make_repo()
        r = install(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("pipeline/run.py", "pipeline/run_metrics.py", "metrics/schema.json", "metrics/summarize.py",
                  "metrics/runs/.gitkeep", ".github/workflows/pipeline.yml", ".github/workflows/ci.yml",
                  ".claude/agents/planner.md", "CLAUDE.md"):
            self.assertTrue((d / f).exists(), f)

    def test_python_caches_and_ds_store_are_never_copied(self):
        junk = [REPO / "template" / "pipeline" / "__pycache__" / "x.cpython-314.pyc",
                REPO / "template" / "metrics" / "__pycache__" / "y.cpython-314.pyc",
                REPO / "template" / "metrics" / "z.pyc", REPO / "template" / ".DS_Store"]
        created = []
        try:
            for j in junk:
                j.parent.mkdir(parents=True, exist_ok=True)
                j.write_bytes(b"junk")
                created.append(j)
            d = make_repo()
            self.assertEqual(install(d).returncode, 0)
            found = [p for p in d.rglob("*") if p.name.endswith(".pyc") or p.name == ".DS_Store" or p.name == "__pycache__"]
            self.assertEqual(found, [])
        finally:
            for j in created:
                j.unlink(missing_ok=True)
            for folder in ("pipeline", "metrics"):
                cache = REPO / "template" / folder / "__pycache__"
                try:
                    cache.rmdir()
                except OSError:
                    pass

    def test_environment_name_is_rewritten_in_every_workflow(self):
        d = make_repo()
        install(d, "--env", "my_env")
        text = "".join(p.read_text() for p in (d / ".github" / "workflows").glob("*.yml"))
        self.assertIn("environment: my_env", text)
        self.assertNotIn("environment: pipeline", text)

    def test_codeowners_uses_the_github_username_from_the_remote(self):
        d = make_repo("https://github.com/someone/project.git")
        install(d)
        self.assertIn("@someone", (d / ".github" / "CODEOWNERS").read_text())
        self.assertNotIn("@OWNER", (d / ".github" / "CODEOWNERS").read_text())

    def test_existing_user_files_are_kept_and_a_copy_is_written_beside_them(self):
        d = make_repo()
        (d / "CLAUDE.md").write_text("MINE")
        (d / ".github").mkdir()
        (d / ".github" / "CODEOWNERS").write_text("MY OWNERS")
        install(d)
        self.assertEqual((d / "CLAUDE.md").read_text(), "MINE")
        self.assertTrue((d / "CLAUDE.md.pipeline-new").exists())
        self.assertEqual((d / ".github" / "CODEOWNERS").read_text(), "MY OWNERS")

    def test_gitignore_lines_are_appended_not_replaced_and_rerun_is_idempotent(self):
        d = make_repo()
        (d / ".gitignore").write_text("my-own-rule\n")
        install(d)
        install(d)
        lines = (d / ".gitignore").read_text().splitlines()
        self.assertIn("my-own-rule", lines)
        self.assertEqual(lines.count("__pycache__/"), 1)

    def test_first_install_over_an_older_install_without_a_manifest_completes(self):
        d = make_repo()
        (d / "pipeline").mkdir()
        (d / "pipeline" / "run.py").write_text("# older run.py\n")
        r = install(d, "--env", "fire_check_env")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Next steps", r.stdout)
        self.assertTrue((d / ".pipeline-version").exists())

    def test_action_versions_the_project_already_uses_are_kept(self):
        d = make_repo()
        (d / ".github" / "workflows").mkdir(parents=True)
        (d / ".github" / "workflows" / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v7\n  - uses: actions/setup-node@v7\n")
        self.assertEqual(install(d).returncode, 0)
        text = (d / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("actions/checkout@v7", text)
        self.assertIn("actions/setup-node@v7", text)
        self.assertNotIn("actions/checkout@v4", text)
        self.assertIn("run:", text)

    def test_refuses_a_folder_that_is_not_a_git_repo(self):
        d = Path(tempfile.mkdtemp())
        self.assertNotEqual(install(d).returncode, 0)


# --------------------------------------------------------------------------- upgrades
import shutil


def make_starter(version="1.0.0"):
    """A private copy of the starter we can edit, so tests can simulate 'a newer version'."""
    d = Path(tempfile.mkdtemp(prefix="starter-copy-"))
    shutil.copytree(REPO / "install", d / "install")
    shutil.copytree(REPO / "template", d / "template", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (d / "VERSION").write_text(version + "\n")
    return d


def run_install(starter, target, *extra):
    return subprocess.run(["bash", str(starter / "install" / "install.sh"), str(target), *extra], capture_output=True, text=True)


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.starter = make_starter("1.0.0")
        self.repo = make_repo("https://github.com/someone/project.git")
        r = run_install(self.starter, self.repo, "--env", "my_env")
        self.assertEqual(r.returncode, 0, r.stderr)

    def manifest(self):
        return (self.repo / ".pipeline-version").read_text()

    def test_install_records_version_environment_and_source(self):
        m = self.manifest()
        self.assertIn("version=1.0.0", m)
        self.assertIn("env=my_env", m)
        self.assertRegex(m, r"source=\S+/\S+")
        self.assertRegex(m, r"[0-9a-f]{64} \./pipeline/run\.py")

    def test_your_own_files_are_not_in_the_manifest(self):
        self.assertNotIn("./CLAUDE.md", self.manifest())

    def test_upgrade_with_nothing_new_changes_nothing(self):
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 new, 0 updated", r.stdout)
        self.assertEqual(list(self.repo.rglob("*.pipeline-new")), [])

    def test_untouched_file_is_updated_and_workflows_keep_your_environment_name(self):
        (self.starter / "VERSION").write_text("1.1.0\n")
        (self.starter / "template" / "pipeline" / "run.py").write_text("# new run.py\n")
        wf = self.starter / "template" / ".github" / "workflows" / "ci.yml"
        wf.write_text(wf.read_text() + "\n# newer\n")
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.repo / "pipeline" / "run.py").read_text(), "# new run.py\n")
        self.assertIn("# newer", (self.repo / ".github" / "workflows" / "ci.yml").read_text())
        self.assertIn("version=1.1.0", self.manifest())
        text = "".join(p.read_text() for p in (self.repo / ".github" / "workflows").glob("*.yml"))
        self.assertIn("environment: my_env", text)
        self.assertNotIn("environment: pipeline", text)

    def test_a_file_you_edited_is_kept_and_the_new_version_is_written_beside_it(self):
        (self.repo / "pipeline" / "run.py").write_text("# MY CHANGE\n")
        (self.starter / "template" / "pipeline" / "run.py").write_text("# upstream change\n")
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertIn("you edited", r.stdout)
        self.assertEqual((self.repo / "pipeline" / "run.py").read_text(), "# MY CHANGE\n")
        self.assertEqual((self.repo / "pipeline" / "run.py.pipeline-new").read_text(), "# upstream change\n")

    def test_a_file_you_edited_stays_flagged_until_you_merge_it(self):
        (self.repo / "pipeline" / "run.py").write_text("# MY CHANGE\n")
        (self.starter / "template" / "pipeline" / "run.py").write_text("# upstream change\n")
        run_install(self.starter, self.repo, "--upgrade")
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertIn("you edited", r.stdout)
        (self.repo / "pipeline" / "run.py").write_text("# upstream change\n")  # you merged it
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertNotIn("you edited", r.stdout)

    def test_claude_md_is_never_overwritten_by_an_upgrade(self):
        (self.repo / "CLAUDE.md").write_text("MINE")
        (self.starter / "template" / "CLAUDE.md").write_text("upstream")
        run_install(self.starter, self.repo, "--upgrade")
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "MINE")
        self.assertEqual((self.repo / "CLAUDE.md.pipeline-new").read_text(), "upstream")

    def test_new_files_are_added_and_removed_files_are_reported_not_deleted(self):
        (self.starter / "template" / "pipeline" / "brand_new.py").write_text("x = 1\n")
        (self.starter / "template" / "pipeline" / "project_plan.py").unlink()
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertTrue((self.repo / "pipeline" / "brand_new.py").exists())
        self.assertIn("no longer shipped", r.stdout)
        self.assertTrue((self.repo / "pipeline" / "project_plan.py").exists())

    def test_upgrade_without_a_manifest_explains_what_to_do(self):
        other = make_repo()
        r = run_install(self.starter, other, "--upgrade")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("without --upgrade", r.stdout)

    def test_update_check_workflow_ships_and_changes_no_files(self):
        text = (REPO / "template" / ".github" / "workflows" / "update-check.yml").read_text()
        self.assertIn("schedule:", text)
        self.assertNotIn("environment:", "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#")))
        self.assertIn("contents: read", text)


class SelfUpdateTests(unittest.TestCase):
    def setUp(self):
        self.starter = make_starter("1.0.0")
        self.repo = make_repo("https://github.com/someone/project.git")
        self.assertEqual(run_install(self.starter, self.repo, "--env", "my_env").returncode, 0)
        # the "GitHub release" of a newer version, as a tarball with a top-level folder like GitHub makes
        self.newer = make_starter("1.2.0")
        (self.newer / "template" / "pipeline" / "run.py").write_text("# from 1.2.0\n")
        self.tgz = Path(tempfile.mkdtemp()) / "s.tar.gz"
        subprocess.run(["tar", "-czf", str(self.tgz), "-C", str(self.newer.parent), self.newer.name], check=True)

    def update(self, *args, **env):
        e = dict(os.environ, PIPELINE_TARBALL=str(self.tgz), **env)
        return subprocess.run(["bash", str(self.repo / "pipeline" / "update.sh"), *args], capture_output=True, text=True, cwd=self.repo, env=e)

    def test_a_dependabot_version_bump_is_not_treated_as_your_edit(self):
        wf = self.repo / ".github" / "workflows" / "ci.yml"
        wf.write_text(wf.read_text().replace("actions/checkout@v4", "actions/checkout@v7"))
        (self.starter / "VERSION").write_text("1.0.1\n")
        r = run_install(self.starter, self.repo, "--upgrade")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("you edited", r.stdout)
        self.assertEqual(list(self.repo.rglob("*.pipeline-new")), [])
        self.assertIn("actions/checkout@v7", wf.read_text())

    def test_update_script_is_installed_in_projects(self):
        self.assertTrue((self.repo / "pipeline" / "update.sh").exists())

    def test_update_downloads_the_newer_version_and_applies_it(self):
        r = self.update(PIPELINE_LATEST="1.2.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.repo / "pipeline" / "run.py").read_text(), "# from 1.2.0\n")
        self.assertIn("version=1.2.0", (self.repo / ".pipeline-version").read_text())
        self.assertIn("environment: my_env", (self.repo / ".github" / "workflows" / "pipeline.yml").read_text())

    def test_update_keeps_your_edits(self):
        (self.repo / "pipeline" / "run.py").write_text("# MINE\n")
        r = self.update(PIPELINE_LATEST="1.2.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.repo / "pipeline" / "run.py").read_text(), "# MINE\n")
        self.assertEqual((self.repo / "pipeline" / "run.py.pipeline-new").read_text(), "# from 1.2.0\n")

    def test_already_current_does_nothing(self):
        r = self.update(PIPELINE_LATEST="1.0.0")
        self.assertIn("Already up to date", r.stdout)
        self.assertNotIn("version=1.2.0", (self.repo / ".pipeline-version").read_text())

    def test_it_never_commits_or_pushes(self):
        before = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
        self.update(PIPELINE_LATEST="1.2.0")
        after = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
        self.assertEqual(before, after)

    def test_a_download_without_an_installer_is_refused(self):
        bad = Path(tempfile.mkdtemp()) / "bad.tar.gz"
        d = Path(tempfile.mkdtemp()); (d / "x").mkdir(); (d / "x" / "f").write_text("1")
        subprocess.run(["tar", "-czf", str(bad), "-C", str(d), "x"], check=True)
        self.tgz = bad
        r = self.update(PIPELINE_LATEST="1.2.0")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("install/install.sh", r.stdout + r.stderr)
        self.assertEqual((self.repo / "pipeline" / "run.py").read_text() != "# from 1.2.0\n", True)


if __name__ == "__main__":
    unittest.main()
