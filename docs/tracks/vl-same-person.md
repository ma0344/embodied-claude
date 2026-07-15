# VL 同一人物判定（様子見）

**状態**: 💤 2026-07-15 棚上げ  
**きっかけ**: Azure Face 個人認識は却下（申請・クラウド・面倒）。代わりにローカル VL で「同じ人物か？」スモーク。

## 現状（本線は触らない）

- 在席ゲートは **`present` bool**（誰かまでは見ない）のまま → [koyori-near-eye.md](../ops/koyori-near-eye.md)
- Azure Face Identify：**見送り**

## スモークメモ（2026-07-15）

VL（文章分類 e4b ではなく vision）に2枚載せて「同一人物か？」:

| 条件 | 結果 |
|------|------|
| サングラス | OK |
| 眼鏡なし | OK |
| うつむき加減の正面 | OK |
| 横顔のみ（見本が正面寄り） | NG |

仮説: **見本に正面＋横顔を足せば横顔も行ける**可能性あり。ただし物語合わせであって生体認証ではない。

## 再開時（そのうち）

1. 見本セット（正面／横）＋ probe 比較の小さなスクリプト or API
2. false positive（別人）／false negative（横顔・暗所 near JPEG）を測る
3. 偽陽性が実害（家族が机 → 声かけ）になるまで **本番ゲートには載せない**

## 参照

- 在席: [koyori-near-eye.md](../ops/koyori-near-eye.md)
- Azure 却下の経緯: Linksee thread `2026-07-14-near-eye-scope`
