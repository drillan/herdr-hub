# hc-session の設計

2026-11-11。herdr-core（`hc`）向けに、`herdr-session` の capture/restore に当たる配布 skill `hc-session` を `skills/hc-session/` に追加する。

## 背景

- 2026-11-11 11:42 の PC の再起動で、hc の端末の中の Claude Code がすべて終わった。端末は `state: live` のまま残り、address・名前・ラベル（`hc-hub.*` を含む）も残った。中のプログラムは keep の回復でシェル（fish）に置き換わった
- Claude Code の会話の記録（`~/.claude/projects/…/<session id>.jsonl`）も残るので、同じ端末で `claude --resume <id>` を打てば続きから再開できる。足りないのは「どの端末でどのセッションが動いていたか」の記録だけ
- hc-hub の設計（2026-10-31）は「herdr-core では再起動でプログラムが消えるため、名前を付け直す対象がない」として `herdr-session` に当たるものを作らなかった。端末が残るので、付け直す対象（端末）はある。この判断を改める

## 決めたこと（人の選択）

- 置き場所: hc-hub から独立した skill。hc-hub を使わない端末も対象にする
- capture: Claude Code の `SessionStart` hook で自動に記録する。capture の打ち忘れや突然の電源断でも restore できるようにする
- restore: 対象は Claude Code だけ。`status` で対応を見てから `restore` で送る

## 記録（`hc-session record`）

`SessionStart` hook から呼ぶ。標準入力の JSON（`session_id`・`transcript_path`・`cwd`）を読み、自分の端末に次のラベルを付ける。

| ラベル | 値 |
|---|---|
| `claude.session` | セッション ID（UUID） |
| `claude.cwd` | セッションを始めたディレクトリ（`--resume` はここで打つ） |
| `claude.transcript` | 会話の記録のパス（restore 前に存在を確かめる） |
| `claude.at` | 記録した時刻（epoch ミリ秒） |

- ラベルは再起動でも残る（2026-11-11 に実測）。`/clear`・`--resume` でも `SessionStart` が走り、上書きされる
- `HC_TERMINAL_ID` が無い（hc の外の Claude）ときは何もせず終了コード 0。対象が存在しないだけで、失敗ではない
- **端末の前面の Claude だけを記録する**。hook を起動した最も近い祖先の `claude` プロセスの pid と、`hc get` の `foreground.pid` が一致するときだけ書く。端末の中の Claude が `claude -p` を子として起こしても、そのセッションで上書きしない
- 標準出力には何も書かない（`SessionStart` hook の標準出力は Claude の文脈に入る）。理由は標準エラーへ
- 入力の欠落・`hc` の失敗・祖先に `claude` が無いときは終了コード 1

## 判定（`hc-session status`）

`hc ls` の live な端末のうち `claude.session` ラベルを持つものを、次の順で判定する。

| 印 | 条件 | restore の扱い |
|---|---|---|
| `[running]` | 前面にプログラムがある（`foreground.pid` ≠ 端末の `pid`）、または端末の最初のプロセスが `claude`（hc-hub spawn の worker） | 送らない |
| `[exited]` | 前面がシェルで、シェルの起動が `claude.at` 以前 | 送らない（そのシェルの中で Claude が普通に終わった） |
| `[missing]` | 前面がシェルで、シェルの起動が `claude.at` より後、かつ記録のファイルが無い | 送らずにエラー |
| `[restore]` | 前面がシェルで、シェルの起動が `claude.at` より後 | 送る |
| `[duplicate]` | 同じ `claude.session` を持つ live な端末が他にもある（上の判定より優先） | 送らずにエラー |

- 「シェルの起動が `claude.at` より後」は、Claude が動いていた後でシェルが立ち上がった（keep の回復でシェルに置き換わった）ことを表す。再起動のほか、同じ起動の中で Claude がシグナルで死んだ場合も含む
- シェルの起動時刻は `/proc/<pid>/stat` の starttime と `/proc/stat` の btime から求める。hc の端末は同じマシンの同じ PID 名前空間で動く（2026-11-11 に確認）
- ラベルが欠けている・値が不正（UUID でない、時刻が整数でない）端末は `[invalid]`、`hc get` に pid か `foreground.pid` が無い端末は `[unknown]` として示す。起動直後の端末は `foreground` が null のことがある（2026-11-11 に実測）。どちらも他の端末の判定は続ける
- `[missing]`・`[invalid]`・`[unknown]`・`[duplicate]` があれば終了コード 1

## 再開（`hc-session restore [--dry-run] [<端末>...]`）

- `[restore]` の端末に `hc send <t> "cd <cwd> && claude --resume <id>"` を送る。`<cwd>` はシェル向けに引用する。起動時のフラグは引き継がない（roster の `command` が `claude` だけの運用を前提にする）
- 端末を指定したときは、その端末だけを対象にする。指定した端末が `[restore]` でなければエラー
- `[missing]`・`[invalid]`・`[unknown]`・`[duplicate]` があれば、それらには送らず名前を挙げて終了コード 1
- `--dry-run` は送るコマンドを表示するだけ

## 範囲外

- Codex など Claude Code 以外のエージェント
- keep の無い端末（再起動で `finished` になり、送る先が無い）。hc-hub spawn の worker と Herdr app の端末は keep が付いている（2026-11-11 に `hc get` で確認）
- 端末を作り直すこと。端末は残る前提

## 入れ替わりの検出（2026-11-11 追記）

- 再起動の後、hub のセッションが worker の端末で再開し、worker のセッションはどこでも動かなかった（ytscribe レーン、11-06 と 11-11 の 2 回）。worker の端末で `claude -c` を打つと、同じディレクトリの最新のセッション（hub のもの）が開くためと推測している
- hook はどちらの端末にも同じ `claude.session` を記録するので、同じ値が 2 つの live な端末にあれば `[duplicate]` とし、どちらにも送らない
- hc-hub の `start` と `preflight` も、自分の端末が worker の端末（hub 以外の `hc-hub.role`）であるか、自分の `claude.session` が別の live な端末にもあれば止まる
