# roster（名簿）

hub が調整対象を知るための「名前 → 役割」の対応表。roster の**正は編成の意図（desired state）**であり、live の agent はその記述に合わせて照合・起動される — live に無いが `kind` を持つエントリは「起動対象」である。

## 与え方と優先順位

1. **起動引数**（最優先）: skill 起動プロンプトに `名前: 役割` をカンマ区切りで並べる

   ```
   reviewer: レビュー専任, worker1: 実装
   ```

2. **`--roster <path>`**: YAML を明示指定
3. **既定パス**: cwd の `.herdr-hub.yml`（存在しなければ引数指定のみで動く）

起動引数では `role` の短いラベルしか渡せない。`role_def`・`rules`・`preset`・`kind` を使うなら **YAML 経路限定**。

## YAML スキーマ

```yaml
presets:                                 # 名前付きの設定テンプレート（省略可）
  impl:
    role: 実装
    role_def: roles/impl.md
    rules: [.herdr-hub/worker-rules.md]
    kind: claude
    placement: pane
    handoff_at: 0.9
  reviewer:
    role: レビュー専任
    kind: claude

defaults:                                # 全 agent の既定値（省略可。preset・agent 個別の指定が優先）
  rules: [.herdr-hub/common-boundary.md] # 全員共通の規律（rules は union。下記「rules の merge」参照）
  placement: tab
  # transport: herdr                     # native 経路を持たない宛先への fallback（詳細は transports.md の優先順位）
  # handoff_at: 0.8

agents:                                  # 空の map `{}` や省略も可 — hub 単独で起きて全部動的に足す運用
  hub:      { role: 統括, rules: [.herdr-hub/merge-gate.md] }
  worker1:  { preset: impl }             # preset の各フィールドを引き継ぐ
  worker2:  { preset: impl, placement: tab }  # 個別指定が preset を上書き
  reviewer: { preset: reviewer }
```

テンプレートはこの skill 同梱の [.herdr-hub.yml.example](../.herdr-hub.yml.example) — 作業対象プロジェクトの cwd に `.herdr-hub.yml` としてコピーして使う。

### agent 個別フィールド

| フィールド | 型 | 既定 | 意味 |
|---|---|---|---|
| `role` | string | （必須。preset が与えることも可） | 役割の説明（短いラベル）。briefing にそのまま使う |
| `role_def` | string（パス） | （なし） | 長文の役割定義 .md へのパス（roster YAML の dir 基準の相対）。worker には briefing の役割ブロックへ内容をそのまま注入、hub のものは hub が起動時に読む |
| `rules` | string または list（パス） | （なし） | その agent が従う規律 file（群）。delivery は宛先で分かれる — 下記「rules の delivery」 |
| `preset` | string | （なし） | `presets:` のキー名。未定義の名前は即エラー |
| `kind` | string | （なし） | `herdr agent start --kind` の値。**live に無いとき起動対象になるマーカー**（下記「起動時検証」） |
| `transport` | `herdr` \| `sendmessage` \| `codex-queue` \| `auto` | `auto` | この宛先への送信経路。`auto` は省略と同じ自動解決の明示値（[transports.md](transports.md) の優先順位） |
| `handoff_at` | float (0–1) | `0.8` | 交代判定の使用率閾値（80% 使用で発火）。詳細は [context-and-handover.md](context-and-handover.md) |
| `placement` | `pane` \| `tab` | `tab` | 起動時の配置。少数を横に並べて監視したいなら `pane`（[startup.md](startup.md)） |

**解決順序**: `defaults` → `preset` → agent 個別（個別が最優先）。ただし **defaults が与えられるのは `rules` / `transport` / `handoff_at` / `placement` のみ** — `role` / `role_def` / `preset` / `kind` は preset または agent 個別の指定に限る。defaults で `role` を許すと必須フィールド検証を潜り抜け、`kind` を許すと typo した名前まで起動対象になって「`kind` 無し = typo 検出」（下記「起動時検証」）が死ぬ。preset 内では `transport` / `handoff_at` / `placement` / `rules` / `role` / `role_def` / `kind` が使え、個別指定が preset を上書きする。`rules` だけは例外 — 下記。

### rules の merge（union）

`rules` だけは上書きでなく **union（連結）** する — 規律は「共通＋役割固有＋個人固有」の重ね合わせなので、個別指定が共通を潰すと境界が消える。`defaults.rules` + `preset の rules` + `agent の rules` をこの順で連結したものが最終セット。重複するパスは 1 度だけ適用する。

⚠ 他フィールドの「個別が優先」と merge 規則が違う — 混同しない。

