# -*- coding: utf-8 -*-
"""大学別「インカレ全記録まとめ」記事（Type A: 大学の軌跡シリーズ）を自動生成する。

ローイングマニアはアーカイブ型サイトのため、大学別ページ（site/universities/<slug>/）
に載っている年度別戦績を、SEO記事として1大学1本にまとめ直したものを
content/articles/ に量産する。LLMは使わず、data/results/ のキャッシュ済み結果から
テンプレートで機械的に組み立てる（決定的・再現可能）。

対象: 通算出場レース数が10以上の大学のみ（データが薄い大学の低品質記事を防ぐ品質ゲート）。
既に記事がある大学（content/articles/univ-history-<slug>.md が存在）はスキップし、
通算レース数が多い大学から順に、1回の実行につき最大 MAX_PER_RUN 本のみ新規生成する
（cronで日次実行し、ストックを少しずつ消化していく想定）。

frontmatterはgenerate_site.load_articles()が読む平文形式（key: value）。
dateはビルド日時ではなく「最終出場年の12月31日」で固定し、Date.now()相当に
依存しない決定的な値にする（同じデータなら常に同じ記事が生成される）。

出力先: content/articles/univ-history-<大学slug>.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_site import EVENT_ORDER, is_final_round, load_years, round_label, round_priority
from university_slugs import slug_for

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "articles"

MIN_RACES = 10          # 品質ゲート: 通算出場レース数がこれ未満の大学は対象外
MAX_PER_RUN = 2          # 1回の実行での新規生成本数の上限
CATEGORY = "大学の軌跡"
SOURCE_URL = "https://www.jara.or.jp/race/"
SOURCE_NAME = "日本ローイング協会 (JARA)"


# ---------------------------------------------------------------- 集計

def build_university_stats(years):
    """大学別の通算成績を集計する。generate_site.build_indices()と同じ
    「(年度,種目)ごとの最高到達ラウンド」集計に加え、記事生成に必要な
    通算出場レース数・種目別出場回数・出場年度を持たせたもの。"""
    stats = {}

    for y in years:
        year = y["year"]
        for code, ev in y["events"].items():
            for race in ev["races"]:
                prio = round_priority(race["round"])
                for res in race["results"]:
                    name = res["university"]
                    u = stats.setdefault(name, {
                        "name": name,
                        "slug": slug_for(name),
                        "years": set(),
                        "total_races": 0,
                        "event_race_counts": {},
                        "event_names": {},
                        "records": {},
                    })
                    u["years"].add(year)
                    u["total_races"] += 1
                    u["event_race_counts"][code] = u["event_race_counts"].get(code, 0) + 1
                    u["event_names"][code] = ev["name"]

                    key = (year, code)
                    rec = u["records"].setdefault(key, {
                        "event_name": ev["name"], "stage_priority": -1,
                        "stage": None, "final_rank": None, "final_time": None,
                    })
                    if prio > rec["stage_priority"]:
                        rec["stage_priority"] = prio
                        rec["stage"] = race["round"]
                        if is_final_round(race["round"]):
                            rec["final_rank"] = res["rank"]
                            rec["final_time"] = res["time"]
                        else:
                            rec["final_rank"] = None
                            rec["final_time"] = None

    for u in stats.values():
        u["first_year"] = min(u["years"])
        u["last_year"] = max(u["years"])
        u["final_appearances"] = sum(
            1 for r in u["records"].values() if r["stage"] and is_final_round(r["stage"]))
        # 決勝A（優勝決定戦）で3位以内に入った実績（優勝・入賞）を新しい年度順に
        medals = [
            {"year": year, "code": code, **r}
            for (year, code), r in u["records"].items()
            if r["stage"] == "final_a" and r["final_rank"] in (1, 2, 3)
        ]
        medals.sort(key=lambda m: (-m["year"], m["final_rank"]))
        u["medals"] = medals
        u["championships"] = sum(1 for m in medals if m["final_rank"] == 1)

    return stats


def eligible_universities(stats):
    """出場レース数が品質ゲート以上の大学を、レース数の多い順（同数は大学名順）で返す。"""
    elig = [u for u in stats.values() if u["total_races"] >= MIN_RACES]
    elig.sort(key=lambda u: (-u["total_races"], u["name"]))
    return elig


# ---------------------------------------------------------------- 記事本文組み立て

def format_result(rank, time):
    if rank is None:
        return "—"
    return f"{rank}位（{time or '—'}）"


MAX_HIGHLIGHT_ITEMS = 8  # ハイライトに列挙する優勝・入賞の最大件数（全記録は年度別成績テーブルに掲載）


def medal_line(m):
    result = "優勝" if m["final_rank"] == 1 else f"{m['final_rank']}位入賞"
    return f"- {m['year']}年度 {m['event_name']}：決勝A {result}（タイム {m['final_time'] or '—'}）"


def build_highlight_section(u):
    medals = u["medals"]
    if medals:
        lines = [medal_line(m) for m in medals[:MAX_HIGHLIGHT_ITEMS]]
        if u["championships"]:
            lead = (
                f"{u['name']}は全日本大学ローイング選手権の決勝A（優勝決定戦）で"
                f"通算{u['championships']}回優勝しており、3位以内（優勝・入賞）の実績は"
                f"通算{len(medals)}回に上る。"
            )
        else:
            lead = (
                f"{u['name']}は優勝経験こそまだないが、決勝A（優勝決定戦）で"
                f"通算{len(medals)}回、3位以内に入賞している。"
            )
        more = ""
        if len(medals) > MAX_HIGHLIGHT_ITEMS:
            more = "\n\n（上記は直近の成績を抜粋。優勝・入賞の全記録は下記の年度別成績で確認できる）"
        return lead + "（直近の主な成績）\n\n" + "\n".join(lines) + more

    if u["final_appearances"]:
        # 決勝進出はあるが決勝Aで3位以内には未到達（決勝B以下、または決勝Aで4位以下）
        best = min(
            (r for r in u["records"].values() if r["stage"] and is_final_round(r["stage"])),
            key=lambda r: (r["final_rank"] is None, r["final_rank"] if r["final_rank"] is not None else 99),
        )
        stage_txt = round_label(best["stage"])
        rank_txt = format_result(best["final_rank"], best["final_time"])
        return (
            f"{u['name']}はこれまでに{u['final_appearances']}回、決勝の舞台に進出しているが、"
            f"優勝・入賞（決勝A3位以内）にはまだ届いていない。決勝での最高成績は"
            f"{stage_txt} {rank_txt}。"
        )

    return (
        f"{u['name']}はこれまで決勝進出の実績はなく、予選・敗者復活・準々決勝・準決勝が"
        "出場歴の中心となっている。"
    )


def build_year_table(u):
    keys = sorted(
        u["records"].keys(),
        key=lambda yc: (-yc[0], EVENT_ORDER.index(yc[1]) if yc[1] in EVENT_ORDER else 99),
    )
    rows = ["| 年度 | 種目 | 最高到達ラウンド | 着順/タイム |", "|---|---|---|---|"]
    for year, code in keys:
        rec = u["records"][(year, code)]
        stage_txt = round_label(rec["stage"]) if rec["stage"] else "—"
        result_txt = format_result(rec["final_rank"], rec["final_time"])
        rows.append(f"| {year} | {rec['event_name']} | {stage_txt} | {result_txt} |")
    return "\n".join(rows)


def build_event_tendency(u):
    codes = sorted(
        u["event_race_counts"].keys(),
        key=lambda c: (-u["event_race_counts"][c], EVENT_ORDER.index(c) if c in EVENT_ORDER else 99),
    )
    lines = [
        f"- {u['event_names'][c]}（{c}）: {u['event_race_counts'][c]}レース"
        for c in codes
    ]
    return "\n".join(lines)


def build_related_links(u, rel="../../"):
    lines = [f"- [{u['name']}の大学別戦績ページ]({rel}universities/{u['slug']}/index.html)"]
    years_for_links = sorted({u["first_year"], u["last_year"], *[m["year"] for m in u["medals"][:3]]}, reverse=True)
    for year in years_for_links:
        lines.append(f"- [{year}年度 全日本大学ローイング選手権 結果]({rel}years/{year}/index.html)")
    return "\n".join(lines)


def build_article_markdown(u):
    name = u["name"]
    first_year, last_year = u["first_year"], u["last_year"]
    total_races, finals = u["total_races"], u["final_appearances"]

    title = f"{name}ボート部のインカレ全記録｜出場史と最高成績"
    description = (
        f"{name}の全日本大学ローイング選手権（インカレ）出場記録まとめ。"
        f"{first_year}〜{last_year}年度・通算{total_races}レースに出漕し、決勝進出{finals}回。"
        "年度別の全成績と種目別の出場傾向を掲載。"
    )
    date_str = f"{last_year}-12-31"

    lead = (
        f"{name}は全日本大学ローイング選手権（インカレ）に{first_year}年度から{last_year}年度まで"
        f"出場し、収録期間中の通算出場レース数は{total_races}レース、決勝進出は{finals}回を数える。"
        "本ページでは年度別の全成績を一覧にまとめ、出場傾向を振り返る。"
    )

    body = f"""{lead}

