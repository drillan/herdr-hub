# hc-hub spawn と ledger append --resolve（#8 の 2 点目）

## 1. 何のためか

いまは worker を 1 人起こすたびに、hub が次の 6 段を手で組む。`spawn-argv` をファイルに受けて終了コードを確かめる。`jq` と `xargs -0` で `hc` に渡す。応答から address を読む。起動を確かめる。`herdr-app ls` で tab id を引いて `tab.rename` する。`resolve` の `command` を `--command-json` に写して台帳に記録する。試運転では worker 4 人で 6 段を 4 回繰り返し、tab の名前付けを一度後回しにした。手で組むと段が抜けるので、機械的な段を CLI に移す。

「依頼が届いたと確認してから台帳に記録する」順序と、起動後の確認（信頼の確認に答える判断を含む）は hub の判断なので、CLI に入れない。

## 2. `hc-hub spawn`

```
hc-hub spawn --lane <L> (--preset <p> | --agent <名>) --name <名前> --cwd <絶対パス> \
  --task "<最初の依頼>" [--brief <path>] [--roster …] [--hc …] [--herdr-app …]
```

- 引数と検査は `spawn-argv` と同じ。`spawn-argv` が組む argv を、シェルを通さずに `hc` へ渡す（`jq`・`xargs` の段が要らなくなる。`hc` の終了コードも書き換わらない）
- `hc run` の応答の `address` を読む。文字列でなければエラー
- 配置が `tab` なら、`herdr-app ls` の `spaces[].tabs[].terminals[].terminal` から worker のアドレスを含む tab を探し、`herdr-app do tab.rename --id <tab id> --name <名前>` を打つ。起こした直後は `herdr-app ls` にまだ出ないことがあるので、0.5 秒おきに最大 10 回引き直し、尽きたらエラー。見つかった tab が 2 つ以上でもエラー
- 配置が `hidden` なら tab を扱わない
- `hc run` のあとに失敗したら（応答の解釈・tab の名前付け）、起こした worker を `hc kill` → `hc rm` で片付けてから、エラーで止まる。記録の無い worker を残さないため。片付けにも失敗したら、アドレスを添えてエラーにする
- 出力は JSON 1 行: `{"address", "name", "tab"（hidden なら null）, "command"（template なら null）, "template"（command なら null）}`
- 台帳には書かない。起動後の確認も行わない

`spawn-argv` は残す（ほかの起動の仕方を組む余地のため）。手順書の正規の手順は `spawn` にする。

## 3. `ledger append --resolve`

- `--resolve` を付けると、記録する `command` / `template` を roster から解決する。`--preset` があれば `resolve_worker(roster, lane, preset)`、無ければ常駐 agent として `resolve_resident(roster, lane, name)`（常駐 agent の名前は roster のエントリ名そのもの）
- `--resolve` と `--command-json`・`--template` は同時に使えない（argparse の排他）
- 解決の失敗は、ほかの検査と同じく終了コード 2 のエラー

## 4. 設計者の判断

- 引き直しの回数と間隔（0.5 秒 × 10 回）は試運転の観察からの見積もりで、実測ではない
- `hc run` の後の失敗で worker を CLI が片付けるのは、CLI が自分で起こした端末だからで、probe の端末と同じ扱い
- `--herdr-app` は `--hc` と同じく、テストと別の場所のバイナリのための指定（既定は `herdr-app`）
