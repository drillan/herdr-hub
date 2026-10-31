# agents（エージェント固有の知識）

スキル本体はエージェント固有の分岐を持たない。どのエージェントで worker を起こすかは、roster の preset・個別エントリの `command`（argv の配列）か `template`（hc の template 名）のどちらか一方で選ぶ。両方ある・どちらも無い場合はエラー。

ここに書くのは、エージェントごとに違うこと。入力待ちに答えるキー、`blocked` を報告するか、必須の引数。確かめたのは Claude Code と opencode（対話の画面の起動のみ）。当面は worker を Claude に統一しており、Codex は測っていない。

**`command` は core から見つかる必要がある。** hc の core の PATH は、hub のシェルの PATH と違うことがある（実測: `~/.opencode/bin` の opencode は hub のシェルから見えたが、core からは見えなかった）。core から見つからないと `hc run` が `spawn_failed: cannot start "<コマンド>"` で失敗する。`hc-hub validate` と `hc-hub spawn-argv` はこの不一致を検出できない。直し方は 2 つ。roster の `command` の先頭を絶対パスにするか、core の PATH にそのディレクトリを入れる（[failure-modes.md](failure-modes.md)）。

**`status` はオブジェクト。** `hc get --json` の `status` は `{"app":…,"msg":…,"state":"working"}` の形で、状態は `.status.state` で読む。`turn` は最初のターンが終わるまで 0 で、それが正常。状態を報告しない（`.status` が `null`）という結論は、待ってから 1 回見た値では出さず、間を置いた複数回の観測で出す（試運転では、60 秒待った後の 1 回の観測で「報告しない」と誤判定した）。

## 起動直後の検査

起動したら `hc wait <t> --timeout 60` で待つ（[startup.md](startup.md) の「起動後の確認」）。状態の知らせで返れば、エージェントは状態を報告している。timeout で返ったら `hc get <t> --json` の `.status.state` を見て、`null`（`.status` ごと `null` の場合を含む）のままなら `hc read` で画面を読み、確認のダイアログ（信頼の確認など。下の Claude Code の節）なら答える。ダイアログも無く状態が `null` のままでも、1 回の観測では結論にしない。間を置いて複数回観測してから、状態を報告しないエージェントとみなす。ダイアログも状態の報告も無いエージェントは、承認待ちに気づけないので、人に知らせて止まる。

## Claude Code

hc 0.1.15 で確かめたこと。出所が実測でないものは、行末に（hc の手引き）・（spec）と書く。

- 状態（OSC 7501）を報告する。働いている間は `working`、ターンを終えると `done`（`working` は hc の手引き）
- 質問 UI（AskUserQuestion など）で止まると `blocked` を報告し、`hc wait <t>` は `{"reason":"status","status":"blocked",…}` で返る。親でない hub の `hc wait` も返る。親には `<hc>` のタグで通知が来る（通知は hc の手引き）
- `blocked` の子への `hc send <t> …` は exit 9（`kind: blocked`、`hint` は「画面を読め、または `--force`」）で拒否される
- 答え方は、先に `hc read <t>` で画面を読み、`hc keys <t> down enter` のようにキーを押すか、`hc send --force <t> "…"` で文字を送る。押す順序は、読んだ画面の選択肢の並びで決める（`hc keys` の形は hc の手引き。blocked の画面への押下は未実測）
- plan mode の承認もこの形で答える。範囲の確認は [approvals.md](approvals.md) に従う
- 信頼していない cwd で起こすと、起動直後に信頼の確認ダイアログ（`Is this a project you created or one you trust?`、選択肢 `No, exit` / `Yes, I trust this folder`）が出ることがある。出ると状態は `null` のままで、`blocked` の通知は来ず、`hc wait` も返らない。`hc read` で画面を見て初めて分かる。一方、新しく作った worktree で起こした Claude Code に、ダイアログが出なかった実測もある（2026-10-31。理由は未確認で、親ディレクトリが信頼済みだった可能性がある）。出るかどうかは起こすまで分からないので、起動直後は毎回疑う（[startup.md](startup.md)）
- ダイアログが出たら画面を読み、フォルダーを確かめる。hub 自身が worker のために作った worktree のフォルダーなら、hub が `Yes, I trust this folder` を選んでよい。それ以外のフォルダーは人に上げる（needs-human。[approvals.md](approvals.md) の表と「設定に残る選択肢は選ばない」の例外）
- エージェント自身の権限モードは `command` の引数（`--permission-mode` など）で選ぶ。`approval:` とは独立（spec）

## opencode

opencode v2.2.5 で確かめたこと（2026-10-31。対話の画面の起動だけで、`blocked` への答え方は未測定）。

- 対話の画面（TUI）は hc に状態を報告する（`status.app` が `opencode`）
- 最初の依頼は `--prompt "<依頼>"` で渡す。位置引数はディレクトリとして解釈される。roster の `command` は `[opencode, --prompt]` とし、`--task` の値（依頼の文字列）が `--prompt` の直後に付く
- `sh -c "opencode run … | tee"` のように包んで起こすと、agent は `sh` として見え、`.status` は `null` のままになる。状態を報告させるには、包まずに起こす
- `opencode` が core の PATH に無いと起動できない。上の「`command` は core から見つかる必要がある」に従う

## Codex

この版では測っていない。分かっているのは hc の手引き（`hc --skill`）に書かれた次の 1 点だけ。

- `--no-daemon` を付けて起こす。付けないと、コマンドが hc の外で実行される

`blocked` などの状態を報告するか、入力待ちに答えるキーは未測定。使うことにした時点で、使い捨てのターミナルで測ってからここに書く。測るまでは、起動直後の検査で状態の報告が無ければ人に知らせて止まる。

## 他のエージェントを足すとき

利用者が自分で書き足す。この節の形に揃える。

1. `command`（または `template`）に、そのエージェントを `hc run` で起こす argv を書く。必須の引数（Codex の `--no-daemon` のような固有の起動引数）はここに入れる
2. 使い捨てのターミナルで起こし、`hc get` で状態を報告するかを確かめる。報告しなければ、承認待ちに気づけないので hub の運用には使えない
3. 入力待ちを起こして `blocked` になるかを確かめ、`hc read` で画面を読み、どのキー・文字で答えられるかを書き残す
4. 信頼の確認のように、状態が `null` のまま止まる画面が無いかを、未信頼の cwd で起こして確かめる
5. この節に、測った日・hc のバージョンとともに、見出しを 1 つ立てて書く。測っていないことは「未測定」と書く

例（旧来の `herdr` の運用で知られていたことで、hc では未測定）: Devin は `--permission-mode` を省略すると auto で起き、tool の承認待ちで黙って停止する。`-- --permission-mode dangerous` を付けるとプロジェクトの deny list まで auto-approve する。deny を維持するなら hook 側で塞ぐ。
