# -*- coding: utf-8 -*-
"""data/results/ の正規化JSONから静的サイト「ローイングマニア」（site/）を生成する。

データモデルはラグビーマニア（リーグ戦型）と異なり、大会アーカイブ型。
「全日本大学ローイング選手権」という単一の大会の年度別結果を主軸に、
種目別（歴代優勝校）・大学別（年度別戦績）に横断集計する。

URL構造:
  site/index.html                          ポータルトップ（最新年度ハイライト・年度一覧）
  site/years/index.html                    年度一覧
  site/years/<year>/index.html             年度別結果（決勝結果＋全レース結果）
  site/events/index.html                   種目一覧
  site/events/<code>/index.html            種目別歴代優勝校年表
  site/universities/index.html             大学一覧
  site/universities/<slug>/index.html      大学別年度別戦績
  site/articles/ ...                       読みもの（雛形のまま。現状は空でも動作する）
"""
import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from university_slugs import slug_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = DATA / "results"
SITE = ROOT / "site"
ASSETS = ROOT / "assets"
CONTENT = ROOT / "content" / "articles"

SITE_BASE = "https://rowingmania.jp/"
GA_MEASUREMENT_ID = "G-2VXCQKLYZ8"  # GA4「ローイングマニア」専用プロパティ（プロパティID 549897625）
GSC_VERIFICATION = "0X77J6-cDQak8VJkyt1PGegqMjZwEI2HWAYjkwl3OF0"  # Search Console所有権確認トークン（アカウント共通）
SITE_NAME = "ローイングマニア"

# ---- ツナカレ接続導線（部活メディア→ツナカレ接続設計 2026-08 D1〜D5準拠） --------------
# 全リンク共通のUTM規約: utm_source=<サイト>&utm_medium=referral&utm_campaign=<種別>
SPONSOR_CTA_URL = "https://tunakare.jp/?utm_source=rowingmania&utm_medium=referral&utm_campaign=sponsor"
SPONSOR_LP02_URL = "https://lp.tunakare.jp/02/?utm_source=rowingmania&utm_medium=referral&utm_campaign=sponsor"  # 企業向けLP
LISTING_LP_URL = "https://lp.tunakare.jp/s01/?utm_source=rowingmania&utm_medium=referral&utm_campaign=listing"  # 学生団体向けLP（協賛募集の無料掲載）
MEDIA_PR_CONTACT_URL = "https://media.tunakare.jp/contact/student/?utm_source=rowingmania&utm_medium=referral&utm_campaign=media-pr"
SHUKATSU_URL = "https://shukatsu.tunakare.jp/?utm_source=rowingmania&utm_medium=referral&utm_campaign=shukatsu"
CAREER_URL = "https://career.tunakare.jp/?utm_source=rowingmania&utm_medium=referral&utm_campaign=career"

# ---- お問い合わせ（中立リレーAPI経由・運営元秘匿。メディアSNS統合要件定義_2026-08 §3-1）
CONTACT_MEDIA_KEY = "rowing"
CONTACT_RELAY_URL = "https://mania-contact.vercel.app/api/contact"

# 種目コードの表示順（男子7種目→女子6種目。年度により一部種目が存在しないこともある）
EVENT_ORDER = [
    "m1x", "m2x", "m2-", "m2+", "m4x", "m4-", "m4+", "m8+",
    "w1x", "w2x", "w2-", "w4+", "w4x", "w4x+", "w8+",
]
ROUND_LABEL = {
    "heat": "予選", "repechage": "敗者復活", "quarterfinal": "準々決勝",
    "semifinal": "準決勝", "final_a": "決勝A（優勝決定）", "other": "その他",
}


def round_label(round_key: str) -> str:
    """final_b以降は「決勝B」のように動的にラベルを組み立てる（出漕数が多い種目では
    決勝が複数組=Final A〜E程度に分かれ、Aが優勝決定戦になる）。"""
    if round_key in ROUND_LABEL:
        return ROUND_LABEL[round_key]
    if round_key.startswith("final_"):
        return f"決勝{round_key[len('final_'):].upper()}"
    return round_key


def round_priority(round_key: str) -> int:
    base = {"other": 0, "heat": 1, "repechage": 2, "quarterfinal": 3, "semifinal": 4}
    if round_key in base:
        return base[round_key]
    if round_key.startswith("final_") and len(round_key) == 7:
        # final_a=最優先、final_b以降は文字が進むほど優先度を下げる（が準決勝より上位）
        letter = round_key[-1]
        return 100 - (ord(letter) - ord("a"))
    return -1


FINAL_ROUNDS_PREFIX = "final_"


def is_final_round(round_key: str) -> bool:
    return round_key.startswith(FINAL_ROUNDS_PREFIX)
RANK_MEDAL = {1: "gold", 2: "silver", 3: "bronze"}

_sitemap_paths: list[str] = []


# ---------------------------------------------------------------- data loading

def load_years():
    years = []
    for f in sorted(RESULTS.glob("*.json")):
        years.append(json.loads(f.read_text(encoding="utf-8")))
    years.sort(key=lambda y: y["year"], reverse=True)
    return years


