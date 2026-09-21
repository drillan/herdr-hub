# roster desired-state 化・rules 注入・B 層吸収 — 設計改訂

2026-09-21。`2026-09-13-herdr-hub-design.md` の改訂（差分を記す。本文の正典は SKILL.md / references）。

## 背景

mixseek-data-lake の `multi-session-hub` を**完全退役**させる方針が決まった（プロジェクト側の spec・skill 本体・参照を削除し、herdr-hub に置き換える）。退役に伴い 2 つの変更が要る:

1. **B 層の未移管分を吸収** — 初版 spec は A+B を引き継ぐとしていたが、突合で「裁定の境界」「裁定の質」「review 向け briefing 差分」等が未移管と判明
2. **C 層の差し込み口** — merge gate・worktree 等のプロジェクト固有規律は配布 skill に入れられないが、consumer 側 file を roster 経由で注入する機構があれば、プロジェクト側に非追跡 file として保持できる

## スコープ変更

初版 spec の「**正は既に live な agent の調整。skill が自動で編成・起動まで行うのは将来拡張**」を取り込み、**roster を desired state に格上げ**する:

- `agents:` は空を許容（hub 単独で起き、全部動的に足す運用を可能にする）
- **`kind` を起動対象のマーカーとする**（`herdr agent start --kind` に必須の値がちょうど「起動可能性」を表す）。live に無い + `kind` あり → 起動対象、live に無い + `kind` 無し → 即エラー（typo 検出を守る）
- **自動起動の前に hub が人間へ編成案を 1 行確認する** — agent の spawn は pane が増え briefing 受信でトークンを消費し始める環境への変更であり、無人での実行はしない

## schema 変更

```yaml
presets:                 # 新規。名前付きテンプレート（role / role_def / rules / kind / transport / placement / handoff_at）
  impl: { role: 実装, kind: claude, rules: [...] }

defaults:
  rules: [...]           # 新規。全 agent 共通の規律

agents:
  hub:     { role: 統括, rules: [.herdr-hub/merge-gate.md] }   # hub の rules は hub が起動時に読む
  worker1: { preset: impl }                                   # preset 参照（新規）
```

| 変更 | 内容 |
|---|---|
| `role_file` → **`role_def`** | clean rename。`role_file` を検出したら「`role_def` に改名してください」として即エラー（alias なし）。命名の曖昧さ（「role の file」が 2 通りに読める）の解消 |
| **`rules`** | string または list。`defaults.rules` + preset + 個別を **union（連結）** — 規律は共通＋役割固有＋個人固有の重ね合わせなので override しない。他フィールドの「個別が優先」と merge 規則が違う点は明記 |
| **`presets`** | 動的追加を 1 行（`{ preset: impl }`）に畳み、同 role の規律セットを 1 箇所に集約。未定義名の参照は即エラー |
| **`kind`** | 上記の通り起動対象マーカー |
| **解決順序** | `defaults` → `preset` → agent 個別。**defaults が与えられるのは `rules` / `transport` / `handoff_at` / `placement` のみ** — `role` / `role_def` / `preset` / `kind` は preset か個別指定に限る。defaults.kind を許すと typo 名が起動対象になり「kind 無し = typo 検出」が死ぬ。defaults.role も必須フィールド検証を潜り抜ける |

## rules の delivery（宛先で届け方が違う）

- **worker 向け**: briefing の境界ブロックへ**本文を改変せず全文を注入**（出所パスを併記）。パスだけ渡す形にしない — codex 等はその file を読まないため、注入が本経路。要約・抜粋もしない — 「file を編集すれば worker に届く」が rules の約束であり、黙って削ると両側に分からない（実測: 初回 dogfooding で hub が要約注入していた）
- **hub 向け**: hub が起動時に自分で読む（briefing を受け取る側ではないため注入先が無い）

schema 上は同一フィールド `rules` で、届け方だけが分かれる — `hub_rules` のような別フィールドは置かない。

## B 層の吸収（multi-session-hub から）

新設・拡充した references:

| file | 内容 |
|---|---|
| `references/escalation.md`（新設） | 裁定の境界（裁く/上げる）、不変条件 vs 手段、決断の要求は前提が動き終わってから、N 択に整形しない上げ方 |
| `references/adjudication.md`（新設） | 状態 vs 判定の観測分離、worker の主張を裁定に使う前の 1 問、hub 自身の出力を疑う、裁定は材料提供者全員へ戻す、指示・裁定の作法（逐語+裁定日・指示語で指さない・ついでに・4 段階） |
| `references/briefing.md` | review 担当への差分（SHA pin・非同期補助の申告・merge 通知で停止・期待値の事前登録）、worker 作法の細部（数値は逐語・観測と解釈分離・ref 併記・名指しの数は下限・全数走査）、rules 注入位置、8 ブロック版（途中参加） |
| `references/messaging.md` | 直列待ちを作らない、逆方向の作法、届いた事実を届いたタイミングで確認 |
| `references/context-and-handover.md` | 恒久性クラス（hosted / machine-local / 揮発）、共有メモリ writer は hub 単独、hub 交代の合図と 3 種の引き継ぎ、latest 系ポインタ |
| `references/failure-modes.md` | 汎用運用の失敗項目を追加（直列待ち・枠組み追認・hub 出力の未検算・ref mismatch・母集団切断・idle 未棚卸し・review SHA ずれ） |
| `references/roster.md` / `startup.md` | 本 spec の schema・3 分岐検証・動的追加・起動確認 |

C 層（merge gate・Copilot・worktree lock 等）は herdr-hub に入れない — consumer 側が `rules:` で参照する file（例: `.herdr-hub/*.md`）としてプロジェクトに保持する。git 管理外にしたい場合は `.git/info/exclude` 等で除外する。

## 検証

初版と同じく「実際の herdr セッションで hub + worker 1 名を立て、briefing → 指示 → 返信 → 着地まで一周させる」実演 + `rules` file が briefing に注入されること・`kind` 起動対象の 3 分岐が機能することを確認する。
