"""扫描下载的JS，生成可复核的字符串位置、webpack模块号和上下文。

字符串扫描不是动态调试的替代品；它用于先缩小范围，再回到DevTools断点验证。
"""

from __future__ import annotations

import bisect
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "captured" / "original"
JSON_REPORT = ROOT / "captured" / "scan-report.json"
MARKDOWN_REPORT = ROOT / "ANALYSIS.generated.md"

PATTERNS = (
    "/ait/text/translate",
    "milliTimestamp",
    "useAcsToken",
    "Acs-Token",
    "getAcsInstance",
    "getSign",
    "paris_",
    "abclite-",
    "acs-",
    "svcp_stk",
    "TranslationSucceed",
    "Translating",
)
MODULE_RE = re.compile(r"(?P<id>\d+):function\(t,e,n\)")


def compact_context(text: str, position: int, width: int = 260) -> str:
    start = max(0, position - width)
    end = min(len(text), position + width)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def module_at(markers: list[tuple[int, str]], position: int) -> str | None:
    positions = [item[0] for item in markers]
    index = bisect.bisect_right(positions, position) - 1
    return markers[index][1] if index >= 0 else None


def scan_file(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    markers = [(match.start(), match.group("id")) for match in MODULE_RE.finditer(text)]
    pattern_results: dict[str, object] = {}

    for pattern in PATTERNS:
        positions: list[int] = []
        cursor = 0
        while True:
            position = text.find(pattern, cursor)
            if position == -1:
                break
            positions.append(position)
            cursor = position + len(pattern)

        if positions:
            pattern_results[pattern] = {
                "count": len(positions),
                "occurrences": [
                    {
                        "offset": position,
                        "webpackModule": module_at(markers, position),
                        "context": compact_context(text, position),
                    }
                    for position in positions[:8]
                ],
            }

    return {
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "characters": len(text),
        "webpackModuleCount": len(markers),
        "patterns": pattern_results,
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 百度翻译JS静态扫描报告",
        "",
        "> 由 `scripts/scan_bundles.py` 根据当前下载文件生成。位置是字符偏移，不是源码行号。",
        "",
    ]

    for file_result in report["files"]:  # type: ignore[index]
        lines.extend(
            [
                f"## `{file_result['file']}`",
                "",
                f"- 字符数：{file_result['characters']}",
                f"- 识别出的webpack模块：{file_result['webpackModuleCount']}",
                "",
            ]
        )
        for pattern, detail in file_result["patterns"].items():
            modules = sorted(
                {
                    item["webpackModule"]
                    for item in detail["occurrences"]
                    if item["webpackModule"] is not None
                }
            )
            lines.append(
                f"- `{pattern}`：{detail['count']}处；模块：{', '.join(modules) or '未识别'}"
            )
        lines.append("")

    lines.extend(
        [
            "## 已确认的业务调用链",
            "",
            "```text",
            "35353（翻译SSE）",
            "  → 83276（SSE请求封装）",
            "  → 88172（Paris/ACS外层封装）",
            "  → Acs-Token请求头",
            "",
            "71890（命中风险时调起验证码并写svcp_stk）",
            "```",
            "",
            "完整上下文位于 `captured/scan-report.json`。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    files = sorted(SOURCE_DIR.glob("*.js"))
    if not files:
        raise SystemExit("没有原始JS；请先运行 scripts/download_assets.py")

    report: dict[str, object] = {"patterns": PATTERNS, "files": []}
    report["files"] = [scan_file(path) for path in files]
    JSON_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    MARKDOWN_REPORT.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON报告：{JSON_REPORT}")
    print(f"Markdown摘要：{MARKDOWN_REPORT}")


if __name__ == "__main__":
    main()

