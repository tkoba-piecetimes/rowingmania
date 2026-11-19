# SERP分析メモ｜taiikukai-boat-shukatsu リライト診断（2026-11-19・diagnose45）

- 対象: `content/articles/taiikukai-boat-shukatsu.md`（公開2026-08-14・94日経過）
- 候補ID: cmukntdod022ale04r11tbnji
- GSC（週 2026-11-16）: 表示29・クリック8・CTR27.6%・平均順位3.55（同順位帯の平均CTRは7.8%）
- 狙いKW（titleとslugから推定）: 「ボート部 就活 有利」「漕艇部 就活 アピール」
- 前回メモ: `taiikukai-boat-shukatsu-rewrite-20260917.md`（triage30。当時は表示0・被リンク0。ES・面接の専門記事へのリンクを追加済み）

## WebSearch結果（2026-11-19）

### 「ボート部 就活 有利」
- 上位は高校・大学のボート部紹介PDF（八尾高・岐阜大・島根大）、外資就活ドットコムの体育会就活コラム、北海道新聞の記事、マイナビキャリアリサーチLab（運動部学生の意識調査）、高知工科大の論文PDF（体育会と就活の関係）。
- **ボート部と就活を扱う専用記事は上位にない。** 競技を問わない体育会記事か、部の紹介資料ばかり。
- 独自要素として目立つのは、調査データ（マイナビ×UNIVAS）と学術的な見方（高知工科大）の2つ。

### 「漕艇部 就活 アピール 体育会」
- 上位はワンキャリア・就活の教科書（jo-katsu）・外資就活ドットコム・インターンシップガイド・ネオキャリアなど、体育会全般向けの記事。記事型は「体育会の強み→アピール方法→注意点（体育会なのに頼りない印象など）→向いている業界」の解説型。
- 漕艇部ならではの切り口（未経験から始める人が多い・クルーでの役割・コックス）を書いた記事は見つからなかった。

## 一次情報の確認
- 確認済み: マイナビアスリートキャリアと大学スポーツ協会（UNIVAS）の「運動部学生の就職に関する意識調査」（2022年3月発表）。就活経験者に聞くと「有利だと思う」39.3%、「どちらかというと有利だと思う」38.2%で、合わせて77.5%。調査時期とサンプル数は記事に書かれていない。https://career-research.mynavi.jp/?p=25398
- 未確認: 高知工科大の論文PDF（https://www.kochi-tech.ac.jp/library/ron/pdf/2021/03/15/a1220401.pdf）。検索結果の要約では「就職の結果に差は見られず、就活の過程では心理面で有利に働く可能性」とされている。ただしPDFが圧縮されていて本文を読めず、タイトル・著者・結論を確かめられていない。**本文を読んで確かめるまで記事には使わない。**

## 自媒体の状況
- 本記事へのリンクは0本から4本に増えた（ob-shinro・taibu-kento・stroke-position-yakuwari・intai-jiki-intai-shiai）。本記事からも ob-tekishoku・ob-shinro・es-jikopr・mensetsu へリンクしている。孤立は解消済み。
- 本記事は、ES・面接・適職・進路の各記事をまとめる親記事として機能している。

## 診断（§3bの9要素）
| 要素 | 層 | 見立て |
|---|---|---|
| 検索意図の一致 | article | 一致している。上位の体育会記事と同じ解説型で、ボートに特化している分だけ当記事が上回る |
| タイトル・スニペット | article | CTR27.6%で同順位帯平均7.8%の約3.5倍。変更すると下がるおそれがあるので触らない |
| 網羅性 | article | ほぼ足りている。抜けているのは「有利と言われる根拠のデータ」と「漕手以外（コックス・マネージャー）や実績がない人の伝え方」 |
| 独自性・E-E-A-T | article / media | 出典が「各種就活関連メディア」とあいまい。具体的な調査URLを示せば補える。部員やOBの生の声は一次情報バンクにないため media 層 |
| 構成・読みやすさ | article | 冒頭は3文で短く、表もある。大きな問題なし |
| 内部リンク | article | 孤立は解消済み。役割の記事（stroke-position-yakuwari）への発リンクがないので1本足す |
| ドメイン評価・被リンク | media | 1位はおそらく大手の体育会就活メディアか部の紹介PDF。記事だけでは対応できない |
| 技術・表示 | media | 記事側で不具合は見つからない。構造化データ（Article・FAQ）はテンプレート側の対応 |
| CV | article / media | ツナカレ就活へのCTAは1か所。小さく文言を直す余地はあるが、CV計測が媒体全体で取れていないため media 層 |

## 結論
大きな書き直しは不要。差分は小さいものだけにする（データ1段落・コックスとマネージャーのH3・FAQ 2問・出典の具体化・内部リンク1本）。タイトルとdescriptionは変更しない。意図の変更や統合の提案はない。

## 出典
- https://career-research.mynavi.jp/?p=25398
- https://www.kochi-tech.ac.jp/library/ron/pdf/2021/03/15/a1220401.pdf（未確認）
- https://gaishishukatsu.com/archives/12707
- https://onecareer.jp/articles/2147
- https://jo-katsu.com/campus/4365
- https://internshipguide.jp/columns/view/jock-employment
- https://www.neo-career.co.jp/careertrus/shukatsu-shukatsuagent-sports-students
- https://www.hokkaido-np.co.jp/article/201484/
