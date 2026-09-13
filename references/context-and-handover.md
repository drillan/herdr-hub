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

## 発火時コストを常時化して潰す

交代コストの支配項は**後任の context 再暖機**であり発火時期に依存しない。発火時の生成量を減らすため:

- worker は進捗・判断・罠を **`/tmp/herdr-hub/<name>.log` へ随時追記**（briefing の作法に含める）
- handoff は「ログのパス + 差分のひとこと」で済む → 発火時生成コスト ≈ 0 → 高い閾値でも安全に書き切れる
- 揮発知識を随時ファイルへ逃がす設計。「引き継ぐものが無ければ handoff は不要」が成立する状態を保つ

## hub 自身の交代

`.herdr-hub.yml` の **roster ファイルが新規 hub セッションの再開資材**になる:

1. 人間が新しいセッションを起ち上げ、`herdr-hub` を `--roster`（または既定パス）で起動する
2. 新 hub は roster 検証で全 worker を再認識し、briefing ではなく「hub 交代の告知」を全 worker へ送る
3. 旧 hub の裁定の経緯・却下した案・worker ごとの癖はどこにも書かれていない — **旧 hub は退く前にこれらを人間へ報告するか `.herdr-hub.yml` のコメントとして残す**
