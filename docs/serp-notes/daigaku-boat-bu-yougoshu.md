# SERP分析メモ: 大学ボート部 用語集（漕艇・ローイング用語）

- 作成日: 2026-09-21
- 対象KW: 「大学ボート部 用語集」（近接: 「ボート競技 用語」「漕艇 用語 一覧」「ローイング 用語」）
- KW在庫の該当: K4（企画系）＝P11（部員向け定番）の統合。レーン: K
- 記事slug: `daigaku-boat-bu-yougoshu`

## KW選定の経緯（K1からの変更理由）

当初候補はK1「全日本大学ローイング選手権 通算優勝回数ランキングTOP10」だったが、
**既に `content/articles/incare-boat-yusho-ranking.md`（2026-09-14公開、タイトル「大学ボート部の強豪大学はどこ？インカレボート通算優勝回数ランキング」）で公開済み**
であることを確認したため見送った。K16「女子種目の出場校数推移」も
`daigaku-boat-bu-shutsujo-kosu-suii.md` で公開済み。

代替候補の可否を実データで検証した結果:

| 候補 | 可否 | 根拠 |
|---|---|---|
| K7 インカレ開催地・コース一覧 | 見送り | `data/results/*.json` に会場・コースのフィールドが存在しない（年度メタは `year`/`edition`/`tournament_name`/`source_url`/`fetched_at` のみ）。25年度分の開催地を外部から個別に裏取りする必要があり、精度リスクが高い |
| K14 全日本新人選手権 歴代優勝校 | 不可 | `data/results/` はインカレ（全日本大学選手権）本戦のみ。新人戦のレース結果データを保持していない |
| K5 日本代表輩出大学ランキング / K9 部員数 / K10 エルゴ記録 / K11 未経験歓迎度 | 見送り | いずれも自サイト外の公開情報を大学単位で網羅収集する必要があり、欠測大学の扱いで正確性を担保しづらい |
| K2 強豪校まとめ（地区別・種目別） | 見送り | 公開済みのK1記事と検索意図が重複しカニバリスクが高い |
| **K4 用語集まとめ（決定版）** | **採用** | 自サイトの一次データ（種目コード15種・レースラウンド表記）で独自要素を構成でき、外部の裏取りもJARA公式・自治体公開資料で完結する |

## SERP 1ページ目の顔ぶれ（WebSearch 2026-09-21）

「大学ボート部 用語集 ローイング 用語 一覧」「ボート競技 用語 解説 漕艇 初心者 リギング キャッチ フィニッシュ レート」で確認。

- 東郷町公式「用語集 - ボート」 https://www.town.aichi-togo.lg.jp/soshikikarasagasu/shogaigakushuka/gyomuannai/2/3/2424.html （五十音順の網羅的な用語集。自治体の生涯学習ページで、大学部活の文脈はなし）
- 東郷町公式「ボートの基本動作」 https://www.town.aichi-togo.lg.jp/soshikikarasagasu/shogaigakushuka/gyomuannai/2/3/2423.html
- ローイング競技 - Wikipedia https://ja.wikipedia.org/wiki/ローイング競技
- NTT東日本 漕艇部「ボートの楽しみ方」 https://www.ntt-east.co.jp/symbol/boat/contents/howto.html （実業団チームの入門ページ）
- SPOPITA「ボート（ローイング）競技紹介」 https://spopita.jp/sport/boat/
- ボート競技.jp「ボート競技の基本用語」 http://ボート競技.jp/vocabulary/
- 個人ブログ https://toubiyanmar.com/archives/845
- **競艇（ボートレース）系の用語辞典が複数混入**: boatrace.jp 用語辞典 / kyotei-advisor.net / apaie.org（フネラボ）

## 共通点（検索意図の正解）

1. キャッチ・フィニッシュ・フォワード・レート（ピッチ）など**漕ぎの基本動作の用語**を必ず載せている。
2. スカル／スイープ、エイト・フォア・ペア・シングルスカルといった**艇種と乗艇人数**の説明がある。
3. コックス・ストローク・バウなど**乗艇ポジション**の語も定番として含まれる。

## 上位陣に欠けている要素（＝差別化点）

1. **種目コード（m1x / w4x+ / m8+ など）の読み方を解説したページが存在しない**。JARAの公式レース結果ページも自サイトの結果ページもこのコードで種目を表記しているのに、上位のどの用語集にも対応表がない。
2. **レース進行の表記（予選=Heat / 敗者復活戦=Repechage / 準々決勝=Quarter finals / 準決勝=SemiFinal / 決勝A〜E=Final A〜E）を扱っていない**。大会結果を自分で読む部員・保護者が実際につまずく語なのに空白地帯。
3. **競艇（ボートレース）の用語辞典がSERPに混ざり込んでおり、「ボート 用語」単体では大学の漕艇にたどり着けない**。タイトル・見出し・descriptionに「大学ボート部」「漕艇」「ローイング」を明示することで棲み分ける（keyword-inventory.md §5の運用ルール）。

## 自サイト一次データから使える裏取り済みの事実（2026-09-21 `data/results/` 実測）

- 収録範囲: 2000〜2025年度（2021年度はJARA側に種目別レース結果ページが存在せずデータなし）＝**25年度分**
- 収録レース数: **4,416レース**
- 大学（クルー表記）数: **174**（`site/universities/` の生成ページ数と一致）
- 種目コードは通算**15種**: m1x / m2x / m2- / m2+ / m4x / m4- / m4+ / m8+ / w1x / w2x / w2- / w4+ / w4x / w4x+ / w8+（年度により増減）
- ラウンド別レース数: 予選1,561・敗者復活戦1,385・準決勝780・準々決勝50・決勝A 305・決勝B 303・決勝C 24・決勝D 4・決勝E 4
- **決勝C は2022〜2025年度、決勝D・決勝E は2023年度のみ**に設定実績がある

## 内部リンク方針

一次データページへ2本以上（必須）:
- `/events/index.html`（種目一覧）と種目コード別ページ `/events/<code>/index.html`
- `/years/index.html`・`/years/2025/index.html`（年度別結果）
- `/universities/index.html`（大学別戦績）

関連記事（カニバリ回避のため、詳細は既存記事へ送る）:
- `scull-sweep-chigai-daigaku-boat`（スカル/スイープの詳細）
- `boat-bukatsu-cox-towa`（コックスの詳細）
- `boat-kyougi-rule-kaisetsu`（競技ルール）
- `incare-boat-kengaku-guide`（観戦ガイド）
- `incare-boat-yusho-ranking`（通算優勝回数ランキング）

## 出典（本文に明記するも）

- 公益社団法人日本ローイング協会（JARA） https://www.jara.or.jp/
- JARA 第52回全日本大学ローイング選手権大会 https://www.jara.or.jp/2025university/
- JARA 2025年度インカレ レース結果 https://www.jara.or.jp/race/2025/2025intercollege.html
- 東郷町「用語集 - ボート」 https://www.town.aichi-togo.lg.jp/soshikikarasagasu/shogaigakushuka/gyomuannai/2/3/2424.html
- 東郷町「ボートの基本動作」 https://www.town.aichi-togo.lg.jp/soshikikarasagasu/shogaigakushuka/gyomuannai/2/3/2423.html
- NTT東日本 漕艇部「ボートの楽しみ方」 https://www.ntt-east.co.jp/symbol/boat/contents/howto.html
