from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / (
    "skills/novel-writing/scripts/query_story_archive.py"
)
FIRST_HASH = "a" * 64
SECOND_HASH = "b" * 64
ARCHIVE = f"""# 《求雨》故事档案

小说及分支：主线

## 归档覆盖

| 章节 | 采用稿 | SHA-256 | 待复核 |
| --- | --- | --- | --- |
| 12 | `chapters/12 final.md` | `{FIRST_HASH}` | |
| 16 | chapters/16.md | {SECOND_HASH} | Check the back door |
| 17 | chapters/17.md | | No hash yet |

## 当前接续点

summary that need not be loaded

## 人物与信息

| 角色 | 状态 |
| --- | --- |
| 乙 | 要解开旧票的谜 |

## 关键事件与时间线

| 编号 | 经过 | 出处 |
| --- | --- | --- |
| E-042 | 三眼的铜匣藏在井里。 | 12，井边 |
| `E-099` | 乙把旧票折成纸船，没见到背面。 | 16，后门 |
| E-100 | 本不相干的旧票掉了。 | 17 |
| E-101 | 又一张旧票。 | 17 |

```markdown
| 编号 | 经过 | 出处 |
| --- | --- | --- |
| E-123 | 又一张旧票，举例不是正典。 | 99 |
```

## 待确认

| 观察 | 关联 | 当前边界 |
| --- | --- | --- |
| 破票角 | E-099 | 旧票有红蜡，但没有证明两张同源。 |
| 无关 | 17 | {'背景' * 90}砖缝{'议论' * 90} |
"""


class QueryStoryArchiveTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.archive = Path(directory.name) / "story-bible.md"
        self.archive.write_text(ARCHIVE, encoding="utf-8-sig")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--archive", str(self.archive), *args],
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_overview_does_not_print_version_rows_or_prose(self):
        result = self.run_cli("overview")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("主线", result.stdout)
        self.assertIn("coverage rows: 3", result.stdout)
        self.assertNotIn(FIRST_HASH, result.stdout)
        self.assertNotIn("chapters/", result.stdout)
        self.assertNotIn("summary that need not be loaded", result.stdout)

    def test_find_defaults_to_two_real_events_and_does_not_hide_overflow(self):
        result = self.run_cli("find", "--term", "旧票")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 match(es); showing 2", result.stdout)
        self.assertIn("E-099", result.stdout)
        self.assertIn("E-100", result.stdout)
        self.assertNotIn("E-101", result.stdout)
        self.assertNotIn("E-123", result.stdout)
        self.assertNotIn("红蜡", result.stdout)

    def test_pending_preview_locates_exact_full_record_without_expansion(self):
        hits = self.run_cli("find", "--term", "红蜡", "--kind", "pending")
        number = re.search(r"L(\d+) \[pending\]", hits.stdout).group(1)
        details = self.run_cli("read", "--line", number)
        self.assertEqual(details.returncode, 0, details.stderr)
        self.assertIn("没有证明两张同源", details.stdout)
        self.assertNotIn("折成纸船", details.stdout)

    def test_long_previews_stay_short_and_include_the_hit(self):
        result = self.run_cli("find", "--term", "砖缝", "--kind", "pending")
        self.assertIn("砖缝", result.stdout)
        self.assertLess(len(result.stdout.splitlines()[-1]), 125)

    def test_retrieval_returns_only_selected_row_and_fingerprint(self):
        result = self.run_cli(
            "read", "--event", "e-042", "--event", "E-042",
            "--source", "chapters\\12 final.md",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("三眼的铜匣"), 1)
        self.assertIn(f"chapters/12 final.md {FIRST_HASH}", result.stdout)
        self.assertNotIn(SECOND_HASH, result.stdout)
        self.assertNotIn("E-099", result.stdout)

    def test_unknown_duplicate_and_unversioned_selections_report_failure(self):
        self.archive.write_text(
            ARCHIVE.replace("| E-100 |", "| E-042 |"), encoding="utf-8"
        )
        result = self.run_cli(
            "read", "--event", "E-042", "--event", "E-777",
            "--source", "chapters/17.md", "--source", "chapters/16.md",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("E-042: ambiguous", result.stdout)
        self.assertIn("E-777: not found", result.stdout)
        self.assertIn("chapters/17.md: no recorded SHA-256", result.stdout)
        self.assertIn("Check the back door", result.stdout)
        self.assertNotIn("三眼的铜匣", result.stdout)

    def test_unsupported_archive_falls_back_instead_of_dumping(self):
        self.archive.write_text("# 雨\n手写内容不要转存。", encoding="utf-8")
        result = self.run_cli("overview")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("targeted text search", result.stderr)


if __name__ == "__main__":
    unittest.main()
