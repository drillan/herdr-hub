# transports（通信経路）

宛先 agent への送信経路。roster の `transport:` で指定、省略時は下の優先順位で推定。

## 解決の優先順位

宛先ごとに、上から最初に合致した規則を使う:

1. **agent 個別の `transport:`**（最優先・強制）
2. **送り手 = Claude かつ宛先 = Claude → `sendmessage`**（native。held/refused 意味論と `notify_when_idle` がある）
3. **宛先 = Codex → `codex-queue`**（CLI なので誰でも送れる。queue で非同期）
4. **`defaults.transport`**（roster YAML トップレベル。native 経路を持たない宛先への fallback）
5. **それ以外 → `herdr`**（汎用。観測も兼ねる）

明示値 `transport: auto` は省略と同じく自動解決する — 規則 1 には合致せず規則 2 以降を辿る（「経路なし」を意味する `none` や `defaults:` と紛らわしい `default` とは別物）。`defaults.transport: auto` も同じく no-op（書かないのと同じ）として扱う。

### `defaults.transport` の効き方

- 規則 4 は規則 2・3 の native 推定より後に効く — **native 経路を持たない宛先にだけ適用される fallback**。書いても Claude 宛の sendmessage・Codex 宛の codex-queue 推定は潰れない
- fallback 先として実質意味を持つのは `herdr` のみ — 非 Claude 宛に `sendmessage`（Claude のツール）は送れず、非 Codex 宛に `codex-queue` の thread は解決しない
- Claude hub で `defaults.transport: herdr` と書くと「**Claude 宛は sendmessage、Codex 宛は codex-queue、それ以外は herdr**」のモードになる。Codex 宛にも herdr を使いたい場合は agent 個別に `transport: herdr` を書く（規則 1 で強制できる）

## `herdr`（既定・汎用）

```bash
herdr agent prompt <name> "<text>"            # 非同期（既定）
herdr agent prompt <name> "<text>" --wait --timeout 120000   # 同期照会のみ
```

- `agent prompt` は入力として受け手を起床させる。`--wait` は first settled state (`idle`/`done`/`blocked`) まで待つ
- 宛先は **live agent name** または pane ID。ターミナル ID・agent 種名は受け付けない
- エラー意味論:
  - `agent_blocked` — 宛先が承認/質問 UI で待っている。**送信は行われない**。`agent get` / `agent read` で UI を見てから人間に判断を仰ぐ
  - `agent_prompt_stalled` — 送信後 5 秒以内に `working`/`blocked` を観測できなかった。**未配送の証明ではない**。再送前に `agent read` で届いたか確認する
  - `timeout` — 呼び出し側 timeout 内に settled しなかった。未配送とは限らない
- `unknown` 状態は「agent がいるが分類不能」。**完了の証明ではない**
- `pane read` の罠: alternate screen 上の agent は host scrollback に残らず `--lines` を増やしても取れない。取れなければ受け手に「完全な応答をファイルに書いてパスだけ返せ」と依頼する
- 応答の読み取り: `herdr agent read <name> --source recent-unwrapped --lines 120`

## `sendmessage`（Claude → Claude）

形式: **Claude が `SendMessage` ツールを呼ぶ**（CLI ではない）。skill は「この宛先には SendMessage を使え」と Claude に指示する形になる。

- 要件: 両端とも Claude Code v2.1.224+（macOS/Linux）。同一マシン上のセッション登録ファイルを共有できることが前提（コンテナ・WSL 跨ぎは届かない）
- **held / refused 意味論**: 受け手の `crossSessionInbound`（`accept`/`hold`/`refuse`）が効く。未設定時は両者の permission mode の組で決まり、**受け手が bypass 系・送り手がプロンプト系だと held になり人間の承認待ち**になる。無人運用は `accept` 設定か mode の組を揃える
- **`notify_when_idle`**: 相手が次に idle/exit したとき 1 回通知を返す購読。`agent wait` で監視させる代わりにこれを使う
- 宛先名: `claude --name` / `/rename` のセッション名。herdr の agent name と**別体系**なので命名規約で揃える（[startup.md](startup.md)）
- 制約: サイズ上限・バースト上限あり、**自分宛は拒否**、同名複数セッションは識別子併記、メッセージはテキストのみ（文脈・ファイルは運ばない）
- 発見: `ListAgents`（または `/list-agents`）

## `codex-queue`（任意 → Codex）

```bash
codex queue --thread <SESSION_UUID or 厳密セッション名> --message "<text>"
```

- **CLI コマンド**なので送り手は codex でなくてよい — hub が Devin でも使える
- セッションの入力キューに積む。idle なら起床して新ターン、ターン中なら次の入力として待機（割り込まない）
- `--remote wss://host:port` で他マシンの app-server にも届く
- ⚠ **公式リファレンス未掲載**（0.149.0 で導入との報告あり。実機確認は codex-cli 0.154.0 の `--help`、2026-09-13）。将来の版で変わりうるので使用前に `codex queue --help` で確認する
- `--thread` は UUID か**厳密なセッション名**。命名規約で herdr agent name と揃える
