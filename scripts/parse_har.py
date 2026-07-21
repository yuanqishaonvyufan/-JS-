"""从Chrome导出的HAR中提取百度翻译请求，并自动脱敏。

推荐导出 sanitized HAR。即使输入包含敏感Header，本脚本也会移除Cookie、
Authorization和完整Acs-Token，只保留字段存在性及长度。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TARGET = "/ait/text/translate"
SENSITIVE_HEADERS = {"cookie", "set-cookie", "authorization", "acs-token"}


def sanitize_headers(headers: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in headers:
        name = str(item.get("name", ""))
        value = str(item.get("value", ""))
        if name.lower() in SENSITIVE_HEADERS:
            result[name] = f"<redacted length={len(value)}>"
        else:
            result[name] = value
    return result


def decode_post_data(request: dict[str, Any]) -> Any:
    post_data = request.get("postData") or {}
    text = post_data.get("text")
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def extract(har: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request") or {}
        url = str(request.get("url", ""))
        if TARGET not in url:
            continue
        response = entry.get("response") or {}
        results.append(
            {
                "startedDateTime": entry.get("startedDateTime"),
                "request": {
                    "method": request.get("method"),
                    "url": url,
                    "headers": sanitize_headers(request.get("headers") or []),
                    "body": decode_post_data(request),
                },
                "response": {
                    "status": response.get("status"),
                    "headers": sanitize_headers(response.get("headers") or []),
                    "mimeType": (response.get("content") or {}).get("mimeType"),
                },
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="提取并脱敏百度翻译HAR请求")
    parser.add_argument("har", type=Path, help="Chrome导出的HAR文件")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("captured/har-extracted.sanitized.json"),
    )
    args = parser.parse_args()

    har = json.loads(args.har.read_text(encoding="utf-8-sig"))
    result = extract(har)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"提取到 {len(result)} 条目标请求：{args.output.resolve()}")


if __name__ == "__main__":
    main()