def load_articles():
    if not CONTENT.exists():
        return []
    arts = []
    for f in sorted(CONTENT.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        _, fm, body = raw.split("---", 2)
        a = {"slug": f.stem, "body": body.strip()}
        for line in fm.strip().splitlines():
            k, _, v = line.partition(":")
            a[k.strip()] = v.strip()
        arts.append(a)
    arts.sort(key=lambda a: (a.get("date", ""), a["slug"]), reverse=True)
    return arts


def build_indices(years):
    """年度別JSONを種目別・大学別に横断集計する。"""
    events = {}         # code -> {"code","name","years": {year: [races]}}
    universities = {}   # 大学名 -> {"name","slug","records": {(year,code): {...}}}

    for y in years:
        year = y["year"]
        for code, ev in y["events"].items():
            e = events.setdefault(code, {"code": code, "name": ev["name"], "years": {}})
            e["years"][year] = ev["races"]
            for race in ev["races"]:
                prio = round_priority(race["round"])
                for res in race["results"]:
                    univ = res["university"]
                    u = universities.setdefault(
                        univ, {"name": univ, "slug": slug_for(univ), "records": {}})
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

    for u in universities.values():
        u["championships"] = sum(
            1 for r in u["records"].values() if r["stage"] == "final_a" and r["final_rank"] == 1)
        u["final_appearances"] = sum(
            1 for r in u["records"].values() if r["stage"] and is_final_round(r["stage"]))
        u["years_active"] = sorted({y for y, _c in u["records"].keys()}, reverse=True)

    for e in events.values():
        champs = {}
        for year, races in e["years"].items():
            fa = next((r for r in races if r["round"] == "final_a"), None)
            if not fa:
                continue
            ranked = sorted(
                (r for r in fa["results"] if r["rank"]), key=lambda r: r["rank"])
            champs[year] = ranked[:3]
        e["champions"] = champs

    return events, universities


# ---------------------------------------------------------------- text helpers

def date_jp(iso):
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return f"{d.month}月{d.day}日"


def event_label(code, name):
    return f"{escape(name)}（{escape(code)}）"


def rank_cell(rank):
    if rank is None:
        return '<td class="rank">—</td>'
    cls = RANK_MEDAL.get(rank, "")
    cls_attr = f' class="rank rk-{cls}"' if cls else ' class="rank"'
    return f'<td{cls_attr}>{rank}</td>'


def univ_link(name, universities, R=""):
    u = universities.get(name)
    if not u:
        return escape(name)
    return f'<a href="{R}universities/{u["slug"]}/index.html">{escape(name)}</a>'


def tunakare_cta(url, label, event, css_class="cta"):
    """ツナカレ系リンク共通の描画（D5: 全リンク rel=\"noopener sponsored\"＋「PR」表記）。"""
    return (f'<a class="{css_class}" href="{escape(url)}" target="_blank" rel="noopener sponsored" '
            f'onclick="window.gtag&&gtag(\'event\',\'{event}\')">'
            f'<span class="pr-badge">PR</span>{escape(label)}</a>')


def source_note(y):
    return (f'<a href="{escape(y["source_url"])}">{escape(y["source"])}</a>'
            f'（{escape(y["tournament_name"])}）')


# ---------------------------------------------------------------- page shell

NAV_ITEMS = [
    ("index.html", "トップ"),
    ("years/index.html", "年度一覧"),
    ("events/index.html", "種目一覧"),
    ("universities/index.html", "大学一覧"),
    ("contact/index.html", "お問い合わせ"),
]


def page(rel, title, body, meta, *, path="", desc="", extra_head="", og_type="website",
         subnav="", sitemap=True):
    if sitemap:
        _sitemap_paths.append(path)
    else:
        extra_head = '<meta name="robots" content="noindex, nofollow">\n' + extra_head
    desc = desc or "全日本大学ローイング選手権（インカレ）の年度別結果・種目別歴代優勝校・大学別戦績を掲載する記録データベース。"
    url = SITE_BASE + path
    og_image = ""
    if (ASSETS / "ogp.png").exists():
        og_image = (f'<meta property="og:image" content="{SITE_BASE}assets/ogp.png">\n'
                    '<meta name="twitter:card" content="summary_large_image">\n')
    ga = ""
    if GA_MEASUREMENT_ID:
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>'
              '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
              f"gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>")
    gsc = f'<meta name="google-site-verification" content="{GSC_VERIFICATION}">\n' if GSC_VERIFICATION else ""
    nav = "".join(f'<a href="{rel}{href}">{label}</a>' for href, label in NAV_ITEMS)
    src_html = f'<a href="{escape(meta["source_url"])}">{escape(meta["source"])}</a>'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{gsc}<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:site_name" content="{SITE_NAME}">
{og_image}<link rel="icon" href="{rel}assets/favicon.svg" type="image/svg+xml">
<link rel="canonical" href="{escape(url)}">
{extra_head}{ga}
<link rel="stylesheet" href="{rel}style.css">
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="{rel}index.html"><span class="brand-tick"></span>{SITE_NAME}<span class="brand-sub">JAPAN COLLEGE ROWING</span></a>
    <nav class="global-nav">{nav}</nav>
  </div>
</header>
{subnav}
<main>
{body}
</main>
<footer class="site-footer">
  <div class="footer-inner">
    <p class="footer-brand">{SITE_NAME}</p>
    <nav class="footer-nav">{nav}</nav>
    <p>大会データ出典: {src_html}
    （情報更新日: {escape(meta['fetched_at'][:10])}）</p>
    <p>{SITE_NAME}は全日本大学ローイング選手権（インカレ）の記録アーカイブサイトです。掲載の着順・タイムは出典元の公表データを編集部で整形したものです。個人の氏名・身長・体重等は掲載していません。確定情報は日本ローイング協会公式サイトをご確認ください。</p>
  </div>
