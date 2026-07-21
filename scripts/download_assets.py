"""下载百度翻译当前页面及关键JavaScript，生成带哈希的资产清单。

本脚本只执行普通HTTP GET，不使用浏览器自动化。主包文件名从HTML动态发现，
避免把会随网站发布变化的hash文件名写死在分析流程里。
"""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


PAGE_URL = "https://fanyi.baidu.com/mtpe-individual/transText"
ACS_URLS = (
    "https://dlswbr.baidu.com/heicha/mw/abclite-2060-s.js",
    "https://dlswbr.baidu.com/heicha/mm/2060/acs-2060.js",
)
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "captured" / "original"
MANIFEST_PATH = ROOT / "captured" / "assets-manifest.json"


class ScriptSourceParser(HTMLParser):
    """从HTML的script标签中收集src。"""

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = dict(attrs)
        if values.get("src"):
            self.sources.append(values["src"] or "")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def safe_filename(url: str) -> str:
    """取URL中的文件名；无法取得时使用hash，避免路径穿越。"""
    name = Path(urlparse(url).path).name
    if not name:
        name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return name.replace("..", "_")


def fetch(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=(10, 60))
    response.raise_for_status()
    return response


def probe_source_map(session: requests.Session, script_url: str) -> dict[str, object]:
    """探测同名.js.map；只记录状态，不在失败时抛异常。"""
    map_url = script_url + ".map"
    try:
        response = session.get(map_url, timeout=(10, 30))
        return {
            "url": map_url,
            "status": response.status_code,
            "available": response.ok,
            "bytes": len(response.content),
        }
    except requests.RequestException as exc:
        return {"url": map_url, "available": False, "error": str(exc)}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    page_response = fetch(session, PAGE_URL)
    page_bytes = page_response.content
    (OUTPUT_DIR / "page.html").write_bytes(page_bytes)

    parser = ScriptSourceParser()
    parser.feed(page_response.text)
    discovered_urls = [urljoin(PAGE_URL, source) for source in parser.sources]

    # 页面主包全部保留；再补充主包中动态加载的两个ACS脚本。
    script_urls = list(dict.fromkeys(discovered_urls + list(ACS_URLS)))
    assets: list[dict[str, object]] = [
        {
            "kind": "page",
            "url": PAGE_URL,
            "file": "captured/original/page.html",
            "status": page_response.status_code,
            "bytes": len(page_bytes),
            "sha256": sha256_bytes(page_bytes),
        }
    ]

    for url in script_urls:
        response = fetch(session, url)
        content = response.content
        filename = safe_filename(url)
        target = OUTPUT_DIR / filename
        target.write_bytes(content)

        assets.append(
            {
                "kind": "javascript",
                "url": url,
                "file": f"captured/original/{filename}",
                "status": response.status_code,
                "contentType": response.headers.get("Content-Type"),
                "bytes": len(content),
                "sha256": sha256_bytes(content),
                "sourceMap": probe_source_map(session, url),
            }
        )
        print(f"下载 {filename}: {len(content):,} bytes")

    manifest = {
        "pageUrl": PAGE_URL,
        "note": "文件hash和内容会随百度发布变化；重新运行脚本即可刷新。",
        "assets": assets,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"资产清单：{MANIFEST_PATH}")


if __name__ == "__main__":
    main()

