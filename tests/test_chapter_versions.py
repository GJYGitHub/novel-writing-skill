import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / (
    "skills/novel-writing/scripts/check_chapter_versions.py"
)


class ChapterVersionsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "novel"
        (self.root / "chapters").mkdir(parents=True)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_snapshot_and_new_process_check(self):
        name = "chapters/01 final.md"
        text = b"private prose not shown in the version report\r\n"
        (self.root / name).write_bytes(text)
        snapshot = self.run_cli("snapshot", name)
        self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
        data, = json.loads(snapshot.stdout)
        self.assertEqual(data["sha256"], hashlib.sha256(text).hexdigest())
        check = self.run_cli("check", "--expect", name, data["sha256"].upper())
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)[0]["status"], "unchanged")
        self.assertNotIn("private prose", snapshot.stdout + check.stdout)
        self.assertEqual((self.root / name).read_bytes(), text)

    def test_in_place_rewrite_and_missing_file_are_reported_together(self):
        names = ["chapters/01.md", "chapters/02.md", "chapters/03.md"]
        for name in names:
            (self.root / name).write_bytes(b"The key changed hands.")
        baseline = json.loads(self.run_cli("snapshot", *names).stdout)
        (self.root / names[0]).write_bytes(b"The key fell in water.")
        (self.root / names[1]).unlink()
        pairs = [
            value for item in baseline
            for value in ("--expect", item["path"], item["sha256"])
        ]
        check = self.run_cli("check", *pairs)
        self.assertEqual(check.returncode, 1)
        self.assertEqual([item["status"] for item in json.loads(check.stdout)],
                         ["changed", "missing", "unchanged"])

    def test_unrelated_chapter_is_not_scanned(self):
        selected = "chapters/01.md"
        (self.root / selected).write_text("selected", encoding="utf-8")
        other = self.root / "chapters/02.md"
        other.write_text("unrelated", encoding="utf-8")
        original = json.loads(self.run_cli("snapshot", selected).stdout)[0]
        other.write_text("a rewrite elsewhere", encoding="utf-8")
        check = self.run_cli("check", "--expect", selected, original["sha256"])
        self.assertEqual(check.returncode, 0)
        self.assertEqual([entry["path"] for entry in json.loads(check.stdout)], [selected])

    def test_outside_paths_and_non_files_have_no_fingerprint(self):
        outside = self.root.parent / "outside.md"
        outside.write_bytes(b"outside")
        check = self.run_cli("snapshot", "../outside.md", str(outside), "chapters")
        self.assertEqual(check.returncode, 1)
        self.assertEqual(json.loads(check.stdout), [
            {"path": "../outside.md", "status": "invalid_path"},
            {"path": str(outside), "status": "invalid_path"},
            {"path": "chapters", "status": "unreadable"},
        ])

    def test_invalid_expected_fingerprint_is_a_usage_error(self):
        check = self.run_cli("check", "--expect", "chapters/01.md", "bad-hash")
        self.assertEqual(check.returncode, 2)
        self.assertEqual(check.stdout, "")


if __name__ == "__main__":
    unittest.main()
