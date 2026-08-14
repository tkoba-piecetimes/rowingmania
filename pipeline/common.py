# -*- coding: utf-8 -*-
"""jara.or.jp（日本ローイング協会）取得スクリプトで共有するヘルパー。"""
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; RowingManiaBot/1.0; +https://github.com/tkoba-piecetimes/rowingmania)"


class NotFound(Exception):
    """404 Not Found（その年度・種目のページが存在しない）。"""


def fetch(url: str, retries: int = 3) -> str:
    """1リクエストごとに必ず1秒スリープしてから取得する（サーバー負荷配慮）。
    404は呼び出し側でスキップできるよう NotFound を送出する。"""
    time.sleep(1)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(url) from None
            if attempt == retries - 1:
                raise
            print(f"[warn] fetch failed ({e}), retrying in {10 * (attempt + 1)}s...", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                raise
            print(f"[warn] fetch failed ({e}), retrying in {10 * (attempt + 1)}s...", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
