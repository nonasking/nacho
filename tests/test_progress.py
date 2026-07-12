"""progress.find_append_anchor — '## 진행 일지' 섹션 삽입 지점 계산."""
import unittest

from nacho import progress as prog


def _para(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": text}]},
    }


def _heading(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "heading_2",
        "heading_2": {"rich_text": [{"plain_text": text}]},
    }


def _bullet(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"plain_text": text}]},
    }


class FindAppendAnchorTest(unittest.TestCase):
    def test_no_heading_returns_none(self):
        blocks = [_para("p1", "그냥 본문"), _bullet("b1", "메모")]
        self.assertIsNone(prog.find_append_anchor(blocks))

    def test_section_ends_at_next_heading(self):
        # build_body_blocks 스타일: 헤딩이 '#...' paragraph 인 경우
        blocks = [
            _para("h1", "## 진행 일지"),
            _bullet("b1", "2026-07-01: 시작"),
            _bullet("b2", "2026-07-02: 진행"),
            _para("h2", "## Session"),
            _para("p1", "abc-123"),
        ]
        self.assertEqual(prog.find_append_anchor(blocks), "b2")

    def test_real_heading_block_and_last_section(self):
        blocks = [
            _heading("h0", "개요"),
            _para("p0", "설명"),
            _heading("h1", "진행 일지"),
            _bullet("b1", "메모"),
        ]
        self.assertEqual(prog.find_append_anchor(blocks), "b1")

    def test_empty_section_anchors_on_heading_itself(self):
        blocks = [_heading("h1", "진행 일지"), _heading("h2", "Session")]
        self.assertEqual(prog.find_append_anchor(blocks), "h1")


if __name__ == "__main__":
    unittest.main()
