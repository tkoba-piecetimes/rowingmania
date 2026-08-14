# ローイングマニア — 全日本大学ローイング選手権 全記録データベース

大学ボート（ローイング）の情報メディア「ローイングマニア」（運営: PieceTimes）。
日本ローイング協会（JARA）公式サイトが公開している「全日本大学ローイング選手権」
（インカレ）のレース結果ページから、2000年度以降の全レース結果を取得し、
静的サイトを生成する**大会アーカイブ型**サイト。

ラグビーマニア（対戦型リーグのデータモデル）と異なり、大学ボートには対戦型の
リーグ戦が存在しないため、「年度別大会結果アーカイブ＋種目別歴代優勝校＋大学別戦績」
を主コンテンツとするデータモデルを採用している。

- 公開URL: https://tkoba-piecetimes.github.io/rowingmania/
- 対象: 全日本大学ローイング選手権（インカレ）2000〜2025年度、男子7種目・女子6種目
  （年度により増減。詳細は docs/rowing-sources.md 参照）
- 掲載データ: 大学名（クルー名）・着順・500m毎スプリット・タイム・Qualify（勝ち上がり）
  のみ。**選手個人の氏名・身長・体重は取得・掲載しない**（個人情報配慮）。

## 仕組み

```
jara.or.jp（日本ローイング協会）
  → pipeline/fetch_rowing.py（年度×種目コードを総当たり取得、404はスキップ）
  → data/results/<年度>.json（年度別の正規化データ。確定済み年度はキャッシュ固定）
  → pipeline/generate_site.py（年度別・種目別・大学別に横断集計してページ生成）
  → site/
```

## 実行

```
cd pipeline
python fetch_rowing.py            # 全年度取得（過去年度はキャッシュがあればスキップ、
                                   # 当年度・前年度は毎回再取得）
python fetch_rowing.py --force    # キャッシュを無視して全年度再取得
python generate_site.py
```

ローカル確認: `python -m http.server 8941 -d site`

## サイト構成

- `site/index.html` — トップ（最新年度ハイライト・年度一覧・種目一覧）
- `site/years/<year>/` — 年度別結果（種目別決勝結果＋予選含む全レース結果）
- `site/events/<code>/` — 種目別歴代優勝校年表・通算優勝回数ランキング
- `site/universities/<slug>/` — 大学別の年度別出場種目・決勝進出回数・優勝回数
- `site/articles/` — 読みもの（`content/articles/*.md` を追加すれば自動で有効化される）

## 未実装（今後）

- ドメイン取得・GitHub Pages カスタムドメイン設定
- GA4 / Search Console 連携（GA_MEASUREMENT_ID・GSC_VERIFICATIONは空欄）
- 読みもの記事（`content/articles/`）
- 2026年度の大会公開後の自動反映確認（日次workflowで自動検知する設計だが未検証）
