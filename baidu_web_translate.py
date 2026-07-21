"""百度翻译新版网页接口复现：Session + JSON Payload + SSE。

这份代码复现已确认的业务请求，不伪造ACS设备指纹或验证码状态。网页接口可能
返回风控错误；稳定生产任务应使用百度官方开放平台，而不是依赖网页私有接口。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import quote, urlsplit

import requests


PAGE_URL = "https://fanyi.baidu.com/mtpe-individual/transText"
API_URL = "https://fanyi.baidu.com/ait/text/translate"


class BaiduWebError(RuntimeError):
    """网页接口、响应格式或业务错误。"""


class BaiduRiskControlError(BaiduWebError):
    """ACS或验证码风控拒绝请求。"""


@dataclass(frozen=True)
class TranslationResult:
    source: str
    target: str
    from_lang: str
    to_lang: str


@dataclass(frozen=True)
class HarReplayContext:
    """从成功HAR请求中提取的短期浏览器上下文。"""

    headers: dict[str, str]
    cookies: dict[str, str]
    source_file: str


# 这些Header由requests根据实际连接重新计算，不能照搬HAR。
HAR_IGNORED_HEADERS = {
    "accept-encoding",
    "connection",
    "content-length",
    "cookie",
    "host",
}


def load_har_replay_context(path: str | Path) -> HarReplayContext:
    """读取HAR中最近一条成功的普通文本翻译请求。

    不打印、不落盘完整Acs-Token；Token只保留在当前Python进程内。
    """
    har_path = Path(path)
    har = json.loads(har_path.read_text(encoding="utf-8-sig"))
    entries = har.get("log", {}).get("entries", [])

    for entry in reversed(entries):
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        url = str(request.get("url") or "")
        if urlsplit(url).path != "/ait/text/translate":
            continue
        if int(response.get("status") or 0) != 200:
            continue

        raw_headers = {
            str(item.get("name") or ""): str(item.get("value") or "")
            for item in request.get("headers") or []
        }
        acs_token = next(
            (value for name, value in raw_headers.items() if name.lower() == "acs-token"),
            "",
        )
        if not acs_token:
            continue

        headers = {
            name: value
            for name, value in raw_headers.items()
            if name.lower() not in HAR_IGNORED_HEADERS
        }
        cookies = {
            str(item.get("name") or ""): str(item.get("value") or "")
            for item in request.get("cookies") or []
            if item.get("name")
        }
        return HarReplayContext(headers, cookies, str(har_path.resolve()))

    raise BaiduWebError("HAR中没有带Acs-Token且HTTP状态为200的 /ait/text/translate 请求")


def build_payload(
    query: str,
    from_lang: str = "en",
    to_lang: str = "zh",
    *,
    timestamp_ms: int | None = None,
) -> dict[str, object]:
    """等价复现前端业务层的请求体组装。"""
    query = query.strip()
    if not query:
        raise ValueError("query不能为空")
    now_ms = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    # 字段及顺序来自成功HAR中的Request Payload，对应浏览器JSON.stringify结果。
    return {
        "needNewlineCombine": False,
        "disableCache": False,
        "isAi": False,
        "sseStartTime": now_ms,
        "query": query,
        "from": from_lang,
        "to": to_lang,
        "corpusIds": [],
        "needPhonetic": True,
        "domain": "common",
        "detectLang": "",
        "isIncognitoAI": False,
        "milliTimestamp": now_ms,
    }


def iter_sse_json(lines: Iterable[str]) -> Iterator[dict[str, object]]:
    """按照SSE事件块解析所有data行，兼容一条事件含多行data。"""
    data_lines: list[str] = []

    def decode() -> dict[str, object] | None:
        if not data_lines:
            return None
        raw = "\n".join(data_lines)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BaiduWebError(f"SSE data不是合法JSON：{raw[:200]!r}") from exc
        if not isinstance(value, dict):
            raise BaiduWebError("SSE data的JSON顶层不是对象")
        return value

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            value = decode()
            if value is not None:
                yield value
            data_lines.clear()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    value = decode()
    if value is not None:
        yield value


def collect_translation(messages: Iterable[dict[str, object]]) -> tuple[str, str, str]:
    """收集Translating事件中的dst，并返回译文和实际语言方向。"""
    parts: dict[str, str] = {}
    detected_from = ""
    actual_to = ""

    for message in messages:
        errno = int(message.get("errno") or 0)
        if errno:
            errmsg = str(message.get("errmsg") or "未知错误")
            if errno in {995, 1022}:
                raise BaiduRiskControlError(f"风控拒绝：errno={errno}, errmsg={errmsg}")
            raise BaiduWebError(f"接口错误：errno={errno}, errmsg={errmsg}")

        data = message.get("data") or {}
        if not isinstance(data, dict):
            continue
        event = data.get("event")

        if event == "StartTranslation":
            detected_from = str(data.get("from") or detected_from)
            actual_to = str(data.get("to") or actual_to)
        elif event == "Translating":
            items = data.get("list") or []
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                part_id = str(item.get("id") if item.get("id") is not None else index)
                parts[part_id] = str(item.get("dst") or "")

    return "".join(parts.values()), detected_from, actual_to


class BaiduWebTranslator:
    def __init__(
        self,
        timeout: tuple[int, int] = (10, 60),
        replay_context: HarReplayContext | None = None,
    ) -> None:
        self.timeout = timeout
        self.replay_context = replay_context
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": PAGE_URL,
            }
        )
        if replay_context:
            # HAR中的浏览器版本、Client Hints和Acs-Token保持一致。
            self.session.headers.update(replay_context.headers)
            for name, value in replay_context.cookies.items():
                self.session.cookies.set(name, value, domain="fanyi.baidu.com", path="/")

    def bootstrap(self) -> None:
        """访问正确页面，让Session接收BAIDUID等服务器Cookie。"""
        response = self.session.get(PAGE_URL, timeout=self.timeout)
        response.raise_for_status()
        if not response.content:
            raise BaiduWebError("页面正文为空，请检查路径是否为mtpe-individual")

    def translate(
        self,
        query: str,
        from_lang: str = "en",
        to_lang: str = "zh",
        *,
        acs_token: str | None = None,
    ) -> TranslationResult:
        payload = build_payload(query, from_lang, to_lang)
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Origin": "https://fanyi.baidu.com",
            "Referer": (
                f"{PAGE_URL}?query={quote(query.strip())}"
                f"&lang={quote(from_lang)}2{quote(to_lang)}"
            ),
        }
        if acs_token:
            # 仅支持用户自己合法抓包得到的短期值，不在Python中伪造ACS算法。
            headers["Acs-Token"] = acs_token

        with self.session.post(
            API_URL,
            headers=headers,
            # 浏览器使用JSON.stringify：UTF-8且没有多余空格。
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            stream=True,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" not in content_type:
                raise BaiduWebError(
                    f"响应不是SSE：Content-Type={content_type!r}; body={response.text[:200]!r}"
                )

            # 直接按UTF-8解码原始字节，避免Windows控制台/requests猜错编码。
            lines = (line.decode("utf-8") for line in response.iter_lines())
            target, detected_from, actual_to = collect_translation(iter_sse_json(lines))

        if not target:
            raise BaiduWebError("响应结束但未收到Translating译文事件")
        return TranslationResult(
            source=query.strip(),
            target=target,
            from_lang=detected_from or from_lang,
            to_lang=actual_to or to_lang,
        )

    def translate_many(
        self,
        queries: Iterable[str],
        from_lang: str = "en",
        to_lang: str = "zh",
        *,
        acs_token: str | None = None,
        delay: tuple[float, float] = (1.0, 1.8),
    ) -> Iterator[TranslationResult]:
        """顺序批量翻译；遇到风控立即抛错停止。"""
        for index, query in enumerate(queries):
            if index:
                time.sleep(random.uniform(*delay))
            yield self.translate(query, from_lang, to_lang, acs_token=acs_token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="百度翻译新版网页接口学习复现")
    parser.add_argument("texts", nargs="+", help="一条或多条待翻译文本")
    parser.add_argument("--from-lang", default="en")
    parser.add_argument("--to-lang", default="zh")
    parser.add_argument(
        "--har",
        type=Path,
        help="读取自己刚导出的成功HAR，自动使用其中的短期Acs-Token和浏览器Header",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印请求结构，不联网")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        for text in args.texts:
            request_view = {
                "method": "POST",
                "url": API_URL,
                "headers": {
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                    "Acs-Token": "<来自环境变量，若设置；不显示真实值>",
                },
                "json": build_payload(text, args.from_lang, args.to_lang),
            }
            print(json.dumps(request_view, ensure_ascii=False, indent=2))
        return

    replay_context = load_har_replay_context(args.har) if args.har else None
    translator = BaiduWebTranslator(replay_context=replay_context)
    translator.bootstrap()
    # --har优先；没有HAR时仍支持通过环境变量临时提供Token。
    acs_token = None if replay_context else os.environ.get("BAIDU_ACS_TOKEN")

    try:
        for result in translator.translate_many(
            args.texts,
            args.from_lang,
            args.to_lang,
            acs_token=acs_token,
        ):
            print(json.dumps(asdict(result), ensure_ascii=False))
    except BaiduRiskControlError as exc:
        raise SystemExit(f"已停止批量请求：{exc}") from exc


if __name__ == "__main__":
    main()
