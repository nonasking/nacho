"""notion_client — 오류 매핑 + 연결 오류 재시도 (네트워크 없이 mock)."""
import unittest
from unittest import mock

import requests

from nacho import notion_client as nc


def _resp(status_code: int, message: str = "", json_body: dict | None = None):
    r = mock.Mock(spec=requests.Response)
    r.status_code = status_code
    r.text = message
    if json_body is None:
        json_body = {"message": message} if message else {}
    r.json.return_value = json_body
    return r


class FormatErrorTest(unittest.TestCase):
    def test_401_actionable(self):
        msg = nc._format_error(_resp(401, "API token is invalid."))
        self.assertIn("401 인증 실패", msg)
        self.assertIn("nacho init --force", msg)

    def test_403_mentions_capabilities(self):
        msg = nc._format_error(_resp(403))
        self.assertIn("403 권한 없음", msg)
        self.assertIn("capabilities", msg)

    def test_404_mentions_connections(self):
        msg = nc._format_error(_resp(404, "Could not find database."))
        self.assertIn("404", msg)
        self.assertIn("Connections", msg)

    def test_429_rate_limited(self):
        msg = nc._format_error(_resp(429))
        self.assertIn("429 요청 한도 초과", msg)

    def test_5xx_server_error_with_detail(self):
        msg = nc._format_error(_resp(503, "service unavailable"))
        self.assertIn("503 Notion 서버 오류", msg)
        self.assertIn("service unavailable", msg)


class RequestRetryTest(unittest.TestCase):
    def setUp(self):
        self.session = mock.Mock(spec=requests.Session)
        patcher = mock.patch.object(nc, "_get_session", return_value=self.session)
        patcher.start()
        self.addCleanup(patcher.stop)
        sleep_patcher = mock.patch.object(nc.time, "sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def test_http_error_raises_clean_notion_api_error(self):
        self.session.request.return_value = _resp(401, "bad token")
        with self.assertRaises(nc.NotionApiError) as ctx:
            nc.get_database("db-id")
        self.assertIn("401 인증 실패", str(ctx.exception))

    def test_connection_error_retries_once_then_succeeds(self):
        ok = _resp(200, json_body={"id": "db-id"})
        self.session.request.side_effect = [requests.ConnectionError("boom"), ok]
        self.assertEqual(nc.get_database("db-id"), {"id": "db-id"})
        self.assertEqual(self.session.request.call_count, 2)

    def test_connection_error_exhausted_raises(self):
        self.session.request.side_effect = requests.ConnectionError("boom")
        with self.assertRaises(nc.NotionApiError) as ctx:
            nc.get_page("page-id")
        self.assertIn("네트워크 오류", str(ctx.exception))
        self.assertEqual(self.session.request.call_count, 2)

    def test_append_block_children_passes_after(self):
        self.session.request.return_value = _resp(200, json_body={"results": []})
        nc.append_block_children("blk", [{"type": "bulleted_list_item"}], after="anchor-id")
        kwargs = self.session.request.call_args.kwargs
        self.assertEqual(kwargs["json"]["after"], "anchor-id")


if __name__ == "__main__":
    unittest.main()
