"""lesson_differ 测试——验收用例 6-15"""
import pytest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> list[str]:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return f.readlines()


from app.lesson_parser import parse_lessons, Lesson
from app.lesson_differ import up_diff, down_diff, UpState, DownState, UpCandidate, UpDiffItem, DownDiffItem


class TestUpDiff:
    def test_new_candidate(self):
        """用例6: spoke 有 L14[↑]，hub 无 L14 → new。"""
        hub = parse_lessons(_read_fixture("lesson_hub_basic.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_up_candidates.txt"))
        candidates = [UpCandidate("项目A", l) for l in spoke if l.has_up_marker]
        results = up_diff(hub, candidates)
        l14 = [r for r in results if r.lesson.l_number == 14]
        assert len(l14) == 1
        assert l14[0].state == UpState.NEW

    def test_update_candidate(self):
        """用例7: spoke 有 L8[↑] 文本与 hub L8 不同 → update，diff 非空。"""
        hub = parse_lessons(_read_fixture("lesson_hub_basic.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_up_candidates.txt"))
        candidates = [UpCandidate("项目A", l) for l in spoke if l.has_up_marker]
        results = up_diff(hub, candidates)
        l8 = [r for r in results if r.lesson.l_number == 8]
        assert len(l8) == 1
        assert l8[0].state == UpState.UPDATE
        assert l8[0].diff_text

    def test_already_synced(self):
        """用例8: spoke 有 L8[↑] 文本与 hub L8 完全相同 → already_synced。"""
        hub = parse_lessons(_read_fixture("lesson_hub_basic.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_synced.txt"))
        candidates = [UpCandidate("项目A", l) for l in spoke if l.has_up_marker]
        results = up_diff(hub, candidates)
        assert results[0].state == UpState.ALREADY_SYNCED

    def test_conflict(self):
        """用例9: spoke_A 和 spoke_B 都有 L14[↑] 文本不同 → conflict。"""
        hub = parse_lessons(_read_fixture("lesson_hub_basic.txt"))
        a = parse_lessons(_read_fixture("lesson_spoke_up_candidates.txt"))
        b = parse_lessons(_read_fixture("lesson_spoke_b.txt"))
        candidates = []
        for l in a:
            if l.has_up_marker:
                candidates.append(UpCandidate("项目A", l))
        for l in b:
            if l.has_up_marker:
                candidates.append(UpCandidate("项目B", l))
        results = up_diff(hub, candidates)
        l14 = [r for r in results if r.lesson.l_number == 14]
        assert len(l14) == 2
        for r in l14:
            assert r.state == UpState.CONFLICT
            assert r.conflicting is not None
            assert len(r.conflicting) >= 1

    def test_no_candidates(self):
        """用例10: 无 [↑] 条目 → 返回空列表。"""
        hub = parse_lessons(_read_fixture("lesson_hub_basic.txt"))
        results = up_diff(hub, [])
        assert results == []


class TestDownDiff:
    def test_new_in_hub(self):
        """用例11: hub 有 L14，spoke 无 → new_in_hub。"""
        hub = parse_lessons(_read_fixture("lesson_hub_down.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_down.txt"))
        results = down_diff(hub, spoke)
        l14 = [r for r in results if r.lesson.l_number == 14]
        assert len(l14) == 1
        assert l14[0].state == DownState.NEW_IN_HUB

    def test_content_changed(self):
        """用例12: hub 和 spoke 均有 L8 文本不同 → content_changed。"""
        hub = parse_lessons(_read_fixture("lesson_hub_down.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_down.txt"))
        results = down_diff(hub, spoke)
        l8 = [r for r in results if r.lesson.l_number == 8]
        assert len(l8) == 1
        assert l8[0].state == DownState.CONTENT_CHANGED
        assert l8[0].diff_text

    def test_up_to_date(self):
        """用例13: hub 和 spoke 均有 L1 文本相同 → up_to_date。"""
        hub = parse_lessons(_read_fixture("lesson_hub_down.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_down.txt"))
        results = down_diff(hub, spoke)
        l1 = [r for r in results if r.lesson.l_number == 1]
        assert len(l1) == 1
        assert l1[0].state == DownState.UP_TO_DATE

    def test_spoke_only(self):
        """用例14: spoke 有 L99，hub 无 → spoke_only。"""
        hub = parse_lessons(_read_fixture("lesson_hub_down.txt"))
        spoke = parse_lessons(_read_fixture("lesson_spoke_down.txt"))
        results = down_diff(hub, spoke)
        l99 = [r for r in results if r.lesson.l_number == 99]
        assert len(l99) == 1
        assert l99[0].state == DownState.SPOKE_ONLY

    def test_hub_empty(self):
        """用例15: hub 第二部分空 → 全 spoke_only。"""
        spoke = parse_lessons(_read_fixture("lesson_private_normal.txt"))
        results = down_diff([], spoke)
        assert len(results) == 3
        for r in results:
            assert r.state == DownState.SPOKE_ONLY
