# herdr-hub 設計 spec

2026-09-13

## 目的

Herdr セッション内で動く複数のコーディングエージェント（Claude Code / Codex / Devin 等、種混在可）を、**hub-spoke 構成で調整するための運用 runbook skill** を作る。

- この skill を読むのは **hub になるエージェントだけ**（呼び出し側 = hub）
- worker 側は skill を読まない。hub が投げる briefing が作法の担保になる（エージェント種を問わず機能させるための非対称）
- 人間は hub にだけ話し、hub が全 worker へ配る

元ネタは mixseek-data-lake の `multi-session-hub` skill（Claude Code 複数セッション運用の実績ある runbook）。本 spec はその**汎用化**であり、元 skill 自体は変更しない。

## スコープ

引き継ぐもの（`multi-session-hub` の 3 層のうち A+B）:

- **A. 通信・宛先同定の機構層** — roster 解決、送信、受信確認、状態待ち
- **B. hub 運用の規律層** — briefing、裁定の境界、指摘の合流、往復を減らす規律、着地したら終える、等

落とすもの（C 層、`multi-session-hub` に残す）:

- merge gate 5 条件、Copilot review、worktree lock、issue 起票ルール等の mixseek/GHE 固有運用

## 配置形態

- **ユーザーレベル skill**（全プロジェクト・全エージェントから使える位置）
- 本リポジトリが開発の正典。repo root = skill ディレクトリ（`SKILL.md` + `references/`）とし、インストールは `~/.claude/skills/herdr-hub` 等へのコピーまたは symlink で行う
- プラグイン化・他マシンへの配布は将来の拡張とし、本 spec の範囲外

## roster（名簿）

hub の起動時に「役割 → agent」の対応表を与える。2 経路:

1. **起動引数**: skill 起動プロンプトに `reviewer: レビュー専任, advisor: 設計相談, worker1: 実装` のように `名前: 役割` を並べる
2. **YAML**: `--roster <path>` で明示指定。省略時は cwd の `.herdr-hub.yml` を読む（存在しなければ引数指定のみで動く）

YAML スキーマ（案）:

```yaml
agents:
  hub:      { role: 統括,        transport: sendmessage }
  reviewer: { role: レビュー専任 }                        # transport 省略時は既定推定
  worker1:  { role: 実装,        transport: herdr, handoff_at: 0.9, placement: tab }
```

フィールド: `role`（必須・役割）/ `transport`（既定推定で省略可）/ `handoff_at`（交代閾値・既定 0.8）/ `placement`（`pane` 既定 or `tab`。agent 数が増えたら tab が視認性で有利。後から `herdr pane move <id> --new-tab` で tab 化も可）

### roster の検証（起動時に必ず行う）

- roster に載る全名前が `herdr agent list` で live に解決すること
- 解決できない名前があれば **即座にエラー**。黙ってスキップしない
- export 補助手順: `herdr tab list` + `herdr agent list` から現在の配置を YAML 雛形として出力する手順を `references/roster.md` に置く（tab label を役割の初期値にする）

## transport（通信経路）

宛先 agent ごとに経路を選ぶ。3 種:

| transport | 宛先 | 形式 | 条件 |
|---|---|---|---|
| `herdr` | 全 agent 種（既定） | CLI: `herdr agent prompt <name> "<text>"` | herdr 認識 agent |
| `sendmessage` | Claude セッション | agent tool（Claude が `SendMessage` を呼ぶ） | 送り手も Claude。Claude Code v2.1.224+ |
| `codex-queue` | Codex セッション | CLI: `codex queue --thread <name> --message "<text>"` | 誰でも送れる。codex-cli 0.149+（実機は 0.154.0 で確認） |

### transport の既定推定

- 送り手 = Claude かつ宛先 = Claude → `sendmessage`
- 宛先 = Codex → `codex-queue`
- それ以外 → `herdr`
- YAML の `transport:` で個別上書き可

### 命名規約（重要）

宛先解決を 1 つの roster で済ませるため、**3 系統の名前を揃える**:

- herdr agent name（`herdr agent start <name>`）
- Claude セッション名（`claude --name <name>`）
- Codex セッション名（`codex` の session name）

起動手順（`references/startup.md`）で `herdr agent start worker1 --pane <id> -- claude --name worker1` のように同一名を付ける規約とする。

## 通信プロトコル

- **通常送信は非同期**: `--wait` なしで prompt を投げる。受け手は入力として起床する。`--wait` は「送って即答が要る」同期的照会のみ
- **返信経路**: worker は `herdr agent prompt hub "..."`（または SendMessage で `hub` 宛）で hub を起こす。worker がこの手段を知る唯一の経路は briefing なので、**briefing に自分の agent 名と roster を必ず書く**
- **宛先 guard**: 送信前に `herdr agent list`（または `ListAgents`）で名が live に解決することを確認する
- **監視禁止**: worker/hub に `herdr agent wait` で他者を監視させない。Claude 間では `SendMessage` の `notify_when_idle`（idle 時 1 回通知）を使う

### transport 固有の罠

