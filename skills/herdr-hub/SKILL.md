---
name: herdr-hub
description: Herdr セッション内の複数コーディングエージェント (Claude Code / Codex / Devin 等) を hub-spoke で調整する runbook。呼び出したエージェントが hub になる。「別エージェントに作業を頼みたい」「複数 agent を並行運用したい」「pane の agent 同士で連携させたい」「worker / reviewer を束ねたい」で起動。HERDR_ENV=1 が前提。
license: MIT
---

# herdr-hub

Herdr セッション内の複数コーディングエージェントを統括する **hub のための runbook**。
段階順に並んでいるので、**いま自分がどの段階にいるかで引く**。

- 名簿の形式・検証・export → [references/roster.md](references/roster.md)
- transport 3 種の詳細と既定推定 → [references/transports.md](references/transports.md)
- 送受信・待機・往復削減・着地の作法 → [references/messaging.md](references/messaging.md)
- worker へ渡す briefing の雛形 → [references/briefing.md](references/briefing.md)
- agent の起動・配置・命名 → [references/startup.md](references/startup.md)
- context 残量の観測と交代手順 → [references/context-and-handover.md](references/context-and-handover.md)
- 裁定の境界（裁く/人間へ上げる、決断の要求の時機） → [references/escalation.md](references/escalation.md)
- hub の裁定の質（裏取り・hub 自身の出力を疑う） → [references/adjudication.md](references/adjudication.md)
- 実害カタログ（transport・運用の罠） → [references/failure-modes.md](references/failure-modes.md)

## §0 前提

**この skill を読むのは hub だけ。** worker は skill を読まない。hub が投げる briefing が作法の担保になる（codex 等 `.claude/skills` を読まない agent 種でも機能するための非対称）。

**人間は hub にだけ話し、hub が全 worker へ配る。** worker → 人間の直接経路を作らない。

まず環境を確認する。失敗したら「Herdr 管理下ではない」と報告して停止する。

```bash
test "${HERDR_ENV:-}" = 1
```

以降の手順は全て herdr 管理 pane 内を前提とする。CLI 構文の正典はインストール済みバイナリ — `herdr --help` と各コマンドグループ（`herdr agent` / `herdr pane` / `herdr tab` 等）を引く。

## §1 roster（名簿）

hub の起動時に「名前 → 役割」の対応表を得る。2 経路:

1. **起動引数**: `reviewer: レビュー専任, worker1: 実装` のように `名前: 役割` を並べる
2. **YAML**: `--roster <path>` で明示指定。省略時は cwd の `.herdr-hub.yml`

roster は **編成の意図（desired state）** を記述する。`agents:` は空でもよい（hub 単独で起き、後から動的に足す運用）。

**起動時に必ず検証する** — 各エントリを 3 分岐で処理する:

- **live に解決できる** → そのまま
- **live に無い + `kind` が解決できる**（個別 or `presets:` 経由） → **起動対象**。人間へ編成案を 1 行確認してから `herdr agent start` で起動（[references/startup.md](references/startup.md)）
- **live に無い + `kind` 無し** → **即座にエラー**。黙ってスキップ・警告で続行しない（typo 検出を守る）

あわせて、`presets:` / `defaults:` / agent 個別の参照先 `role_def`・`rules` file がすべて存在し読めることを確認（不在・不可読は即エラー）。**hub の `rules` / `role_def` は hub 自身がここで読む** — worker 向けは briefing へ注入する（delivery の非対称は [references/roster.md](references/roster.md)「rules の delivery」）。

スキーマ・優先順位（`defaults` → `preset` → 個別）・`rules` の union・動的追加・export 手順 → [references/roster.md](references/roster.md)

## §2 transport（通信経路）

宛先ごとに経路を選ぶ。解決は優先順位順（個別指定 > Claude→Claude は `sendmessage` > 宛先=Codex は `codex-queue` > `defaults.transport` > `herdr`）:

| 送り手 → 宛先 | transport |
|---|---|
| Claude → Claude | `sendmessage` |
| 任意 → Codex | `codex-queue` |
| それ以外 | `herdr` |

