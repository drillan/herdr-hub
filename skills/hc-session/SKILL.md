---
name: hc-session
description: herdr-core（`hc`）の端末で動いていた Claude Code のセッションを、PC の再起動などで消えた後に同じ端末で再開する。SessionStart hook が端末ごとのセッションをラベルに記録し、status で確認、restore で `claude --resume` を送る。「再起動でエージェントのセッションが消えた」「hc の端末の Claude を復元して」「Herdr app で再起動後に hub や worker を戻したい」で起動。HC_TERMINAL_ID の端末から使う。旧来の herdr には herdr-session を使う。
license: MIT
---

# hc-session

herdr-core では、PC の再起動で端末の中の Claude Code は終わるが、端末（address・名前・ラベル）は残り、中身は keep の回復でシェルに置き換わる。会話の記録も残るので、**どの端末でどのセッションが動いていたか**さえ分かれば、同じ端末で `claude --resume` を打って再開できる。この skill はその対応を記録し、再開を送る。

## §0 前提

- hc の端末の中から使う（`HC_TERMINAL_ID` がある）。依存は `hc` と `uv` のみ
- 端末に keep が付いていること（`hc get <t> --json` の `keep: true`）。keep の無い端末は再起動で `finished` になり、送る先が残らない
- 対象は Claude Code だけ。起動時のフラグは引き継がず、`claude --resume <id>` で再開する

## §1 記録の hook を入れる（一度だけ）

`~/.claude/settings.json` の `hooks` に次を足す。この skill は設定を書き換えない。人に見せて、人の承認を得てから足す。

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "\"$HOME/.claude/skills/hc-session/scripts/hc-session\" record" }
        ]
      }
    ]
  }
}
```

- Claude Code が起動・`/clear`・`--resume` するたびに、自分の端末へラベル `claude.session`・`claude.cwd`・`claude.transcript`・`claude.at` を付ける。ラベルは再起動でも残る
- hc の外の Claude では何もしない。端末の前面でない Claude（前面の Claude が子として起こした `claude -p` など）は記録しない
- hook を入れる前から動いている Claude は記録されていない。その端末は Claude の中で `/clear` するか、記録の無いまま手で `claude --resume` する

## §2 コマンド

実体は [scripts/hc-session](scripts/hc-session)。

```bash
hc-session status                      # 端末ごとの判定を表示する（送らない）
hc-session restore --dry-run [<t>...]  # 送るコマンドを表示する
hc-session restore [<t>...]            # 再開できる端末に claude --resume を送る
```

| 印 | 意味 | restore |
|---|---|---|
| `[restore]` | 前面がシェルで、そのシェルは Claude の記録より後に立ち上がった（再起動・シグナルでの終了の後の回復） | `cd <cwd> && claude --resume <id>` を送る |
| `[running]` | 前面でプログラムが動いている | 送らない |
| `[exited]` | 前面がシェルで、そのシェルの中で Claude が普通に終わった | 送らない |
| `[missing]` | `[restore]` の条件に合うが、会話の記録のファイルが無い | 送らずにエラー |
| `[invalid]` | ラベルが欠けているか値が不正 | 送らずにエラー |
| `[unknown]` | `hc get` に pid か `foreground.pid` が無い（起動直後の端末） | 送らずにエラー |

`[missing]`・`[invalid]`・`[unknown]` があると、終了コードは 1。端末を指定すると、その端末だけを対象にし、`[restore]` でない端末を指定したらエラー。

## §3 再起動の後の手順

1. `hc-session status` で対応を見て、人に示す
2. 人の承認を得てから `hc-session restore` を打つ
3. hc-hub の hub を再開したら、背景の `hc wait --children any` は消えているので張り直す。worker の依頼に期限があれば、過ぎていないかを hub が確かめてから続けさせる
