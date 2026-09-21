# context 残量と交代

## 観測

**第一は pane を外側から読む。** worker の文脈を消費しない。

```bash
herdr pane read <pane> --source visible --lines 10
# agent を名で解決するなら同じ source を取れる agent read でもよい
herdr agent read <name> --source visible --lines 10
```

- **Devin CLI（実測済み）**: footer に `Context: 127k / 262k tokens (48%)` が常時描画される（2026-09-13 実機確認）
- **Claude / Codex は要実機確認。** 常時表示が無い・読めない場合の fallback: **クライアント側 slash コマンドを pane へ打ち込んで描画を読む**（Claude `/context`、Codex `/status`）。これらはモデルの文脈を消費しない。読み終えたら `agent send-keys <name> esc` で閉じる
- それでも取れない agent kind は **オンデマンド申告のみ**。⛔ 定期申告は禁止（往復自体が文脈を消費し、欄は捏造を招いた実績がある）。訊くときは hub が名指しし、実測値の行ごと貼らせる

## 処置の 3 択（判断は hub）

| 処置 | 向く場面 |
|---|---|
| 続行 | 残量に余裕 |
| compact | タスク途中。名前・roster・briefing が存続するので最も安い |
| 交代 | タスクの継ぎ目。herdr では agent だけ入れ替えられる |

「いま失って困るのは土地勘か独立性か」で選ぶ。compact は土地勘を、交代は独立性を守る。

## 交代の手順

1. **使用率 `handoff_at`（既定 80% = 80% 使用）で交代判定。** roster YAML で per-agent 上書き可
   - ⚠ 閾値は**使用率**であり残量ではない。メーター表記は `Context: 127k / 262k tokens (48%)` の使用率なので、比較はそのまま `handoff_at` と行う
   - ⚠ **auto-compact 済みを検出したら閾値無視で即交代。** 要約済み記憶から書く handoff は二次記述で品質が劣る。検出は pane read で: メーター使用率が高値から急落している、または scrollback に compaction 通知行がある（各 agent kind の表示は要実機確認）
   - 閾値は「handoff を書くのに十分な残量が残っているうち」に置く。遅らせると利用率は上がるが handoff 品質のリスクを取る（交代コストの支配項は後任の再暖機で、発火時期に依存しない）
2. **前任生存中に後任を仮名 `<name>-next` で起動**（名前は live 間で一意のため同名を取れない）。手順は [startup.md](startup.md)
3. **briefing の内容ブロックは前任が後任へ直接送る**（[briefing.md](briefing.md) の分担表）
   - 前任が書く: 現在の状態 / 最初の一手 / 既知の罠
   - hub が書く: 宛先 guard / 役割と一元化 / 作法 / 境界 / 進め方
   - 送信は roster と同じ transport 推定で
4. **前任 exit → 名の整理。** `herdr agent rename <name>-next <name>` で後任へ正名を付けるのが最も簡単（roster のキーがそのまま使える）。仮名のまま運用するなら roster のキーを `<name>-next` に付け替える必要がある — どちらか一方は必ず行う
   - `agent rename` が変えるのは agent 名のみ — **pane ラベル・tab ラベルは追従せず仮名のまま残る**（人間がタブバーで旧名を目視する。2026-09-13 実機確認）。正名を取る際はあわせて `herdr pane rename <pane_id> <name>` と `herdr tab rename <tab_id> <name>` を実行する

## 発火時コストを常時化して潰す

交代コストの支配項は**後任の context 再暖機**であり発火時期に依存しない。発火時の生成量を減らすため:

- worker は進捗・判断・罠を **`/tmp/herdr-hub/<name>.log` へ随時追記**（briefing の作法に含める）
- handoff は「ログのパス + 差分のひとこと」で済む → 発火時生成コスト ≈ 0 → 高い閾値でも安全に書き切れる
- 揮発知識を随時ファイルへ逃がす設計。「引き継ぐものが無ければ handoff は不要」が成立する状態を保つ
- **試して駄目だったことを厚く残す。** 成功手順は後任も発見するが、死に筋は書かないと同じ場所で同じ時間を燃やす

## 恒久性クラス（何が生き残るか）

handoff で「どこに書けば届くか」を決めるため、情報の置き場を生存期間で分ける:

| クラス | 例 | 生存期間 |
|---|---|---|
| **恒久（hosted）** | issue tracker、repo の tracked file、PR 本文 | セッション・マシンを跨いで残る。裁定・決定の置き場 |
| **machine-local** | `/tmp/herdr-hub/*.log`、`.herdr-hub/`（gitignore 済みなら）、shell 履歴 | そのマシン上では残るが、clone・別環境では消える。補助ログの置き場 |
| **揮発** | agent の文脈、pane scrollback、画面表示 | compact / exit で消える。ここにだけある知識は恒久か machine-local へ逃がす |

⛔ **裁定・決定を揮発・machine-local のままにしない。** 届くべき相手が読める恒久層へ置く（裁定 → 正典か tracker へ、逐語 + 裁定日で）。

**共有メモリ（複数 agent が読む置き場）の writer は hub 単独にする。** worker が各自で共有置き場を更新すると、writer が分散して更新の衝突・陳腐化の検出が効かなくなる。worker は自分のログを書き、共有置き場への転記は hub が行う。

## hub 自身の交代

**交代の合図**: ①`handoff_at` 閾値（他 agent と同じ）②auto-compact 検出 ③**フェーズの変化**（大きな裁定の束が閉じた、作業の区切り）。③は閾値に依らず検討する — フェーズを跨いだまま旧 hub が残ると、新規判断と旧裁定の経緯が混ざる。

`.herdr-hub.yml` の **roster ファイルが新規 hub セッションの再開資材**になる:

1. 人間が新しいセッションを起ち上げ、`herdr-hub` を `--roster`（または既定パス）で起動する
2. 新 hub は roster 検証で全 worker を再認識し、briefing ではなく「hub 交代の告知」を全 worker へ送る
3. 旧 hub は退く前に **3 種の引き継ぎ**を残す — ①**裁定の経緯**（何を裁き、なぜか）②**却下した案**（後任が同じ案を検討して無駄にしないため）③**worker ごとの癖**（報告の精度・踏みやすい罠）。置き場は人間への報告または `.herdr-hub.yml` のコメント。**出所ラベル（旧 hub の判断である旨）を添える** — 引き継ぎは一次資料ではなく二次記述なので、出所が書かれていないと正典と同じ重みで読まれる

**引き継ぎの形は handoff file に限らない。** 恒久層（tracker・merge 済の文書・repo）から読めるものがほとんどなら、新 hub への 1 便で足りる — 揮発分が 5〜7 件程度のとき file 無しの直接引継ぎが 3 代連続で機能した実績がある。揮発分が多いときだけ file を介する。

## 共有可変ポインタ（latest 系）の扱い

「latest」「current」のような**共有で可変なポインタ**は複数 writer で壊れる（一方が更新すると他方の参照先が変わる）。handoff・briefing で file を渡すときは絶対パス・固定 SHA で渡し、latest 系ポインタの更新は **1 箇所（hub または担当 1 名）だけが行う**。
