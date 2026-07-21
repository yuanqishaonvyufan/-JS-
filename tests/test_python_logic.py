from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baidu_web_translate import (  # noqa: E402
    BaiduRiskControlError,
    build_payload,
    collect_translation,
    iter_sse_json,
    load_har_replay_context,
)


class RequestLogicTests(unittest.TestCase):
    def test_payload_matches_frontend_shape(self) -> None:
        payload = build_payload(" hello ", timestamp_ms=1700000000123)
        self.assertEqual(payload["query"], "hello")
        self.assertEqual(payload["milliTimestamp"], 1700000000123)
        self.assertEqual(payload["sseStartTime"], 1700000000123)
        self.assertEqual(payload["corpusIds"], [])
        self.assertTrue(payload["needPhonetic"])
        self.assertFalse(payload["needNewlineCombine"])

    def test_sse_translation(self) -> None:
        lines = [
            'data: {"errno":0,"data":{"event":"StartTranslation","from":"en","to":"zh"}}',
            "",
            'data: {"errno":0,"data":{"event":"Translating","list":[{"id":1,"dst":"你好"}]}}',
            "",
            'data: {"errno":0,"data":{"event":"TranslationSucceed"}}',
            "",
        ]
        target, from_lang, to_lang = collect_translation(iter_sse_json(lines))
        self.assertEqual(target, "你好")
        self.assertEqual((from_lang, to_lang), ("en", "zh"))

    def test_risk_error(self) -> None:
        messages = [{"errno": 995, "errmsg": "request is not authorized"}]
        with self.assertRaises(BaiduRiskControlError):
            collect_translation(messages)

    def test_load_har_replay_context(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://fanyi.baidu.com/ait/text/translate",
                            "headers": [
                                {"name": "Acs-Token", "value": "secret-test-token"},
                                {"name": "Content-Length", "value": "123"},
                                {"name": "User-Agent", "value": "Test Browser"},
                            ],
                            "cookies": [],
                        },
                        "response": {"status": 200},
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.har"
            path.write_text(json.dumps(har), encoding="utf-8")
            context = load_har_replay_context(path)
        self.assertEqual(context.headers["Acs-Token"], "secret-test-token")
        self.assertNotIn("Content-Length", context.headers)


if __name__ == "__main__":
    unittest.main()