</footer>
</body>
</html>"""


def write_page(path, html):
    out = SITE / path / "index.html" if path else SITE / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- markdown (記事機能・雛形のまま)

def md_inline(s):
    s = escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def md_to_html(md):
    out, para = [], []
    in_ul = in_ol = in_table = False

    def close_blocks():
        nonlocal in_ul, in_ol, in_table
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False
        if in_table:
            out.append("</tbody></table></div>")
            in_table = False

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para = []

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            flush_para()
            if in_ul or in_ol:
                close_blocks()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]+", c) for c in cells):
                continue
            if not in_table:
                out.append('<div class="tbl"><table><thead><tr>'
                           + "".join(f"<th>{md_inline(c)}</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</tbody></table></div>")
            in_table = False
        if not s:
            flush_para()
            close_blocks()
        elif s.startswith("### "):
            flush_para(); close_blocks()
            out.append(f"<h3>{md_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            flush_para(); close_blocks()
            out.append(f"<h2>{md_inline(s[3:])}</h2>")
        elif s.startswith("- "):
            flush_para()
            if not in_ul:
                close_blocks()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline(s[2:])}</li>")
        elif re.match(r"^\d+\.\s", s):
            flush_para()
            if not in_ol:
                close_blocks()
                out.append("<ol>")
                in_ol = True
            item = re.sub(r"^\d+\.\s", "", s)
            out.append(f"<li>{md_inline(item)}</li>")
        else:
            para.append(s)
    flush_para()
    close_blocks()
    return "\n".join(out)


def article_card(a, rel):
    return (f'<div class="digest-card"><p class="cat-line"><span class="cat">{escape(a["category"])}</span>'
            f' <span class="note">{escape(a["date"])}</span></p>'
            f'<h3><a href="{rel}articles/{a["slug"]}/index.html">{escape(a["title"])}</a></h3>'
            f'<p class="note">{escape(a["description"])}</p></div>')


# D3: 記事frontmatterの `cta:` で帯を出し分け（shukatsu/career/listing/sponsor/none・未指定はnone）
CTA_DEFS = {
    "shukatsu": {
        "heading": "部活と就活の両立、ひとりで悩まない",
        "label": "無料で就活相談する →",
        "url": SHUKATSU_URL,
        "event": "cv_shukatsu_click",
    },
    "career": {
        "heading": "体育会出身の転職・キャリア相談",
        "label": "キャリア相談をしてみる →",
        "url": CAREER_URL,
        "event": "cv_career_click",
    },
    "listing": {
        "heading": "遠征費・運営資金に。協賛募集を無料掲載",
        "label": "協賛募集の掲載について見る →",
        "url": LISTING_LP_URL,
        "event": "cv_listing_click",
    },
}


def build_article_cta_band(a):
    """D3: 記事CTA帯。sponsorは全記事共通で協賛検索トップへの汎用導線を表示する

    （個別大学への協賛ページ直リンク・団体名表示は行わない。募集中の部活はツナカレに
    遷移して初めてわかる設計。案件には締切・停止があり静的サイト側に募集状況を持つと
    管理不能になるため）。
    """
    cta = (a.get("cta") or "none").strip()
    if cta == "sponsor":
        return ('<section class="article-cta"><h2>この部活・競技を応援したい方へ</h2>'
                f'<p>{tunakare_cta(SPONSOR_CTA_URL, "ツナカレで協賛募集中の部活を探す →", "cv_sponsor_click")}</p>'
                f'<p class="note">{tunakare_cta(SPONSOR_LP02_URL, "法人・企業の方はこちら（協賛のご相談） →", "cv_sponsor_click", "cta-text")}</p>'
                '</section>')
    if cta in CTA_DEFS:
        d = CTA_DEFS[cta]
        return (f'<section class="article-cta"><h2>{escape(d["heading"])}</h2>'
                f'<p>{tunakare_cta(d["url"], d["label"], d["event"])}</p></section>')
    return ""


def build_articles(articles, meta):
    if not articles:
        return
    rel = "../"
    cards = "".join(article_card(a, rel) for a in articles)
    body = ('<h1>読みもの</h1>'
            '<p class="lead">大学ローイングの競技解説・大会観戦ガイド・データの読み方などをまとめています。</p>'
            f'<div class="digest">{cards}</div>')
    write_page("articles",
               page(rel, f"読みもの | {SITE_NAME}", body, meta,
                    path="articles/",
                    desc="全日本大学ローイング選手権の観戦ガイド・種目解説・データの読み方などの記事。"))
    rel = "../../"
    for a in articles:
        others = [x for x in articles if x["slug"] != a["slug"]][:3]
        related = "".join(
            f'<li><a href="../{x["slug"]}/index.html">{escape(x["title"])}</a></li>'
            for x in others)
        body = (f'<p class="breadcrumb"><a href="{rel}index.html">トップ</a> › '
                f'<a href="{rel}articles/index.html">読みもの</a> › {escape(a["category"])}</p>')
        body += (f'<p class="cat-line"><span class="cat">{escape(a["category"])}</span>'
                 f' <span class="note">{escape(a["date"])}</span></p>')
        body += f'<h1>{escape(a["title"])}</h1>'
        body += f'<div class="article">{md_to_html(a["body"])}</div>'
        body += build_article_cta_band(a)
        body += f'<section><h2>あわせて読む</h2><ul>{related}</ul></section>'
        write_page(f"articles/{a['slug']}",
                   page(rel, f'{a["title"]} | {SITE_NAME}', body, meta,
                        path=f'articles/{a["slug"]}/', desc=a["description"], og_type="article"))


# ---------------------------------------------------------------- contact

CONTACT_FORM_HTML = """<noscript><p class="form-message">このフォームのご利用にはJavaScriptの有効化が必要です。</p></noscript>
<form id="contact-form" class="contact-form">
  <div class="form-row">
    <label for="cf-name">お名前<span class="req">必須</span></label>
    <input type="text" id="cf-name" name="name" required autocomplete="name">
  </div>
  <div class="form-row">
    <label for="cf-affiliation">ご所属</label>
    <input type="text" id="cf-affiliation" name="affiliation" autocomplete="organization">
  </div>
  <div class="form-row">
    <label for="cf-email">メールアドレス<span class="req">必須</span></label>
    <input type="email" id="cf-email" name="email" required autocomplete="email">
  </div>
  <div class="form-row">
    <label for="cf-type">種別<span class="req">必須</span></label>
    <select id="cf-type" name="type" required>
      <option value="">選択してください</option>
      <option value="取材・情報提供">取材・情報提供</option>
      <option value="掲載・広告のご相談">掲載・広告のご相談</option>
      <option value="その他">その他</option>
    </select>
  </div>
  <div class="form-row">
    <label for="cf-body">内容<span class="req">必須</span></label>
    <textarea id="cf-body" name="body" rows="7" required></textarea>
  </div>
  <div class="hp-field" aria-hidden="true">
    <label for="cf-website">ウェブサイト</label>
    <input type="text" id="cf-website" name="website" tabindex="-1" autocomplete="off">
  </div>
  <button type="submit" id="cf-submit" class="cta">送信する</button>