- **SendMessage**: 受け手が bypass 系・送り手がプロンプト系の組み合わせだとメッセージが held になり人間の承認待ちになる。無人運用は `crossSessionInbound: accept` か permission mode の組を揃えること。サイズ上限・バースト上限あり。自分宛送信は拒否される
- **codex queue**: 公式ドキュメント未掲載（実機 0.154.0 で `--help` 確認済み）。`--thread` は UUID または厳密なセッション名
- **herdr**: `blocked` は承認 UI 待ち（完了ではない）、`unknown` は分類不能（完了の証明ではない）。`agent_prompt_stalled` / `timeout` は未配送を意味しない。alternate screen 上の agent は `pane read` で全文を取れないことがある

## 引き継ぐ規律（B 層）

SKILL.md 本体に骨子、詳細は references へ:

- `references/roster.md` — YAML スキーマ、引数形式、export 手順
- `references/messaging.md` — 送受信・状態待ち・各 transport のエラー意味論
- `references/transports.md` — transport 3 種の詳細と既定推定表
- `references/briefing.md` — GHE 要素を抜いた汎用 briefing 雛形（宛先 guard → 役割 → 最初の一手 → 既知の罠 → 作法 → 境界 → 進め方）
- `references/startup.md` — pane split / agent start / 命名規約（補助的・段階的。起動そのものは人間または別手段が行う前提を正とする）
- `references/context-and-handover.md` — 下記「context 残量と交代」の詳細
- `references/failure-modes.md` — 上記「罠」+ `agent wait` 監視禁止 + herdr 固有の失敗面

規律の骨子（`multi-session-hub` から汎用化して転記）:

- hub は実装しない（裁定と実装の分離）
- hub が推奨を出すときは「これは私の裁定であり人間の決定ではない」と明記
- 承認済み成果物・測定値は worker → worker 直送可、判断・裁定は hub 経由
- 指摘は 1 便に合流させる（源が非同期に届くため）
- ack を求めない。訂正は次便に相乗り
- 照会には終了条件を先に書く
- 中継は情報を落とす — 件数・集合の再掲を添える
- 着地したら終える（「終了です」通知も送らない。例外: 走行中の review を止める「停止」1 行）
- context 使用率は実測でのみ書く。worker に定期申告させない

## context 残量と交代

### 観測

- **第一は `herdr agent read` / `pane read` で statusline の context メーターを外側から読む** — worker の文脈を消費しない（herdr 環境の利点）
- **実測済み（Devin CLI）**: footer に `Context: 127k / 262k tokens (48%)` が常時描画され、`pane read --source visible` で scrape できる（2026-09-13 実機確認）
- **Claude / Codex は要実機確認**。常時表示が無い・読めない場合の fallback: `/context`（Claude）や `/status`（Codex）等の **クライアント側 slash コマンドを pane へ打ち込んで描画を読む** — モデルの文脈を消費せず、読み終えたら esc で閉じる
- それでも取れない場合は**オンデマンド申告のみ**（定期申告は往復コスト + 捏造を招いた実績があるため禁止）

### 処置の 3 択（判断は hub）

| 処置 | 向く場面 |
|---|---|
| 続行 | 残量に余裕 |
| compact | タスク途中。名前・roster・briefing が存続するので最も安い |
| 交代 | タスクの継ぎ目（PR・issue 単位）。herdr では agent だけ入れ替えられる |

### 交代の手順

1. 残量 **80%** で交代判定（`handoff_at` で per-agent 上書き可）
   - ⚠ **auto-compact 済みを検出したら閾値無視で即交代** — 要約済み記憶から書く handoff は二次記述で品質が劣る
2. 前任生存中に後任を**仮名**（`<name>-next`）で起動（名前は live 間で一意のため同名を取れない）
3. **briefing の内容ブロックは前任が後任へ直接送る**（現在の状態・最初の一手・既知の罠 — 落とした本人が最も詳しい。hub 中継の情報落下を避ける）
   - エンベロープ（宛先 guard・役割・作法・境界）は **hub が書く**（roster 全体の文脈は hub にしかない）
4. 前任 exit → roster を後任へ付け替え

### 発火時コストを常時化して潰す

交代コストの支配項は**後任の context 再暖機**であり、発火時期に依存しない。発火時に安全に書き切るため:

- worker は進捗・判断・罠を **固定パスの共有ログ**（`/tmp/herdr-hub/<name>.log`）へ随時追記する（briefing の作法に含める）
- handoff は「ログのパス + 差分」で済む → 発火時生成コスト ≈ 0 → 高い閾値でも安全

### hub 自身の交代

`.herdr-hub.yml` の **roster ファイルが新規 hub セッションの再開資材**になる。人間が新セッションで `herdr-hub --roster` を起動すれば hub だけ交換して運用を継続できる。

## 起動フェーズの責務（段階的）

- **正**: 既に live な agent の調整（roster 検証 → briefing → 運用）
- **補助**: `references/startup.md` に pane/tab 作成と `agent start` の手順を置く。skill が自動で起動まで行うのは将来拡張

## 非目標

- GHE/PR/CI 固有の運用（`multi-session-hub` の C 層）
- herdr 管理外・別マシンの agent の発見と編成（transport がネイティブに届く範囲のみ）
- roster の永続化管理・マルチワークスペース編成

## 検証方法

skill は文書なので、検証は「実際の herdr セッションで hub + worker 1 名を立て、briefing → 指示 → 返信 → 着地まで一周させる」実演とする。各 transport（herdr / sendmessage / codex-queue）で最低 1 回の送受信を確認する。