YAML の `transport:` で個別上書き可。`defaults.transport` は native 経路を持たない宛先への fallback（Claude 宛・Codex 宛の native 推定は潰れない）。各経路の要件・コマンド・罠 → [references/transports.md](references/transports.md)

## §3 通信プロトコル（骨子）

- **通常送信は非同期**（`herdr agent prompt <name> "<text>"` に `--wait` を付けない）。受け手は入力として起床する。`--wait` は即答が要る同期照会のみ
- **返信は hub 宛**: worker は `herdr agent prompt hub "..."` または SendMessage で `hub` 宛に送る。worker がこの手段を知るのは briefing だけ — **briefing に自分の agent 名と roster を必ず書く**
- **送信前 guard**: `herdr agent list` / `ListAgents` で宛先名が live に解決することを確認してから送る
- **監視禁止**: worker/hub に `herdr agent wait` で他者を監視させない。Claude 間では SendMessage の `notify_when_idle` を使う

詳細とエラー対処 → [references/messaging.md](references/messaging.md)

## §4 規律（骨子）

- **hub は実装しない。** 裁定と実装の分離 — 検査は自分が書く側に回ると発動しない
- **hub が推奨を出すときは「これは私の裁定であり人間の決定ではない」と明記する。** 書かないと受け手には両者が同じ形で届く
- **承認済み成果物・測定値は worker → worker 直送可。判断・裁定・新規の指摘は hub 経由**
- **指摘は 1 便に合流させる**（源が非同期に届くため。blocker だけ例外）
- **ack を求めない。訂正は次便に相乗りさせる**
- **照会には終了条件を先に書く。** 往復が伸びたら成果物ではなく自分が渡した前提を疑う
- **中継は情報を落とす** — 件数・集合の再掲を添える
- **着地したら終える。** 「終了です」通知も送らない（例外: 走行中の review を止める「停止」1 行）
- **context 使用率は実測でのみ書く。** worker に定期申告させない
- **裁定の境界を先に引く。** 裁くものと人間へ上げるものを分ける。正典（spec・ADR）が矛盾・不在なら自分の原理で解かずに上げる → [references/escalation.md](references/escalation.md)
- **hub は不変条件を裁き、手段は worker が決める。** 手段の裁定は実測でしか決まらず、hub は走らせる側に居ない
- **裁定に worker の数値・分類を引く前に 1 問訊く**（「何を測った値か」「baseline は」）。**hub 自身の出力を疑う** — worker に「私の裁定を壊しにきてください」と招く → [references/adjudication.md](references/adjudication.md)
- **状態の観測を重複させない**（CI の緑/赤等は 1 箇所だけが測る）。**判定（主張の真偽）は独立に取り直す** — こちらの重複は価値である
- **review 役を置くなら、その出力を裏取りする経路を置く**（hub が一次資料で読み直す / review 役に読んだ file の列挙を課す）
- **裁定は材料を出した全セッションへ戻す。** 届いていないものは追えない — 戻すのは裁定した側の義務
- **新しい agent を起動する前に `agent list` で idle を棚卸しし、「既存で足りないか」を問う**

## §5 worker の起動

roster の `kind` を持つ未 live エントリは起動対象 — 人間への編成案確認の後に hub が起動する。配置（pane split / tab create・既定 tab）/ `agent start` / 命名規約（herdr agent name = `claude --name` = codex session name）の手順は [references/startup.md](references/startup.md) が持つ。稼働中の追加は roster への 1 行追記 → 同じ検証・起動経路を通す（[references/roster.md](references/roster.md)「動的追加」）。

## §6 context 残量と交代

- **観測は `agent read` / `pane read` の `--source visible` で外側から**（worker の文脈を消費しない）
- 処置は 続行 / compact / 交代 の 3 択。**80% で交代判定**・auto-compact 検出で即交代
- 交代は **前任が内容ブロックを後任へ直接送る**（hub はエンベロープを書く）

手順の正典 → [references/context-and-handover.md](references/context-and-handover.md)