</form>
<p id="cf-message" class="form-message" role="status" aria-live="polite"></p>"""

CONTACT_FORM_JS = """<script>
(function () {
  var form = document.getElementById('contact-form');
  if (!form) return;
  var msg = document.getElementById('cf-message');
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var payload = {
      mediaKey: '__MEDIA_KEY__',
      name: form.name.value,
      affiliation: form.affiliation.value,
      email: form.email.value,
      type: form.type.value,
      body: form.body.value,
      website: form.website.value
    };
    var elements = form.elements;
    var i;
    for (i = 0; i < elements.length; i++) { elements[i].disabled = true; }
    msg.textContent = '';
    msg.className = 'form-message';
    fetch('__RELAY_URL__', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (res) {
      return res.json().catch(function () { return { ok: false }; });
    }).then(function (data) {
      if (data && data.ok) {
        form.style.display = 'none';
        msg.textContent = '送信しました。3営業日以内にご返信します。';
        msg.className = 'form-message form-message-ok';
      } else {
        throw new Error('failed');
      }
    }).catch(function () {
      msg.textContent = '送信に失敗しました。時間をおいてお試しください。';
      msg.className = 'form-message form-message-error';
      for (i = 0; i < elements.length; i++) { elements[i].disabled = false; }
    });
  });
})();
</script>"""


def build_contact(meta):
    rel = "../"
    body = ('<h1>お問い合わせ</h1>'
            '<p class="lead">取材・情報提供、掲載・広告のご相談を受け付けています。'
            '3営業日以内にメールでご返信します。</p>')
    body += CONTACT_FORM_HTML
    body += CONTACT_FORM_JS.replace("__MEDIA_KEY__", CONTACT_MEDIA_KEY).replace("__RELAY_URL__", CONTACT_RELAY_URL)
    write_page("contact",
               page(rel, f"お問い合わせ | {SITE_NAME}", body, meta,
                    path="contact/",
                    desc=f"{SITE_NAME}への取材・情報提供、掲載・広告のご相談はこちらから。"))


# ---------------------------------------------------------------- portal

def build_support_section():
    """D4: トップページ支援セクション（応援する／無料で掲載／取材募集の3カード。G1解消）。"""
    cards = (
        '<div class="digest-card"><h3>応援する</h3>'
        '<p class="note">気になる大学の部活をチェックして、協賛募集の内容を見てみる。</p>'
        f'<p>{tunakare_cta(SPONSOR_CTA_URL, "応援できる部活を探す →", "cv_sponsor_click")}</p></div>'
        '<div class="digest-card"><h3>無料で掲載</h3>'
        '<p class="note">部活の運営者の方へ。遠征費・運営資金のための協賛募集を無料で掲載できます。</p>'
        f'<p>{tunakare_cta(LISTING_LP_URL, "協賛募集を掲載する →", "cv_listing_click")}</p></div>'
        '<div class="digest-card"><h3>取材募集</h3>'
        '<p class="note">取材してほしい部活・大会がある方はこちらから。</p>'
        f'<p>{tunakare_cta(MEDIA_PR_CONTACT_URL, "取材を依頼する →", "cv_media_pr_click")}</p></div>'
    )
    return (f'<section class="support-section"><h2>{SITE_NAME}を通じて部活を応援する</h2>'
            f'<div class="digest">{cards}</div></section>')


def build_portal(years, events, universities, articles, meta):
    rel = ""
    latest = years[0]
    total_races = sum(len(r) for e in events.values() for r in e["years"].values())
    body = ('<div class="hero">'
            '<img class="hero-img" src="assets/hero.jpg" alt="" width="1440" height="810">'
            '<div class="hero-text">'
            '<p class="hero-kicker">全日本大学ローイング選手権 全記録データベース</p>'
            '<h1>大学ボート・インカレの結果を2000年度から全レース収録</h1>'
            f'<p class="hero-sub">全{len(years)}年度・{len(EVENT_ORDER)}種目・{total_races}レースの着順・タイムを収録　'
            f'|　最終更新 {escape(meta["fetched_at"][:10])}</p>'
            '</div></div>')

    body += (f'<section><h2>{latest["year"]}年度（{escape(latest["tournament_name"])}）優勝校一覧</h2>'
             f'<p class="lead">最新開催年度の種目別優勝校。詳しい全レース結果は'
             f'<a href="years/{latest["year"]}/index.html">{latest["year"]}年度ページ</a>へ。</p>')
    cards = ""
    for code in EVENT_ORDER:
        ev = events.get(code)
        if not ev or latest["year"] not in ev.get("champions", {}):
            continue
        top3 = ev["champions"][latest["year"]]
        if not top3:
            continue
        champ = top3[0]
        cards += (f'<div class="digest-card"><p class="cat-line"><span class="cat">{escape(ev["name"])}</span></p>'
                  f'<h3>{univ_link(champ["university"], universities, rel)}</h3>'
                  f'<p class="note">優勝タイム {escape(champ["time"] or "—")}</p></div>')
    body += f'<div class="digest">{cards}</div></section>'

    body += '<section><h2>年度一覧</h2><div class="digest">'
    for y in years[:12]:
        played = sum(len(r) for e in events.values() for yr, r in e["years"].items() if yr == y["year"])
        body += (f'<div class="digest-card"><h3><a href="years/{y["year"]}/index.html">'
                 f'{y["year"]}年度</a></h3>'
                 f'<p class="cat-line"><span class="cat">{escape(y["tournament_name"])}</span></p>'
                 f'<p class="note">レース{played}件</p></div>')
    body += '</div><p class="more"><a class="cta" href="years/index.html">全年度一覧へ →</a></p></section>'

    body += '<section><h2>種目一覧</h2><div class="digest">'
    for code in EVENT_ORDER:
        ev = events.get(code)
        if not ev:
            continue
        n_years = len(ev["years"])
        body += (f'<div class="digest-card"><h3><a href="events/{escape(code)}/index.html">'
                 f'{escape(ev["name"])}</a></h3>'
                 f'<p class="note">収録{n_years}年度</p></div>')
    body += '</div><p class="more"><a class="cta" href="events/index.html">全種目一覧へ →</a></p></section>'

    body += build_support_section()

    if articles:
        body += ('<section><h2>読みもの</h2><div class="digest">'
                 + "".join(article_card(a, rel) for a in articles[:3])
                 + '</div><p class="more"><a class="cta" href="articles/index.html">読みもの一覧へ →</a></p></section>')

    write_page("", page(rel, f"{SITE_NAME} | 全日本大学ローイング選手権 全記録データベース", body, meta,
                        path="",
                        desc=f"全日本大学ローイング選手権（インカレ）の{years[-1]['year']}〜{years[0]['year']}年度・"
                             f"全{total_races}レースの着順・タイムを収録する記録データベース。"))


# ---------------------------------------------------------------- 年度ページ

def build_years_index(years, meta):
    rel = "../"
    rows = "".join(
        f'<tr><td><a href="{y["year"]}/index.html">{y["year"]}年度</a></td>'
        f'<td>{escape(y["tournament_name"])}</td>'
        f'<td>{len(y["events"])}</td>'
        f'<td>{sum(len(ev["races"]) for ev in y["events"].values())}</td></tr>'
        for y in years)
    body = ('<h1>年度一覧</h1>'
            f'<p class="lead">全日本大学ローイング選手権の年度別結果一覧（{years[-1]["year"]}〜{years[0]["year"]}年度・全{len(years)}年度）。</p>'
            '<div class="tbl"><table><thead><tr><th>年度</th><th>大会名</th><th>種目数</th><th>レース数</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')
    write_page("years", page(rel, f"年度一覧 | {SITE_NAME}", body, meta,
                             path="years/", desc="全日本大学ローイング選手権の年度別結果一覧。"))


def build_year_page(y, prev_y, next_y, universities, meta):
    rel = "../../"
    year = y["year"]
    total_races = sum(len(ev["races"]) for ev in y["events"].values())
    total_crews = len({res["university"] for ev in y["events"].values()
                       for race in ev["races"] for res in race["results"]})

    nav_links = ""
    if prev_y:
        nav_links += f'<a href="../{prev_y}/index.html">← {prev_y}年度</a>'
    if next_y:
        nav_links += f'<a href="../{next_y}/index.html">{next_y}年度 →</a>'
    subnav = (f'<div class="league-nav"><div class="league-nav-inner">'
              f'<span class="league-name">{year}年度</span>{nav_links}</div></div>') if nav_links else ""

    body = f'<h1>{escape(y["tournament_name"])}（{year}年度）</h1>'
    body += (f'<p class="lead">種目{len(y["events"])}・全レース{total_races}件・出場大学のべ{total_crews}校。'
             f'出典: {source_note(y)}</p>')

    body += '<section><h2>種目別 決勝結果</h2>'
    rows = ""
    for code in EVENT_ORDER:
        ev = y["events"].get(code)
        if not ev:
            continue
        fa = next((r for r in ev["races"] if r["round"] == "final_a"), None)
        if not fa:
            continue
        ranked = sorted((r for r in fa["results"] if r["rank"]), key=lambda r: r["rank"])
        cells = "".join(
            f'<td>{r["rank"]}位 {univ_link(r["university"], universities, rel)}'
            f'<span class="note">（{escape(r["time"] or "—")}）</span></td>'
            for r in ranked[:3])
        rows += (f'<tr><td><a href="{rel}events/{escape(code)}/index.html">{escape(ev["name"])}</a></td>'
                 f'{cells}</tr>')
    body += ('<div class="tbl"><table><thead><tr><th>種目</th><th>優勝</th><th>2位</th><th>3位</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></section>')

    body += '<section><h2>種目別 全レース結果（予選〜決勝）</h2>'
    for code in EVENT_ORDER:
        ev = y["events"].get(code)
        if not ev:
            continue
        body += f'<h3>{escape(ev["name"])}</h3>'
        race_rows = ""
        for race in ev["races"]:
            rlabel = round_label(race["round"])
            for r in sorted(race["results"], key=lambda r: (r["rank"] is None, r["rank"])):
                race_rows += (
                    f'<tr><td>{escape(rlabel)}<span class="note">（{escape(race["round_raw"])}）</span></td>'
                    f'<td>{date_jp(race["date"])}</td>'
                    f'{rank_cell(r["rank"])}'
                    f'<td>{univ_link(r["university"], universities, rel)}</td>'
                    f'<td>{escape(r["splits"]["500"] or "—")}</td>'
                    f'<td>{escape(r["splits"]["1000"] or "—")}</td>'
                    f'<td>{escape(r["splits"]["1500"] or "—")}</td>'
                    f'<td class="score">{escape(r["time"] or "—")}</td>'
                    f'<td class="note">{escape(r["qualify"])}</td></tr>')
        body += ('<div class="tbl"><table><thead><tr><th>組</th><th>日付</th><th>着順</th><th>大学</th>'
                 '<th>500m</th><th>1000m</th><th>1500m</th><th>2000m(タイム)</th><th>備考</th></tr></thead>'
                 f'<tbody>{race_rows}</tbody></table></div>')
    body += '</section>'

    write_page(f"years/{year}",
               page(rel, f'{year}年度 全日本大学ローイング選手権 結果 | {SITE_NAME}', body, meta,
                    path=f"years/{year}/",
                    desc=f'{year}年度（{y["tournament_name"]}）の種目別決勝結果・全レース結果（予選〜決勝）。',
                    subnav=subnav))


# ---------------------------------------------------------------- 種目ページ

def build_events_index(events, meta):
    rel = "../"
    rows = ""
    for code in EVENT_ORDER:
        ev = events.get(code)
        if not ev:
            continue
        n_years = len(ev["years"])
        rows += (f'<tr><td><a href="{escape(code)}/index.html">{escape(ev["name"])}</a></td>'
                 f'<td>{escape(code)}</td><td>{n_years}</td></tr>')
    body = ('<h1>種目一覧</h1>'
            '<p class="lead">全日本大学ローイング選手権で実施される種目。各種目ページで歴代優勝校を確認できます。</p>'
            '<div class="tbl"><table><thead><tr><th>種目</th><th>種目コード</th><th>収録年度数</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')
    write_page("events", page(rel, f"種目一覧 | {SITE_NAME}", body, meta,
                              path="events/", desc="全日本大学ローイング選手権の実施種目一覧。"))


def build_event_page(code, ev, universities, meta):
    rel = "../../"
    years_sorted = sorted(ev["years"].keys(), reverse=True)
    body = f'<h1>{escape(ev["name"])}</h1>'
    body += (f'<p class="lead">全日本大学ローイング選手権「{escape(ev["name"])}」（種目コード: {escape(code)}）'
             f'の歴代優勝校（{years_sorted[-1]}〜{years_sorted[0]}年度・収録{len(years_sorted)}年度）。</p>')

    rows = ""
    for year in years_sorted:
        top3 = ev["champions"].get(year, [])
        if not top3:
            rows += f'<tr><td><a href="{rel}years/{year}/index.html">{year}年度</a></td><td colspan="3" class="note">決勝データなし</td></tr>'
            continue
        cells = ""
        for i in range(3):
            if i < len(top3):
                r = top3[i]
                cells += (f'<td>{univ_link(r["university"], universities, rel)}'
                          f'<span class="note">（{escape(r["time"] or "—")}）</span></td>')
            else:
                cells += '<td class="note">—</td>'
        rows += f'<tr><td><a href="{rel}years/{year}/index.html">{year}年度</a></td>{cells}</tr>'
    body += ('<section><h2>年度別 決勝結果</h2>'
             '<div class="tbl"><table><thead><tr><th>年度</th><th>優勝</th><th>2位</th><th>3位</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></section>')

    win_count: dict[str, int] = {}
    for top3 in ev["champions"].values():
        if top3 and top3[0]["rank"] == 1:
            win_count[top3[0]["university"]] = win_count.get(top3[0]["university"], 0) + 1
    ranked = sorted(win_count.items(), key=lambda kv: kv[1], reverse=True)[:15]
    if ranked:
        rows = "".join(
            f'<tr><td class="rank">{i}</td><td>{univ_link(name, universities, rel)}</td>'
            f'<td><strong>{n}</strong></td></tr>'
            for i, (name, n) in enumerate(ranked, 1))
        body += ('<section><h2>通算優勝回数ランキング</h2>'
                 '<div class="tbl"><table><thead><tr><th>#</th><th>大学</th><th>優勝回数</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div></section>')

    write_page(f"events/{code}",
               page(rel, f'{ev["name"]} 歴代優勝校 | {SITE_NAME}', body, meta,
                    path=f"events/{code}/",
                    desc=f'{ev["name"]}の歴代優勝校一覧（{years_sorted[-1]}〜{years_sorted[0]}年度）と通算優勝回数ランキング。'))


# ---------------------------------------------------------------- 大学ページ

def build_universities_index(universities, meta):
    rel = "../"
    ranked = sorted(universities.values(),
                    key=lambda u: (-u["championships"], -u["final_appearances"], u["name"]))
    rows = "".join(
        f'<tr><td><a href="{u["slug"]}/index.html">{escape(u["name"])}</a></td>'
        f'<td>{u["championships"]}</td><td>{u["final_appearances"]}</td>'
        f'<td>{len(u["years_active"])}</td></tr>'
        for u in ranked)
    body = ('<h1>大学一覧</h1>'
            f'<p class="lead">全日本大学ローイング選手権に出場した大学（延べ{len(universities)}校）。優勝回数の多い順に表示。</p>'
            '<div class="tbl"><table><thead><tr><th>大学</th><th>優勝回数</th><th>決勝進出回数</th>'
            '<th>出場年度数</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')
    write_page("universities", page(rel, f"大学一覧 | {SITE_NAME}", body, meta,
                                    path="universities/",
                                    desc="全日本大学ローイング選手権に出場した大学の一覧。優勝回数・決勝進出回数付き。"))


def build_support_block():
    """D2改訂版: チームページ（＝アーカイブ型のためこのリポジトリでは大学ページ）の応援ブロック。
    全大学共通の汎用3導線を表示する。

    個別大学への協賛ページ直リンク・団体名表示は行わない（募集中の部活はツナカレに
    遷移して初めてわかる設計。案件には締切・停止があり静的サイト側に募集状況を持つと
    管理不能になるため）。
    """
    lanes = [
        tunakare_cta(SPONSOR_CTA_URL, "この部活・競技を応援したい方へ：ツナカレで協賛募集中の部活を探す →", "cv_sponsor_click"),
        tunakare_cta(
            LISTING_LP_URL, "この部の関係者の方へ：協賛募集を無料で掲載 →",
            "cv_listing_click", "cta cta-sub"),
        tunakare_cta(
            MEDIA_PR_CONTACT_URL, "取材してほしい部活を募集中 →", "cv_media_pr_click", "cta cta-sub"),
    ]
    lanes_html = "".join(f"<p>{lane}</p>" for lane in lanes)
    return f'<section class="sponsor"><h2>この部を応援する</h2>{lanes_html}</section>'


def build_university_page(u, meta):
    rel = "../../"
    name = u["name"]
    body = (f'<p class="breadcrumb"><a href="{rel}index.html">トップ</a> › '
            f'<a href="{rel}universities/index.html">大学一覧</a> › {escape(name)}</p>')
    body += f'<h1>{escape(name)}</h1>'
    body += ('<section><h2>通算成績</h2><div class="stat-row">'
             f'<div class="stat"><span class="num">{u["championships"]}</span>優勝回数</div>'
             f'<div class="stat"><span class="num">{u["final_appearances"]}</span>決勝進出回数</div>'
             f'<div class="stat"><span class="num">{len(u["years_active"])}</span>出場年度数</div>'
             '</div></section>')

    rows = ""
    for year, code in sorted(u["records"].keys(), key=lambda yc: (-yc[0], EVENT_ORDER.index(yc[1]) if yc[1] in EVENT_ORDER else 99)):
        rec = u["records"][(year, code)]
        stage_label = round_label(rec["stage"]) if rec["stage"] else "—"
        result_txt = f'{rec["final_rank"]}位（{rec["final_time"] or "—"}）' if rec["final_rank"] else "—"
        rows += (f'<tr><td><a href="{rel}years/{year}/index.html">{year}年度</a></td>'
                 f'<td><a href="{rel}events/{escape(code)}/index.html">{escape(rec["event_name"])}</a></td>'
                 f'<td>{escape(stage_label)}</td><td>{escape(result_txt)}</td></tr>')
    body += ('<section><h2>年度別出場種目・成績</h2>'
             '<div class="tbl"><table><thead><tr><th>年度</th><th>種目</th><th>最高到達ラウンド</th>'
             '<th>決勝結果</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>'
             '<p class="note">※「決勝結果」は決勝（A〜D）に進出した場合の着順・タイムです。決勝未進出の種目は到達ラウンドのみ表示しています。</p></section>')

    body += build_support_block()

    write_page(f"universities/{u['slug']}",
               page(rel, f'{name} 全日本大学ローイング選手権 出場記録 | {SITE_NAME}', body, meta,
                    path=f"universities/{u['slug']}/",
                    desc=f'{name}の全日本大学ローイング選手権 年度別出場種目・決勝進出回数・優勝回数。'))


# ---------------------------------------------------------------- 運営ダッシュボード

DASHBOARD_PATH = "dash-rwm-ops"  # 非公開運用ダッシュボード（noindex・sitemap非掲載）


def build_dashboard(years, events, universities, meta):
    rel = "../"
    total_races = sum(len(ev["races"]) for y in years for ev in y["events"].values())

    body = ('<h1>運営ダッシュボード</h1>'
            f'<p class="lead">ローイングマニアの定点観測。データ取得: {escape(meta["fetched_at"][:16].replace("T", " "))}</p>')
    body += ('<section><h2>サイト全体</h2><div class="stat-row">'
             f'<div class="stat"><span class="num">{len(_sitemap_paths)}</span>公開ページ</div>'
             f'<div class="stat"><span class="num">{len(years)}</span>年度</div>'
             f'<div class="stat"><span class="num">{len(events)}</span>種目</div>'
             f'<div class="stat"><span class="num">{total_races}</span>レース</div>'
             f'<div class="stat"><span class="num">{len(universities)}</span>大学</div>'
             '</div></section>')

    rows = "".join(
        f'<tr><td><a href="{rel}years/{y["year"]}/index.html">{y["year"]}年度</a></td>'
        f'<td>{len(y["events"])}</td>'
        f'<td>{sum(len(ev["races"]) for ev in y["events"].values())}</td>'
        f'<td>{escape(y["fetched_at"][:16].replace("T", " "))}</td></tr>'
        for y in years)
    body += ('<section><h2>年度別の取得状況</h2>'
             '<div class="tbl"><table><thead><tr><th>年度</th><th>種目数</th><th>レース数</th>'
             '<th>取得日時</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></section>')

    body += ('<section><h2>外部ツール（クリックで開く）</h2><ul>'
             '<li><a href="https://search.google.com/search-console">Search Console</a></li>'
             '<li><a href="https://analytics.google.com/">GA4</a></li>'
             '<li><a href="https://www.jara.or.jp/race/">日本ローイング協会 大会情報</a></li>'
             '</ul></section>')

    write_page(DASHBOARD_PATH,
               page(rel, f"運営ダッシュボード | {SITE_NAME}", body, meta,
                    path=f"{DASHBOARD_PATH}/", desc="運営用の内部ダッシュボード。",
                    sitemap=False))


# ---------------------------------------------------------------- misc output

def write_sitemap_and_robots():
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{SITE_BASE}{p}</loc><lastmod>{today}</lastmod></url>"
        for p in _sitemap_paths)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + urls + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_BASE}sitemap.xml\n", encoding="utf-8")


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#0b2e4a"/>
<path d="M8 44 Q32 36 56 44" stroke="#22b8cf" stroke-width="4" fill="none" stroke-linecap="round"/>
<text x="32" y="32" font-family="Arial, sans-serif" font-size="22" font-weight="bold"
 fill="#ffffff" text-anchor="middle">RW</text>
</svg>
"""

