"""page_draft — Notion API 길이·개수 제한 대응."""
import unittest

from nacho import page_draft as pd


class BodyBlocksLimitTest(unittest.TestCase):
    def test_long_line_split_into_2000_char_rich_text(self):
        blocks = pd.build_body_blocks("가" * 4500)
        rich = blocks[0]["paragraph"]["rich_text"]
        self.assertEqual([len(r["text"]["content"]) for r in rich], [2000, 2000, 500])
        self.assertEqual("".join(r["text"]["content"] for r in rich), "가" * 4500)

    def test_empty_line_has_no_rich_text(self):
        blocks = pd.build_body_blocks("a\n\nb")
        self.assertEqual(blocks[1]["paragraph"]["rich_text"], [])

    def test_chunk_blocks_respects_100_limit(self):
        blocks = pd.build_body_blocks("\n".join(str(i) for i in range(250)))
        sizes = [len(b) for b in pd.chunk_blocks(blocks)]
        self.assertEqual(sizes, [100, 100, 50])

    def test_chunk_blocks_empty(self):
        self.assertEqual(pd.chunk_blocks([]), [])


if __name__ == "__main__":
    unittest.main()
