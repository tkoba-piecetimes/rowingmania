# -*- coding: utf-8 -*-
"""大学名（クルー名） → URLスラッグの対応表とスラッグ解決ロジック。

jara.or.jp のクルー表記は基本的に「○○大学」のフル表記（学部付き表記が混在する
ことがある: 例「早稲田大学理工学部」）なので、ラグビー版のような大学名の省略
表記ゆれは少ない。頻出校のみ手動で読みやすいスラッグを登録し、残りは
pykakasiのローマ字化にフォールバックする。
"""
import re
import sys

UNIV_SLUGS = {
    "早稲田大学": "waseda",
    "慶應義塾大学": "keio",
    "明治大学": "meiji",
    "法政大学": "hosei",
    "立教大学": "rikkyo",
    "中央大学": "chuo",
    "東京大学": "tokyo-u",
    "京都大学": "kyoto-u",
    "一橋大学": "hitotsubashi",
    "東京工業大学": "tokyo-tech",
    "東京科学大学": "science-tokyo",
    "筑波大学": "tsukuba",
    "北海道大学": "hokkaido-u",
    "東北大学": "tohoku-u",
    "名古屋大学": "nagoya-u",
    "大阪大学": "osaka-u",
    "九州大学": "kyushu-u",
    "神戸大学": "kobe-u",
    "同志社大学": "doshisha",
    "立命館大学": "ritsumeikan",
    "関西大学": "kansai-u",
    "関西学院大学": "kwansei-gakuin",
    "近畿大学": "kindai",
    "龍谷大学": "ryukoku",
    "日本大学": "nihon-u",
    "東海大学": "tokai",
    "専修大学": "senshu",
    "青山学院大学": "aoyamagakuin",
    "学習院大学": "gakushuin",
    "成城大学": "seijo",
    "武蔵大学": "musashi",
    "獨協大学": "dokkyo",
    "東京経済大学": "tokyo-keizai",
    "国際基督教大学": "icu",
    "東京農業大学": "tokyo-nodai",
    "東京理科大学": "tus",
    "東京都立大学": "tmu",
    "横浜国立大学": "ynu",
    "横浜市立大学": "yokohama-cu",
    "千葉大学": "chiba-u",
    "埼玉大学": "saitama-u",
    "群馬大学": "gunma-u",
    "茨城大学": "ibaraki-u",
    "山梨大学": "yamanashi-u",
    "新潟大学": "niigata-u",
    "金沢大学": "kanazawa-u",
    "信州大学": "shinshu-u",
    "静岡大学": "shizuoka-u",
    "岐阜大学": "gifu-u",
    "三重大学": "mie-u",
    "滋賀大学": "shiga-u",
    "京都産業大学": "kyoto-sangyo",
    "大阪市立大学": "osaka-cu",
    "大阪公立大学": "osaka-metropolitan",
    "大阪府立大学": "osaka-pu",
    "大阪工業大学": "osaka-kogyo",
    "大阪経済大学": "osaka-keizai",
    "大阪商業大学": "osaka-shoin",
    "甲南大学": "konan",
    "広島大学": "hiroshima-u",
    "岡山大学": "okayama-u",
    "愛媛大学": "ehime-u",
    "松山大学": "matsuyama-u",
    "九州工業大学": "kyutech",
    "福岡大学": "fukuoka-u",
    "西南学院大学": "seinan-gakuin",
    "熊本大学": "kumamoto-u",
    "鹿児島大学": "kagoshima-u",
    "小樽商科大学": "otaru-uc",
    "東北学院大学": "tohoku-gakuin",
    "総合研究大学院大学": "sokendai",
    "兵庫大学": "hyogo-u",
    "東京医科歯科大学": "tmdu",
}

_kks = None


def _romaji(name: str) -> str | None:
    global _kks
    try:
        if _kks is None:
            import pykakasi
            _kks = pykakasi.kakasi()
        base = re.sub(r"(大学院|大学)$", "", name.strip()) or name.strip()
        s = "-".join(x["hepburn"] for x in _kks.convert(base))
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
        return s or None
    except Exception:
        return None


def slug_for(univ: str) -> str:
    if univ in UNIV_SLUGS:
        return UNIV_SLUGS[univ]
    r = _romaji(univ)
    if r:
        UNIV_SLUGS[univ] = r
        return r
    print(f"[warn] スラッグ生成不可のクルー名: {univ}", file=sys.stderr)
    return f"crew-{abs(hash(univ)) % 10**8}"
