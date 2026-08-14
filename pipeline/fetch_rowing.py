# -*- coding: utf-8 -*-
"""日本ローイング協会（jara.or.jp）から全日本大学ローイング選手権（インカレ）の
レース結果を取得し、data/results/<年度>.json に正規化保存する。

データ出典: 公益社団法人日本ローイング協会 (https://www.jara.or.jp/)
URL形式: https://www.jara.or.jp/race/<年度>/<年度>intercollege_<種目コード>.html
種目コードは年度によって増減する（例: 2000年は m2+ あり w4x+ なし、2025年は逆）ため、
既知の種目コード一覧を総当たりし、404は種目未開催としてスキップする。

同じ大会ページ配下に「全日本大学選手権」以外に「ジャパンオープンレガッタ」
（jom8+/jow8+）や「オックスフォード盾レガッタ」（ox/oxm8+）が併催されている年が
あるが、これらは大学インカレ本戦ではないため対象外（EVENT_CODESに含めない）。
また et（出漕一覧）/ tt（タイムテーブル）/ point（総合得点表）/ sc（参加人数）は
種目別のレース結果ページではないため対象外。

個人情報配慮のため、選手の氏名・身長・体重は取得しない（大学名・着順・タイムのみ）。
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from common import NotFound, fetch
from university_slugs import slug_for

BASE = "https://www.jara.or.jp/race"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "results"

# 全日本大学ローイング選手権の種目コード（男子7種目・女子6種目が基本形。
# 年度により増減するため過去に存在が確認できたコードもすべて含め、404はスキップする）。
EVENT_CODES = [
    "m1x", "m2x", "m2-", "m2+", "m4x", "m4-", "m4+", "m8+",
    "w1x", "w2x", "w2-", "w4+", "w4x", "w4x+", "w8+",
]

# ページ取得に失敗した場合のフォールバック表示名（通常はページ内 panel-heading から取得できる）
EVENT_NAMES_FALLBACK = {
    "m1x": "男子シングルスカル", "m2x": "男子ダブルスカル", "m2-": "男子ペア",
    "m2+": "男子舵手付きペア", "m4x": "男子クォドルプル", "m4-": "男子フォア",
    "m4+": "男子舵手つきフォア", "m8+": "男子エイト",
    "w1x": "女子シングルスカル", "w2x": "女子ダブルスカル", "w2-": "女子ペア",
    "w4+": "女子舵手つきフォア", "w4x": "女子クォドルプル", "w4x+": "女子舵手付きクォドルプル",
    "w8+": "女子エイト",
}

TITLE_RE = re.compile(r'<h1 class="title">([^<]+)</h1>')
EDITION_RE = re.compile(r"第(\d+)回")
PANEL_HEADING_RE = re.compile(r'<div class="panel-heading">([^<]+)の組合せと結果</div>')
RACE_HEADER_RE = re.compile(
    r'^(\d+)"></a>\s*'
    r'<div class="panel-heading">Race No: \d+</div>\s*'
    r'<div class="panel-body">\s*'
    r'<div class="row race-info">\s*'
    r'<div class="col-xs-6"><b>発艇時刻:</b>\s*(\d{2})/(\d{2})\s+(\d{2}:\d{2})</div>\s*'
    r'<div class="col-xs-6"><b>組別:</b>\s*<a[^>]*>([^<]*)</a></div>',
    re.DOTALL)
ROW_RE = re.compile(
    r'<tr>\s*'
    r'<td class="text-right">(\d*)</td>\s*'
    r'<td class="crew"[^>]*>(.*?)</td>\s*'
    r'<td class="text-center">([^<]*)</td>\s*'
    r'<td class="text-center">([^<]*)</td>\s*'
    r'<td class="text-center">([^<]*)</td>\s*'
    r'<td class="text-center">([^<]*)</td>\s*'
    r'<td class="text-right">(\d*)</td>\s*'
    r'<td class="qualify">([^<]*)</td>\s*'
    r'</tr>',
    re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
PAREN_RE = re.compile(r"\(([^()]+)\)\s*$")


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s).strip()


def parse_crew(raw: str) -> str | None:
    """クルーセルから大学名のみを抽出する。
    シングルスカルは「個人名<br/><small>(大学名)</small>」形式なので個人名は捨てる。
    複数人艇は最初から大学名のみが入っている。"""
    text = raw.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = strip_tags(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    m = PAREN_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


def classify_round(raw: str) -> str:
    """組別表記（年度により日本語/英語が混在）を正規化ラウンド区分に変換する。"""
    s = raw.strip()
    if re.match(r"^(準々決|Quarter\s*final)", s, re.I):
        return "quarterfinal"
    if re.match(r"^(準決|Semi[\s-]?Final)", s, re.I):
        return "semifinal"
    if re.match(r"^(敗復|Repechage)", s, re.I):
        return "repechage"
    if re.match(r"^(予選|Heat)", s, re.I):
        return "heat"
    if s == "決勝":
        return "final_a"
    if s == "順決":
        return "final_b"
    # Final A/B/C/D/E...（出漕数が多い種目では決勝が複数組に分かれる。Aが優勝決定戦）
    m = re.match(r"^Final\s*([A-Z])\b", s, re.I)
    if m:
        return f"final_{m.group(1).lower()}"
    return "other"


FINAL_ROUNDS = {"final_a", "final_b", "final_c", "final_d"}


def parse_event_page(html: str, year: int) -> tuple[str | None, list[dict]]:
    m = PANEL_HEADING_RE.search(html)
    event_name = m.group(1).strip() if m else None

    races = []
    for part in html.split('<a name="race')[1:]:
        hm = RACE_HEADER_RE.match(part)
        if not hm:
            continue
        race_no, mo, dd, tm, heat_raw = hm.groups()
        heat_raw = heat_raw.strip()
        rows = ROW_RE.findall(part)
        results = []
        for rank, crew_raw, s500, s1000, s1500, s2000, bno, qualify in rows:
            univ = parse_crew(crew_raw)
            if univ is None:
                continue
            results.append({
                "rank": int(rank) if rank else None,
                "university": univ,
                "splits": {
                    "500": s500.strip() or None, "1000": s1000.strip() or None,
                    "1500": s1500.strip() or None, "2000": s2000.strip() or None,
                },
                "time": s2000.strip() or None,
                "boat_no": int(bno) if bno else None,
                "qualify": qualify.strip(),
            })
        if not results:
            continue
        races.append({
            "race_no": int(race_no),
            "date": f"{year:04d}-{mo}-{dd}",
            "time": tm,
            "round_raw": heat_raw,
            "round": classify_round(heat_raw),
            "results": results,
        })
    races.sort(key=lambda r: r["race_no"])
    return event_name, races


def fetch_year(year: int) -> dict | None:
    events = {}
    tournament_name = None
    edition = None
    for code in EVENT_CODES:
        url = f"{BASE}/{year}/{year}intercollege_{code}.html"
        try:
            html = fetch(url)
        except NotFound:
            continue
        except Exception as e:
            print(f"  [warn] {year}/{code}: 取得失敗（{e}）", file=sys.stderr)
            continue
        if tournament_name is None:
            tm = TITLE_RE.search(html)
            if tm:
                tournament_name = tm.group(1).strip()
                em = EDITION_RE.search(tournament_name)
                edition = int(em.group(1)) if em else None
        event_name, races = parse_event_page(html, year)
        if not races:
            continue
        events[code] = {
            "code": code,
            "name": event_name or EVENT_NAMES_FALLBACK.get(code, code),
            "races": races,
        }
        print(f"  {year}/{code}: {event_name or code} レース{len(races)}件")
    if not events:
        return None
    return {
        "year": year,
        "edition": edition,
        "tournament_name": tournament_name or f"{year}年度 全日本大学ローイング選手権大会",
        "source": "日本ローイング協会 (JARA)",
        "source_url": f"{BASE}/{year}/{year}intercollege.html",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "events": events,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="jara.or.jp 全日本大学ローイング選手権データ取得")
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--end", type=int, default=date.today().year)
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して全年度再取得")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 当年度・前年度は結果が更新中の可能性があるため、キャッシュがあっても毎回再取得する。
    # それより過去の年度は確定済みとみなしキャッシュがあれば再取得しない。
    refresh_years = {date.today().year, date.today().year - 1}

    ok = 0
    skipped = 0
    empty = 0
    total_races = 0
    total_crews = set()
    for year in range(args.start, args.end + 1):
        out_path = DATA_DIR / f"{year}.json"
        if out_path.exists() and not args.force and year not in refresh_years:
            skipped += 1
            print(f"{year}: キャッシュ済みのためスキップ")
            continue
        print(f"=== {year}年度 ===")
        data = fetch_year(year)
        if data is None:
            empty += 1
            print(f"{year}: 大会データなし（未開催 or 未公開）")
            continue
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        races_n = sum(len(ev["races"]) for ev in data["events"].values())
        total_races += races_n
        for ev in data["events"].values():
            for r in ev["races"]:
                for res in r["results"]:
                    total_crews.add(res["university"])
        ok += 1
        print(f"{year}: 種目{len(data['events'])} レース{races_n}件 保存完了")

    print(f"\ndone: 取得{ok}年度 / スキップ{skipped}年度 / データなし{empty}年度 "
          f"/ 新規取得レース{total_races}件 / 新規取得中の大学延べ{len(total_crews)}校")


if __name__ == "__main__":
    main()