## 最高成績ハイライト

{build_highlight_section(u)}

## 年度別成績

{build_year_table(u)}

## 種目別の出場傾向

{build_event_tendency(u)}

## 関連リンク

{build_related_links(u)}

## 出典

本記事のデータは{SOURCE_NAME}の公式サイトで公表されている結果（[大会情報]({SOURCE_URL})）をもとに
編集部が集計したものです。選手個人の氏名・身長・体重は掲載していません。
確定情報は日本ローイング協会公式サイトをご確認ください。
"""

    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"date: {date_str}\n"
        f"category: {CATEGORY}\n"
        f"description: {description}\n"
        "---\n"
    )
    return frontmatter + body


# ---------------------------------------------------------------- main

def main():
    years = load_years()
    if not years:
        raise SystemExit("大会データがありません（fetch_rowing.pyを先に実行）")

    stats = build_university_stats(years)
    elig = eligible_universities(stats)

    CONTENT.mkdir(parents=True, exist_ok=True)
    existing_slugs = {f.stem for f in CONTENT.glob("univ-history-*.md")}

    pending = [u for u in elig if f"univ-history-{u['slug']}" not in existing_slugs]
    to_generate = pending[:MAX_PER_RUN]

    for u in to_generate:
        out = CONTENT / f"univ-history-{u['slug']}.md"
        out.write_text(build_article_markdown(u), encoding="utf-8")

    print(f"対象大学（出場レース数{MIN_RACES}以上・ストック数）: {len(elig)}校")
    print(f"既存記事: {len(existing_slugs)}件 / 未生成の残り: {len(pending) - len(to_generate)}件")
    if to_generate:
        for u in to_generate:
            print(f"生成: {u['name']}（races={u['total_races']}, "
                  f"slug=univ-history-{u['slug']}）")
    else:
        print("今回の新規生成: 0件（対象なし、またはストック消化済み）")


if __name__ == "__main__":
    main()