### rules の delivery（宛先で届け方が違う）

| 宛先 | delivery |
|---|---|
| **worker** | briefing の境界ブロックへ**本文を注入**する。file パスも併記して再読み可能にする（[briefing.md](briefing.md)） |
| **hub** | **hub が起動時に自分で読む**。briefing を受け取る側ではないので注入先が無い |

⚠ **worker に file のパスだけを渡して済ませない** — 注入が本経路であり、パスは再読み用の補助。worker がそのパスを読まなくても規律は届いている状態にする。

### role_def（旧 role_file）

`role_file` は **`role_def` に改名された**。`role_file` を指定したエントリがあれば「`role_def` に改名してください」として即エラー — 別名として黙って読まない。

## 起動時検証（必須）

roster を得たら、各エントリを 3 分岐で処理する:

| 状態 | 扱い |
|---|---|
| live に解決できる（`herdr agent list` の名前と一致） | そのまま |
| live に無い + **`kind` が解決できる**（個別指定 or preset 経由） | **起動対象** — 手順は [startup.md](startup.md)。起動後に live 解決を再確認する |
| live に無い + `kind` 無し | **即座にエラー**。黙ってスキップ・警告で続行しない |

⚠ **`kind` 無しの未解決を起動対象にしない** — `kind` の不在は「起動方法が書かれていない」= 名前の typo か陳腐化の可能性であり、黙って起動すると「間違った名前の agent が spawn する」形になる。typo の検出を守るため、この分岐は厳密に。

あわせて確認する:

- **`preset` 参照が `presets:` で定義されていること** — 未定義名は即エラー
- **`role_def` / `rules` で参照される file がすべて存在し読めること**（preset・defaults 経由で解決された分も含む）。不在・不可読は即エラー
- **返信宛先 `hub` が live に解決すること。** worker の返信経路は `herdr agent prompt hub` 固定のため、自分（呼び出し側）の herdr agent name が `hub` でないなら `herdr agent rename <self-pane> hub` で付けるか、briefing で返信先名を明示する。`sendmessage` 経路を使う場合は受け手の Claude セッション名（`claude --name` / `/rename`）も `hub` に揃える必要がある — `agent rename` が変えるのは herdr 名のみ
- 逆方向も見る: live だが roster に無い agent があれば、名簿の陳腐化として人間に確認する
- roster が古い・矛盾する場合の修復は人間の判断。hub が勝手に roster を書き換えない（**動的追加の追記は例外 — 下記**）

## 動的追加（稼働中に agent を足す）

roster の正は編成の意図なので、追加は **YAML への追記**として扱う:

1. `worker3: { preset: impl }` のようにエントリを追記（preset が `kind` を持てば起動情報まで揃う）
2. 起動時検証と同じ 3 分岐をそのエントリに適用 — `kind` が解決できるなら起動、無ければエラー
3. briefing を送る — **稼働途中の参加なので「現在の状態」ブロックを含む 8 ブロック版**を使う（[briefing.md](briefing.md) の交代時と同じ形）

⛔ **追記せずに live にだけ追加しない** — roster に無い agent は次回の検証で「陳腐化」として浮く。

## export（現在の配置から雛形を作る）

```bash
herdr tab list --workspace "$HERDR_WORKSPACE_ID"   # tab_id ↔ label
herdr agent list                                  # name ↔ pane_id ↔ tab_id
```

2 つの JSON を突合し、各 agent の tab label を `role` の初期値にした YAML 雛形を生成する:

```bash
# agent の tab_id と tab label を join して role の初期値にする
python3 - <<'PY'
import json, subprocess
agents = json.loads(subprocess.check_output(["herdr","agent","list"]))["result"]["agents"]
tabs = {t["tab_id"]: t["label"] for t in json.loads(
    subprocess.check_output(["herdr","tab","list","--workspace",subprocess.run(
        ["printenv","HERDR_WORKSPACE_ID"],capture_output=True,text=True).stdout.strip()]))["result"]["tabs"]}
print("agents:")
for a in agents:
    print(f"  {a['name']}: {{ role: {tabs.get(a.get('tab_id'),'TODO')} }}")
PY
```

生成物はあくまで雛形 — `role` を実際の役割に書き換え、`preset` / `rules` / `kind` を必要に応じて足してから使う。

## 交代時の仮名

交代では前任生存中に後任を起動するため同名を取れない。後任は `<name>-next` の仮名で起動し、前任 exit 後に roster を後任へ付け替える。手順は [context-and-handover.md](context-and-handover.md)。
