"""main 헬퍼 — _auto_map_fields / _pick_page_by_title (네트워크 없이 mock)."""
import unittest
from unittest import mock

from nacho import main


def _page(title: str) -> dict:
    return {
        "id": f"id-{title}",
        "properties": {"이름": {"title": [{"plain_text": title}]}},
    }


class AutoMapFieldsTest(unittest.TestCase):
    def test_type_only_and_hint_matching(self):
        props = {
            "이름": {"type": "title"},
            "상태": {"type": "status"},
            "마감일": {"type": "date"},
            "시작일": {"type": "date"},
            "링크": {"type": "url"},
        }
        mapping = main._auto_map_fields(props)
        self.assertEqual(mapping["title"], "이름")
        self.assertEqual(mapping["status"], "상태")
        self.assertEqual(mapping["due_date"], "마감일")
        self.assertEqual(mapping["start_date"], "시작일")
        self.assertEqual(mapping["link"], "링크")

    def test_unmatched_keys_map_to_empty_string(self):
        mapping = main._auto_map_fields({"이름": {"type": "title"}})
        self.assertEqual(mapping["title"], "이름")
        self.assertEqual(mapping["status"], "")
        self.assertEqual(mapping["due_date"], "")

    def test_property_not_reused_across_keys(self):
        # rich_text "Session" 은 session_id 가 먼저 소비 — status_note 재사용 금지
        props = {"Session ID": {"type": "rich_text"}}
        mapping = main._auto_map_fields(props)
        self.assertEqual(mapping["session_id"], "Session ID")
        self.assertEqual(mapping["status_note"], "")

    def test_wrong_type_not_matched_despite_hint(self):
        props = {"마감일": {"type": "rich_text"}}
        mapping = main._auto_map_fields(props)
        self.assertEqual(mapping["due_date"], "")


class PickPageByTitleTest(unittest.TestCase):
    def test_no_match_returns_none(self):
        with mock.patch.object(main.nc, "query_database", return_value=[]):
            self.assertIsNone(main._pick_page_by_title("없는것", "db", "이름"))

    def test_single_match_returned_without_prompt(self):
        page = _page("큐레이션")
        with mock.patch.object(main.nc, "query_database", return_value=[page]), \
                mock.patch("builtins.input", side_effect=AssertionError("input 호출 금지")):
            self.assertIs(main._pick_page_by_title("큐레", "db", "이름"), page)

    def test_multiple_matches_prompts_for_number(self):
        pages = [_page("a"), _page("b"), _page("c")]
        with mock.patch.object(main.nc, "query_database", return_value=pages), \
                mock.patch("builtins.input", return_value="2"):
            self.assertIs(main._pick_page_by_title("q", "db", "이름"), pages[1])

    def test_invalid_or_out_of_range_input_returns_none(self):
        pages = [_page("a"), _page("b")]
        with mock.patch.object(main.nc, "query_database", return_value=pages):
            with mock.patch("builtins.input", return_value="abc"):
                self.assertIsNone(main._pick_page_by_title("q", "db", "이름"))
            with mock.patch("builtins.input", return_value="9"):
                self.assertIsNone(main._pick_page_by_title("q", "db", "이름"))


if __name__ == "__main__":
    unittest.main()