STYLE = """
:root {
  --navy:#071a33; --navy-2:#1d3a63; --accent:#b5652a; --accent-dark:#8f4e1f;
  --accent-soft:#f7ebe0; --ink:#0f1f33; --sub:#5b6b7b; --line:#dfe5ec;
  --bg:#f8f8f6; --surface:#fff;
  --gold:#b8860b; --silver:#6b7280; --bronze:#92400e;
}
* { box-sizing:border-box; }
body { margin:0; font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif;
  color:var(--ink); background:var(--bg); line-height:1.7; }
a { color:var(--navy-2); }
a:hover { color:var(--accent-dark); }

.site-header { background:var(--surface); border-bottom:1px solid var(--line); }
.header-inner { max-width:960px; margin:0 auto; padding:.7rem 1rem .5rem;
  display:flex; flex-wrap:wrap; align-items:center; gap:.3rem 1.5rem; }
.brand { display:flex; align-items:baseline; gap:.5rem; font-weight:800;
  color:var(--navy); text-decoration:none; font-size:1.25rem; letter-spacing:.02em; }
.brand-tick { width:.55em; height:.55em; background:var(--accent);
  border-radius:2px; align-self:center; }
.brand-sub { font-size:.6rem; color:var(--accent); font-weight:700; letter-spacing:.15em;
  text-transform:uppercase; }
.global-nav { display:flex; gap:.2rem; overflow-x:auto; margin-left:auto; }
.global-nav a { color:var(--navy); text-decoration:none; font-size:.85rem; font-weight:600;
  padding:.35em .7em; border-radius:6px; white-space:nowrap;
  border-bottom:2px solid transparent; }
.global-nav a:hover { border-bottom-color:var(--accent); }

.league-nav { background:var(--navy); }
.league-nav-inner { max-width:960px; margin:0 auto; padding:.3rem 1rem;
  display:flex; gap:.15rem; align-items:center; overflow-x:auto; }
.league-nav .league-name { color:#fff; font-weight:700; font-size:.85rem;
  margin-right:.6rem; white-space:nowrap; }
.league-nav a { color:#d7e0ea; text-decoration:none; font-size:.8rem;
  padding:.3em .6em; border-radius:6px; white-space:nowrap; margin-left:auto; }
.league-nav a:hover { background:var(--accent); color:var(--navy); }

.hero { max-width:960px; margin:0 auto; padding:1.6rem 1rem 0; }
.hero-img { width:100%; height:auto; display:block; border-radius:12px; margin-bottom:1.1rem; }
.hero-text { padding-bottom:1.8rem; }
.hero-kicker { color:var(--accent); font-weight:700; font-size:.85rem;
  letter-spacing:.2em; text-transform:uppercase; margin:0 0 .4rem; }
.hero h1 { font-size:1.5rem; line-height:1.45; margin:0 0 .6rem; color:var(--navy);
  font-weight:900; }
.hero-sub { color:var(--sub); font-size:.85rem; margin:0; }

main { max-width:960px; margin:0 auto; padding:0 1rem 3rem; }
h1 { font-size:1.35rem; line-height:1.45; }
h2 { font-size:1.08rem; border-left:4px solid var(--accent); padding-left:.55em;
  margin-top:2.4em; color:var(--navy); }
h3 { font-size:.95rem; margin-top:1.6em; }

.tbl { overflow-x:auto; background:var(--surface); border:1px solid var(--line);
  border-radius:12px; box-shadow:0 1px 3px rgba(7,26,51,.06); }
table { width:100%; border-collapse:collapse; font-size:.85rem; }
th, td { border-bottom:1px solid var(--line); padding:.5em .7em; text-align:left;
  white-space:nowrap; }
tbody tr:last-child td { border-bottom:none; }
thead th { background:var(--navy); color:#fff; font-weight:600; font-size:.78rem; }
tbody tr:nth-child(even) { background:var(--bg); }
tbody tr:hover { background:var(--accent-soft); }
td.score { font-weight:700; color:var(--navy); }
td.rank { font-weight:700; text-align:center; }
td.rk-gold { color:var(--gold); }
td.rk-silver { color:var(--silver); }
td.rk-bronze { color:var(--bronze); }
.cat { background:var(--accent-soft); color:var(--navy-2); font-size:.72rem; font-weight:700;
  padding:.15em .5em; border-radius:999px; }
table.detail th { background:#eaf2f4; color:var(--ink); width:9em; white-space:normal; }
table.detail td { white-space:normal; }

.breadcrumb { font-size:.8rem; color:var(--sub); margin-top:1rem; }
.breadcrumb a { color:var(--sub); }
.lead { color:var(--sub); }
.note { color:var(--sub); font-size:.8rem; }
.more { margin:.9rem 0 0; }
.cta { display:inline-block; background:var(--accent); color:var(--navy); font-weight:700;
  font-size:.85rem; text-decoration:none; padding:.5em 1.1em; border-radius:8px; }
.cta:hover { background:var(--accent-dark); color:#fff; }

.stat-row { display:flex; gap:.8rem; flex-wrap:wrap; }
.stat { background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:.7rem 1.1rem; font-size:.75rem; color:var(--sub); min-width:100px;
  text-align:center; box-shadow:0 1px 3px rgba(7,26,51,.06); }
.stat .num { display:block; font-size:1.35rem; font-weight:800; color:var(--navy); }

.digest { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr));
  gap:1rem; }
.digest-card { background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:.9rem 1rem 1rem; box-shadow:0 1px 3px rgba(7,26,51,.06); }
.digest-card h3 { margin:.1em 0 .6em; }
.digest-card h3 a { text-decoration:none; color:var(--navy); }
.digest-card h3 a:hover { color:var(--accent-dark); }
.digest-card .tbl { border:none; box-shadow:none; }

.sponsor p, .support-section .digest-card p { margin:.5em 0; }
.pr-badge { display:inline-block; background:#f2c94c; color:#4a3800; font-size:.65rem;
  font-weight:800; letter-spacing:.03em; padding:.12em .45em; border-radius:4px;
  margin-right:.45em; vertical-align:middle; }
.cta-sub { background:var(--navy-2); }
.cta-sub:hover { background:var(--navy); }
.cta-text { display:inline-block; background:none; color:var(--sub); font-weight:600;
  font-size:.8rem; padding:0; }
.cta-text:hover { color:var(--accent-dark); }
.article-cta { background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:1.1rem 1.3rem 1.2rem; margin-top:1.6rem; box-shadow:0 1px 3px rgba(7,26,51,.06); }
.article-cta h2 { margin-top:0; border-left:4px solid var(--accent); padding-left:.55em;
  font-size:1rem; }
.support-section { margin-top:2.4em; }

.cat-line { font-size:.8rem; margin:.4rem 0; }
.article { background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:1.4rem 1.6rem 1.6rem; box-shadow:0 1px 3px rgba(7,26,51,.06); }
.article h2 { margin-top:1.8em; }
.article h2:first-child { margin-top:.4em; }
.article li { margin:.3em 0; }

.site-footer { background:var(--navy); color:#9fb2c8; font-size:.75rem;
  margin-top:3rem; }
.footer-inner { max-width:960px; margin:0 auto; padding:1.4rem 1rem 2rem; }
.footer-brand { color:#fff; font-weight:800; font-size:.95rem; margin:0 0 .3rem; }
.footer-nav { display:flex; gap:1rem; margin:.2rem 0 .8rem; flex-wrap:wrap; }
.footer-nav a { color:#c3d1e0; text-decoration:none; }
.site-footer a { color:#c3d1e0; }

.contact-form { max-width:32rem; margin-top:1.2rem; }
.form-row { margin-bottom:1.1rem; display:flex; flex-direction:column; gap:.35rem; }
.form-row label { font-weight:700; font-size:.85rem; color:var(--navy); }
.form-row .req { display:inline-block; margin-left:.4em; font-size:.68rem; font-weight:700;
  color:#fff; background:var(--accent-dark); border-radius:4px; padding:.05em .4em; vertical-align:middle; }
.form-row input, .form-row select, .form-row textarea {
  font:inherit; padding:.55em .7em; border:1px solid var(--line); border-radius:8px;
  background:var(--surface); color:var(--ink); width:100%; }
.form-row textarea { resize:vertical; }
.form-row input:focus, .form-row select:focus, .form-row textarea:focus {
  outline:2px solid var(--accent); outline-offset:1px; }
.hp-field { position:absolute; left:-9999px; top:-9999px; width:1px; height:1px; overflow:hidden; }
button.cta { border:none; font:inherit; cursor:pointer; }
button.cta:disabled { opacity:.55; cursor:default; }
.form-message { margin-top:1rem; font-weight:700; }
.form-message-ok { color:var(--win, #15803d); }
.form-message-error { color:var(--loss, #b91c1c); }
"""


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    _sitemap_paths.clear()

    years = load_years()
    if not years:
        raise SystemExit("大会データがありません（fetch_rowing.pyを先に実行）")
    articles = load_articles()
    events, universities = build_indices(years)

    global_meta = {
        "source": "日本ローイング協会 (JARA)",
        "source_url": "https://www.jara.or.jp/race/",
        "fetched_at": max(y["fetched_at"] for y in years),
    }

    (SITE / "style.css").write_text(STYLE, encoding="utf-8")
    (SITE / "assets").mkdir()
    (SITE / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    if ASSETS.exists():
        for f in ASSETS.iterdir():
            if f.is_file():
                shutil.copy(f, SITE / "assets" / f.name)

    build_portal(years, events, universities, articles, global_meta)
    build_years_index(years, global_meta)
    year_list = [y["year"] for y in years]
    for i, y in enumerate(years):
        prev_y = year_list[i + 1] if i + 1 < len(year_list) else None  # 1年前
        next_y = year_list[i - 1] if i > 0 else None                  # 1年後
        build_year_page(y, prev_y, next_y, universities, global_meta)
    build_events_index(events, global_meta)
    for code in EVENT_ORDER:
        if code in events:
            build_event_page(code, events[code], universities, global_meta)
    build_universities_index(universities, global_meta)
    for u in universities.values():
        build_university_page(u, global_meta)
    build_articles(articles, global_meta)
    build_contact(global_meta)
    build_dashboard(years, events, universities, global_meta)
    write_sitemap_and_robots()

    print(f"OK: {len(_sitemap_paths)} pages "
          f"({len(years)} years, {len(events)} events, {len(universities)} universities) in {SITE}")


if __name__ == "__main__":
    main()
