# lanes（レーンと分離）

1 つの core の上で複数のレーンが並行して動く。レーンの分離は手順として守る規律であり、機構による遮断ではない。限界は末尾に書く。

## ラベル

分離の単位は space ID ではなくレーン名。space は作り直すと ID が変わるため。

| ラベル | 付ける相手 | 意味 |
|---|---|---|
| `hc-hub.lane=<レーン名>` | すべての hub・worker | 所属するレーン |
| `hc-hub.role=hub` | hub | レーンの hub |
| `hc-hub.role=<preset 名>` | `--preset` から起こした worker | 役割。常駐 agent（`--agent`）は preset を持っていても `hc-hub.role=<エントリ名>`。`hub` は hub 専用の予約語で、preset 名にも常駐 agent 名にも使えない |
| `hc-hub.brief=<依頼ファイルのパス>` | 依頼ファイルがある worker | 起動時の `--label` で付ける。値に `/` を含むパスを入れられる（実測） |
| `hc-hub.needs-human=1` | 人の判断を待つ worker | hub が付け外しする（[approvals.md](approvals.md)） |

- 子はラベルを継承しない。`hc run` のたびに `hc-hub.lane` と `hc-hub.role` を明示する
- `hc ls` の各行はラベル・名前・親を返さない。`hc ls --label hc-hub.lane=<レーン>` で候補を絞り、ラベル・`parent`・`state` は 1 件ずつ `hc get <t> --json` で読む
- `hc get` には、`hc-hub` 以外のラベル（`where` など）が後から付くことがある。`hc-hub.*` だけを見る
- hub がラベルを付けてよいのは、自分自身と、自分が起こした worker・引き継いだ worker だけ
- 人に見せるときのレーンと space の対応（例: space `backend` と `frontend`）は任意。hc-hub は space の存在に依存しない

## hub の起動

```bash
hc-hub start --lane <レーン名>
```

次の 3 つは CLI が行う。手で `hc label` を打って代えない。

- レーン名は起動引数で受け取る。省略した場合、または roster の `lanes:` に無い名前の場合はエラーで止まる
- 同じレーンに `hc-hub.role=hub` の live なターミナルがすでにあればエラーで止まる（1 レーンに hub は 1 人。手での交代でも例外は設けない）
- 自分のターミナル（`HC_TERMINAL_ID`）に `hc-hub.lane=<レーン>` と `hc-hub.role=hub` を付ける

hub のターミナルは人が起こすため名前が無いことがある。hc には起動後に名前を付ける操作が見当たらないので、hub はラベルとアドレスで識別する。

## 操作前のガード

宛先を取る hc の操作（`send`・`keys`・`interrupt`・`kill`・`rm`・`label`・`put`・`attach`・`wait <t>`・`read`・`keep` など、宛先を取るものすべて）を打つ前に、毎回これを打つ。

```bash
hc-hub guard --op <op> <t>
```

`<op>` は打つ hc のサブコマンド名で、`send`・`keys`・`interrupt`・`kill`・`rm`・`label`・`put`・`attach`・`wait`・`read`・`keep` のどれか。これ以外の名前は CLI が拒否する。CLI は自分と宛先のラベルを `hc get` で読み、自分にも宛先にも `hc-hub.lane` と `hc-hub.role` があることを確かめたうえで、次のどちらかに当たれば通す。

1. 宛先の `hc-hub.lane` が自分と同じ
2. 自分が hub で、宛先が `hc-hub.role=hub`（他レーンの hub）で、操作が `send` である

どちらにも当たらなければ非 0 で終わる。その場合は操作せず、エラーとして止まる。別の宛先や別の操作に切り替えて通さない。ラベルの無い宛先（`hc-hub.lane` か `hc-hub.role` が欠ける宛先）は、どのレーンのものとも扱わない。操作せず、必要なら人に上げる（[escalation.md](escalation.md)）。

`hc wait --children any` と `hc ls` のように、宛先を取らない操作にガードは要らない。

`hc --help` の宛先を取る操作（`attach`・`read`・`kill`・`rm`・`label`・`keep`・`send`・`keys`・`interrupt`・`wait`・`put`・`get`）のうち、`get` だけはガードの対象にしない。`get` は読むだけで、ガード自身が両者のラベルを読むために使う。

## 越境の規則

- 干渉は自分のレーン内に留める。他のレーンの worker には、読むことも含めて触れない
- hub 同士はレーンを越えて会話してよい。用途は限定しない（API の取り決めの擦り合わせなど）。手段は `hc send` だけ。他レーンの hub は自分の子ではないので、返事は相手の `hc send` として届く
- worker はレーンを越えない。worker が送るのは、briefing に書かれた hub のアドレスと、hub に指示された相手だけ。hub のアドレスは `<hc>` のタグに頼らず briefing に必ず書く（command 起動の依頼にはタグが付かない、実測）
- 別マシンを指す指定（`hc run --on` など）は使わない。roster に書かれていたらエラーにする。自分の継承コンテキストの外にある core へつなぐ使い方も同じ穴になる

## 通信経路

通信は `hc send` に一本化する。Herdr 1 の運用にあった `sendmessage`・`codex-queue` は持ち込まない。

- どちらもエージェントごとの経路で、エージェントを設定ファイルで選ぶ方針と合わない
- どちらもマシン全域で名前を解決し、レーンの分離をすり抜ける

## ガードの限界

ガードは hub が自分に課す規律であり、機構ではない。

- ラベルは誰でも `hc label` で書き換えられる自己申告。他の hub や worker の誤り・偽装は防げない
- worker が勝手に起こした子はラベルを持たない。hub はそれを自分のレーンのものとして扱えない
- ガードを打ち忘れた操作は検査されない。宛先を取る操作の直前に、毎回打つ

worker の briefing にも、この規律と、機構的な遮断ではないことを書く。
