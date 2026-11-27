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

STATES = """
## 人物状态与信息变化

| 人物 | 生效章／场 | 状态项 | 状态 | 出处 |
| --- | --- | --- | --- | --- |
| 蒋禾 | 300.2 | 与秦乌的关系 | FUTURE_SCENE | 300，南门 |
| 蒋禾 | 5 | 与秦乌的关系 | OLD_ALLIANCE | 5，渡口 |
| 蒋禾 | 300.1 | 与秦乌的关系 | TEMPORARY_TRUCE | 300，街口 |
| 蒋禾 | `第299章` | 与秦乌的关系 | SEPARATED | E-099 |
| 蒋禾 | 299.3 | 所在地 | DIFFERENT_ITEM | 299，酒馆 |
| 蒋禾的姐姐 | 299.4 | 与秦乌的关系 | DIFFERENT_PERSON | 299，渡口 |
"""

DEPENDENCIES = """
## 后文依赖

| 事件编号 | 使用位置 | 依赖点 | 正文锚点 |
| --- | --- | --- | --- |
| E-018 | 846.1 | 把目击当成证据 | 改口段 |
| `e-018` | 321.2 | 据此认出车夫 | 第二句对白 |
| E-0180 | 322.1 | 另一件事 | 街口 |
| E-018 | 75 | 拒绝再作证 | 门边对白 |
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

    def query_relationship(self, before):
        return self.run_cli("state", "--person", "蒋禾", "--item", "与秦乌的关系",
                            "--before", before)

    def test_state_uses_latest_effective_chapter_and_ignores_future_and_other_fields(self):
        self.archive.write_text(ARCHIVE + STATES, encoding="utf-8")
        result = self.query_relationship("300")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SEPARATED | E-099", result.stdout)
        for excluded in ("OLD_ALLIANCE", "TEMPORARY_TRUCE", "FUTURE_SCENE",
                         "DIFFERENT_ITEM", "DIFFERENT_PERSON"):
            self.assertNotIn(excluded, result.stdout)

    def test_state_includes_earlier_scene_but_not_the_requested_scene(self):
        self.archive.write_text(ARCHIVE + STATES, encoding="utf-8")
        result = self.query_relationship("300.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TEMPORARY_TRUCE", result.stdout)
        self.assertNotIn("FUTURE_SCENE", result.stdout)

    def test_state_does_not_guess_legacy_dates_or_unspecified_same_chapter_scenes(self):
        for when, before in (("新年后", "300"), ("300", "300.2"), ("299.1", "300")):
            with self.subTest(when=when, before=before):
                row = f"| 蒋禾 | {when} | 与秦乌的关系 | UNRESOLVED | E-042 |\n"
                self.archive.write_text(ARCHIVE + STATES + row, encoding="utf-8")
                result = self.query_relationship(before)
                self.assertEqual(result.returncode, 1)
                self.assertIn("verify the source", result.stdout)
                self.assertNotIn("[state]", result.stdout)

    def test_state_rejects_duplicate_latest_and_reports_no_earlier_record(self):
        duplicate = "| 蒋禾 | 299 | 与秦乌的关系 | CONFLICT | E-042 |\n"
        self.archive.write_text(ARCHIVE + STATES + duplicate, encoding="utf-8")
        result = self.query_relationship("300")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Ambiguous latest state", result.stdout)
        self.assertNotIn("[state]", result.stdout)
        result = self.query_relationship("5")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No recorded state strictly before", result.stdout)

    def test_impact_finds_only_explicit_uses_of_removed_event_in_story_order(self):
        self.archive.write_text(ARCHIVE + DEPENDENCIES, encoding="utf-8")
        result = self.run_cli("impact", "--event", "e-018", "--limit", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 recorded direct dependency", result.stdout)
        self.assertLess(result.stdout.index("拒绝再作证"), result.stdout.index("据此认出车夫"))
        self.assertIn("--offset 2", result.stdout)
        self.assertNotIn("另一件事", result.stdout)
        self.assertNotIn("把目击当成证据", result.stdout)
        page = self.run_cli("impact", "--event", "E-018", "--limit", "2", "--offset", "2")
        self.assertIn("把目击当成证据", page.stdout)
        self.assertNotIn("拒绝再作证", page.stdout)

    def test_impact_distinguishes_no_records_from_malformed_records(self):
        self.archive.write_text(ARCHIVE + DEPENDENCIES, encoding="utf-8")
        result = self.run_cli("impact", "--event", "E-999")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 recorded direct dependency", result.stdout)
        self.assertIn("coverage may be incomplete", result.stdout)
        self.archive.write_text(ARCHIVE + DEPENDENCIES.replace("846.1", "旧稿末尾"),
                                encoding="utf-8")
        result = self.run_cli("impact", "--event", "E-018")
        self.assertEqual(result.returncode, 1)
        self.assertIn("verify the archive", result.stdout)
        self.assertNotIn("[dependency]", result.stdout)

    def test_retrieval_at_thousand_chapter_scale_remains_targeted(self):
        history = "".join(
            f"| 蒋禾 | {chapter}.1 | 与秦乌的关系 | STATE_{chapter:04} | E-{chapter:04} |\n"
            for chapter in range(1000, 0, -1)
        )
        events = "".join(
            f"| E-{chapter:04} | EVENT_{chapter:04} | {chapter} |\n"
            for chapter in range(1, 1001)
        )
        event_table = "\n## 关键事件与时间线\n\n| 编号 | 经过 | 出处 |\n| --- | --- | --- |\n"
        state_header = STATES.split("| 蒋禾 |", 1)[0]
        self.archive.write_text(
            event_table + events + state_header + history + DEPENDENCIES, encoding="utf-8"
        )
        result = self.query_relationship("1000")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATE_0999", result.stdout)
        self.assertNotIn("STATE_1000", result.stdout)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        result = self.query_relationship("1000.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATE_1000", result.stdout)
        result = self.run_cli("read", "--event", "E-0006")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EVENT_0006", result.stdout)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        result = self.run_cli("impact", "--event", "E-018")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("[dependency]"), 3)

if __name__ == "__main__":
    unittest.main()
