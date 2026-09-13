# roster（名簿）

hub が調整対象を知るための「名前 → 役割」の対応表。roster の**正は live の agent であり、YAML はその記述**であって逆ではない — ファイルに書いてあっても live に無い agent は存在しない。

## 与え方と優先順位

1. **起動引数**（最優先）: skill 起動プロンプトに `名前: 役割` をカンマ区切りで並べる

   ```
   reviewer: レビュー専任, advisor: 設計相談, worker1: 実装
   ```

2. **`--roster <path>`**: YAML を明示指定
3. **既定パス**: cwd の `.herdr-hub.yml`（存在しなければ引数指定のみで動く）

## YAML スキーマ

```yaml
defaults:                                # 全 agent の既定値（省略可。agent 個別の指定が優先）
  placement: tab
  # transport: herdr                     # sendmessage 適格でない宛先への fallback（詳細は transports.md の優先順位）
  # handoff_at: 0.8

agents:
  hub:      { role: 統括,        transport: sendmessage }
  reviewer: { role: レビュー専任 }                        # transport 省略時は既定推定
  worker1:  { role: 実装,        transport: herdr, handoff_at: 0.9, placement: pane }
```

テンプレートはこの skill 同梱の [.herdr-hub.yml.example](../.herdr-hub.yml.example) — 作業対象プロジェクトの cwd に `.herdr-hub.yml` としてコピーして使う。

| フィールド | 型 | 既定 | 意味 |
|---|---|---|---|
| `role` | string | （必須） | 役割の説明。briefing にそのまま使う |
| `transport` | `herdr` \| `sendmessage` \| `codex-queue` | [transports.md](transports.md) の既定推定 | この宛先への送信経路 |
| `handoff_at` | float (0–1) | `0.8` | 交代判定の使用率閾値（80% 使用で発火）。詳細は [context-and-handover.md](context-and-handover.md) |
| `placement` | `pane` \| `tab` | `tab` | 起動時の配置。少数を横に並べて監視したいなら `pane`（[startup.md](startup.md)） |

名前は `[a-z][a-z0-9_-]{0,31}`（herdr agent name の規約）に合わせる。命名規約全体（claude `--name`・codex session name との統一）は [startup.md](startup.md)。

## 起動時検証（必須）

roster を得たら、**全名前が live に解決することを確認する**:

```bash
herdr agent list   # .result.agents[].name（または pane_id）と roster の名前を照合
```

- **解決できない名前が 1 つでもあれば即座にエラー**として人間に報告する。黙ってスキップ・警告で続行しない
- **返信宛先 `hub` が live に解決することも確認する。** worker の返信経路は `herdr agent prompt hub` 固定のため、自分（呼び出し側）の herdr agent name が `hub` でないなら `herdr agent rename <self-pane> hub` で付けるか、briefing で返信先名を明示する。`sendmessage` 経路を使う場合は受け手の Claude セッション名（`claude --name` / `/rename`）も `hub` に揃える必要がある — `agent rename` が変えるのは herdr 名のみ
- 逆方向も見る: live だが roster に無い agent があれば、名簿の陳腐化として人間に確認する
- roster が古い・矛盾する場合の修復は人間の判断。hub が勝手に roster を書き換えない

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

生成物はあくまで雛形 — `role` を実際の役割に書き換えてから使う。

## 交代時の仮名

交代では前任生存中に後任を起動するため同名を取れない。後任は `<name>-next` の仮名で起動し、前任 exit 後に roster を後任へ付け替える。手順は [context-and-handover.md](context-and-handover.md)。
