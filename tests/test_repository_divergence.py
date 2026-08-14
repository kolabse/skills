from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "synchronize-git-repositories"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import classify_repository  # noqa: E402


def git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class RepositoryDivergenceTests(unittest.TestCase):
    def make_remote_and_clone(self, root: Path) -> tuple[Path, Path]:
        remote = root / "remote.git"
        repository = root / "repository"
        git(root, "init", "--bare", str(remote))
        git(root, "clone", str(remote), str(repository))
        git(repository, "config", "user.name", "Divergence Test")
        git(repository, "config", "user.email", "divergence@example.invalid")
        (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
        git(repository, "add", "tracked.txt")
        git(repository, "commit", "-m", "base")
        git(repository, "push", "-u", "origin", "HEAD:main")
        git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        return remote, repository

    def test_identifies_diverged_commits_with_identical_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, repository = self.make_remote_and_clone(root)
            (repository / "tracked.txt").write_text("equivalent\n", encoding="utf-8")
            git(repository, "commit", "-am", "local form")
            other = root / "other"
            git(root, "clone", str(remote), str(other))
            git(other, "config", "user.name", "Divergence Test")
            git(other, "config", "user.email", "divergence@example.invalid")
            (other / "tracked.txt").write_text("equivalent\n", encoding="utf-8")
            git(other, "commit", "-am", "squashed form")
            git(other, "push", "origin", "main")
            git(repository, "fetch", "origin")

            result = classify_repository.classify(repository)

            self.assertEqual("diverged", result["classification"])
            self.assertEqual("identical-tree", result["divergence_equivalence"])
            self.assertEqual(
                "backup-then-align-with-user-approval", result["recommended_action"]
            )
            self.assertFalse(result["mutates"])

    def test_preserves_ordinary_divergence_as_manual_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, repository = self.make_remote_and_clone(root)
            (repository / "local.txt").write_text("local\n", encoding="utf-8")
            git(repository, "add", "local.txt")
            git(repository, "commit", "-m", "local")
            other = root / "other"
            git(root, "clone", str(remote), str(other))
            git(other, "config", "user.name", "Divergence Test")
            git(other, "config", "user.email", "divergence@example.invalid")
            (other / "remote.txt").write_text("remote\n", encoding="utf-8")
            git(other, "add", "remote.txt")
            git(other, "commit", "-m", "remote")
            git(other, "push", "origin", "main")
            git(repository, "fetch", "origin")

            result = classify_repository.classify(repository)

            self.assertEqual("diverged", result["classification"])
            self.assertEqual("none", result["divergence_equivalence"])
            self.assertEqual("manual-reconcile", result["recommended_action"])

    def test_worktree_counts_preserve_leading_porcelain_status_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, repository = self.make_remote_and_clone(root)
            (repository / "tracked.txt").write_text("unstaged\n", encoding="utf-8")

            counts = classify_repository.worktree_counts(repository)

            self.assertEqual(
                {"staged": 0, "unstaged": 1, "untracked": 0}, counts
            )


if __name__ == "__main__":
    unittest.main()
