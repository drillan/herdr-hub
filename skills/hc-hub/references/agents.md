# agents（エージェント固有の知識）

スキル本体はエージェント固有の分岐を持たない。どのエージェントで worker を起こすかは、roster の preset・個別エントリの `command`（argv の配列）か `template`（hc の template 名）のどちらか一方で選ぶ。両方ある・どちらも無い場合はエラー。

ここに書くのは、エージェントごとに違うこと。入力待ちに答えるキー、`blocked` を報告するか、必須の引数。この版で確かめたのは Claude Code だけ。当面は worker を Claude に統一しており、Codex は測っていない。

## 起動直後の検査

起動したら `hc wait <t> --timeout 60` で待つ（[startup.md](startup.md) の「起動後の確認」）。状態の知らせで返れば、エージェントは状態を報告している。timeout で返り `hc get` の状態が `null` のままなら `hc read` で画面を読み、確認のダイアログ（信頼の確認など。下の Claude Code の節）なら答える。ダイアログも状態の報告も無いエージェントは、承認待ちに気づけないので、人に知らせて止まる。

## Claude Code

hc 0.1.15 で確かめたこと。出所が実測でないものは、行末に（hc の手引き）・（spec）と書く。

- 状態（OSC 7501）を報告する。働いている間は `working`、ターンを終えると `done`（`working` は hc の手引き）
- 質問 UI（AskUserQuestion など）で止まると `blocked` を報告し、`hc wait <t>` は `{"reason":"status","status":"blocked",…}` で返る。親でない hub の `hc wait` も返る。親には `<hc>` のタグで通知が来る（通知は hc の手引き）
- `blocked` の子への `hc send <t> …` は exit 9（`kind: blocked`、`hint` は「画面を読め、または `--force`」）で拒否される
- 答え方は、先に `hc read <t>` で画面を読み、`hc keys <t> down enter` のようにキーを押すか、`hc send --force <t> "…"` で文字を送る。押す順序は、読んだ画面の選択肢の並びで決める（`hc keys` の形は hc の手引き。blocked の画面への押下は未実測）
- plan mode の承認もこの形で答える。範囲の確認は [approvals.md](approvals.md) に従う
- 信頼していない cwd で起こすと、起動直後に信頼の確認ダイアログ（`Is this a project you created or one you trust?`、選択肢 `No, exit` / `Yes, I trust this folder`）で止まる。このとき状態は `null` のままで、`blocked` の通知は来ず、`hc wait` も返らない。`hc read` で画面を見て初めて分かる。信頼済みの cwd で起こせば起きない。起きたら画面を読み、フォルダの信頼の確認として [approvals.md](approvals.md) の表に従って答える
- エージェント自身の権限モードは `command` の引数（`--permission-mode` など）で選ぶ。`approval:` とは独立（spec）

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

例（Herdr 1 の運用で知られていたことで、hc では未測定）: Devin は `--permission-mode` を省略すると auto で起き、tool の承認待ちで黙って停止する。`-- --permission-mode dangerous` を付けるとプロジェクトの deny list まで auto-approve する。deny を維持するなら hook 側で塞ぐ。
