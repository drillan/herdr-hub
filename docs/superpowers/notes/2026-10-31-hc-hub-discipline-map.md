# herdr-hub の規律を hc-hub へ移す対応表

2026-10-31。spec 4.8 の対応表。書き直す 6 つの references（`context-and-handover`・`briefing`・`messaging`・`startup`・`failure-modes`・`roster`）と、それに付随する `transports` および `SKILL.md` の規律を、1 つも黙って落とさないための表。Task 5〜8 はこの表を正として書く。

- `区分`: `そのまま`（規律の文をそのまま引き継ぐ）/ `変える`（規律は残し、旧来の `herdr` の仕組みに依存する部分だけを hc に差し替える）/ `捨てる`（旧来の `herdr` の仕組みそのもの。理由を書く）
- `置き場所`: 書き直し後の `skills/hc-hub/` 内のファイル。共有の 3 references（`adjudication`・`escalation`・`worktrees`）には置かない（複製と同一性の検査で内容が固定されるため。`worktrees` は 2026-10-31 に共有をやめ、hc-hub に固有の規則を持つ）
- `検査語`: 置き場所のファイルに逐語で入れる語句（6〜20 文字）。執筆者はその行の規律を書くときにこの語句を本文に入れる
- `出所`: `<元ファイル> / <見出し> / <太字の箇条や小見出し>`。元ファイルの略称は `SKILL`=`skills/herdr-hub/SKILL.md`、他は `skills/herdr-hub/references/<名>.md`

| ID | 出所 | 規律の要約 | 区分 | 置き場所 | 検査語 | 捨てる理由 |
|---|---|---|---|---|---|---|
| D001 | SKILL §0 前提 | 構成: 最初に環境を確認し、失敗したら管理下ではないと報告して停止する | 変える | SKILL.md | HC_TERMINAL_ID | - |
| D002 | SKILL §0 / この skill を読むのは hub だけ | skill を読むのは hub だけで、worker は読まない。briefing が作法の担保になる | そのまま | SKILL.md | skill を読むのは hub だけ | - |
| D003 | SKILL §0 / 人間は hub にだけ話し、hub が全 worker へ配る | 人間が話すのは hub だけで、worker から人間への直接経路を作らない | そのまま | SKILL.md | 人間は hub にだけ話し | - |
| D004 | SKILL §0 / CLI 構文の正典はインストール済みバイナリ | 構文の正典はインストール済みの hc。§0 で毎回 hc --skill を読ませ、画面を触るときだけ herdr-app --skill | 変える | SKILL.md | hc --skill | - |
| D005 | SKILL §1 roster（名簿） | 起動時に roster を得る。YAML は --roster で指定し、既定は repo 直下の .hc-hub.yml | 変える | SKILL.md | .hc-hub.yml | - |
| D006 | SKILL §1 / 起動引数 名前: 役割 | 起動引数で「名前: 役割」を並べる経路は、hub の起動引数でレーン名を受け取る形に変える。省略・未定義のレーン名はエラー | 変える | SKILL.md | レーン名は起動引数で受け取る | - |
| D007 | SKILL §1 / roster は編成の意図（desired state） | roster は編成の意図（desired state）。常駐 agent が空でもよい（hub 単独で起き、後から動的に足す） | 変える | SKILL.md | desired state | - |
| D008 | SKILL §1 / **live に解決できる** | 起動時検証の分岐 1: live に解決できるエントリはそのまま | そのまま | SKILL.md | live に解決できる | - |
| D009 | SKILL §1 / **live に無い + `kind` が解決できる** | 分岐 2: live に無く command か template が解決できるものは起動対象。人間への編成案の確認は外し、hub が人の承認を求めずに起こす | 変える | SKILL.md | 人の承認を求めずに起こす | - |
| D010 | SKILL §1 / **live に無い + `kind` 無し** | 分岐 3: live に無く起動方法も無いエントリは即エラー。黙ってスキップ・警告で続行しない（typo 検出を守る） | 変える | SKILL.md | 即座にエラー | - |
| D011 | SKILL §1 / presets・defaults・個別の参照先 role_def・rules file の検証 | 参照先の role_def と rules の file が存在し読めることを起動時に確認する。不在・不可読は即エラー。hub の rules と role_def は hub 自身が読み、worker 向けは briefing へ注入する | そのまま | SKILL.md | 不在・不可読は即エラー | - |
| D012 | SKILL §2 transport（通信経路） | transport 3 種（herdr・sendmessage・codex-queue）の宛先別の自動解決と defaults.transport | 捨てる | - | - | 通信経路は hc send に一本化する（spec 4.3）。sendmessage・codex-queue は旧来の `herdr` のエージェントごとの経路で、マシン全域で名前を解決するためレーンの分離をすり抜ける |
| D013 | SKILL §3 通信プロトコル（骨子） | 通信は hc send に一本化する | 変える | SKILL.md | hc send に一本化 | - |
| D014 | SKILL §3 / **通常送信は非同期** | 通常の送信は非同期。送って即答が要る同期照会だけが例外で、普通の指示・裁定は投げたら送信側のターンを終える | 変える | SKILL.md | 送信側のターンを終える | - |
| D015 | SKILL §3 / **返信は hub 宛** | worker は hub のアドレスへ hc send で返信する。worker がこの手段を知るのは briefing だけなので、briefing に自分の名前・roster・hub のアドレスを必ず書く | 変える | SKILL.md | hub のアドレスを必ず書く | - |
| D016 | SKILL §3 / **送信前 guard** | 送信前に宛先を確認する。宛先が自分のレーンのものであることを hc-hub guard で確かめてから送る | 変える | SKILL.md | hc-hub guard | - |
| D017 | SKILL §3 / **監視禁止** | worker や hub に他の worker を監視させない（hc wait で張り付かせない）（hub 自身の hc wait --children any は除く）。Claude 間の notify_when_idle は持ち込まない | 変える | SKILL.md | 他の worker を監視させない | - |
| D018 | SKILL §4 規律（骨子） | 規律の骨子の節 | そのまま | SKILL.md | 規律（骨子） | - |
| D019 | SKILL §4 / **hub は実装しない** | hub は実装しない。裁定と実装を分ける（検査は自分が書く側に回ると発動しない） | そのまま | SKILL.md | hub は実装しない | - |
| D020 | SKILL §4 / **hub が推奨を出すときは「これは私の裁定であり人間の決定ではない」と明記する** | 推奨には「これは私の裁定であり人間の決定ではない」と明記する | そのまま | SKILL.md | 私の裁定であり人間の決定ではない | - |
| D021 | SKILL §4 / **承認済み成果物・測定値は worker → worker 直送可** | 承認済みの成果物・測定値は worker から worker へ直送してよい。判断・裁定・新規の指摘は hub 経由 | そのまま | SKILL.md | 判断・裁定・新規の指摘は hub 経由 | - |
| D022 | SKILL §4 / **指摘は 1 便に合流させる** | 指摘は 1 便に合流させる（源が非同期に届くため）。blocker だけ例外 | そのまま | SKILL.md | 指摘は 1 便に合流させる | - |
| D023 | SKILL §4 / **ack を求めない。訂正は次便に相乗りさせる** | ack を求めない。訂正は次便に相乗りさせる | そのまま | SKILL.md | 訂正は次便に相乗り | - |
| D024 | SKILL §4 / **照会には終了条件を先に書く** | 照会には終了条件を先に書く。往復が伸びたら成果物ではなく自分が渡した前提を疑う | そのまま | SKILL.md | 自分が渡した前提を疑う | - |
| D025 | SKILL §4 / **中継は情報を落とす** | 中継は情報を落とす。件数・集合の再掲を添える | そのまま | SKILL.md | 件数・集合の再掲 | - |
| D026 | SKILL §4 / **着地したら終える** | 着地したら終える。「終了です」通知も送らない（例外は走行中の review を止める「停止」1 行） | そのまま | SKILL.md | 着地したら終える | - |
| D027 | SKILL §4 / **context 使用率は実測でのみ書く** | context 使用率は実測でのみ書く。worker に定期申告させない | そのまま | SKILL.md | 実測でのみ書く | - |
| D028 | SKILL §4 / **裁定の境界を先に引く** | 裁くものと人間へ上げるものを先に分ける。正典（spec・ADR）が矛盾・不在なら自分の原理で解かずに上げる | そのまま | SKILL.md | 裁定の境界を先に引く | - |
| D029 | SKILL §4 / **hub は不変条件を裁き、手段は worker が決める** | hub は不変条件を裁き、手段は worker が決める（手段の裁定は実測でしか決まらない） | そのまま | SKILL.md | 手段は worker が決める | - |
| D030 | SKILL §4 / **裁定に worker の数値・分類を引く前に 1 問訊く** | 裁定に worker の数値・分類を引く前に「何を測った値か」「baseline は」と 1 問訊く。hub 自身の出力を疑い、worker に「私の裁定を壊しにきてください」と招く | そのまま | SKILL.md | 私の裁定を壊しにきてください | - |
| D031 | SKILL §4 / **状態の観測を重複させない** | 状態の観測を重複させない（CI の緑/赤等は 1 箇所だけが測る）。判定（主張の真偽）は独立に取り直す。こちらの重複は価値である | そのまま | SKILL.md | 状態の観測を重複させない | - |
| D032 | SKILL §4 / **review 役を置くなら、その出力を裏取りする経路を置く** | review 役を置くなら出力を裏取りする経路を置く（hub が一次資料で読み直す / review 役に読んだ file の列挙を課す） | そのまま | SKILL.md | 出力を裏取りする経路 | - |
| D033 | SKILL §4 / **裁定は材料を出した全セッションへ戻す** | 裁定は材料を出した全セッションへ戻す。戻すのは裁定した側の義務 | そのまま | SKILL.md | 材料を出した全セッション | - |
| D034 | SKILL §4 / **新しい agent を起動する前に `agent list` で idle を棚卸しし、「既存で足りないか」を問う** | 新しい worker を起こす前に、同じレーンの idle を hc ls --label と hc get で棚卸しし「既存で足りないか」を問う | 変える | SKILL.md | 既存で足りないか | - |
| D035 | SKILL §5 worker の起動 | 起動の手順（配置・起動・命名）は startup の reference が持つ。稼働中の追加は同じ検証・起動経路を通す | 変える | SKILL.md | startup.md | - |
| D036 | SKILL §6 context 残量と交代 | context 残量の観測と交代の節。手順の正典は context-and-handover の reference | そのまま | SKILL.md | context 残量と交代 | - |
| D037 | SKILL §6 / **観測は `agent read` / `pane read` の `--source visible` で外側から** | 観測は hc read で外側から画面を読み、worker の文脈を消費しない | 変える | SKILL.md | worker の文脈を消費しない | - |
| D038 | SKILL §6 / 処置は 続行 / compact / 交代 の 3 択。**80% で交代判定** | 処置は続行・compact・交代の 3 択。80% で交代判定し、auto-compact を検出したら即交代 | そのまま | SKILL.md | 80% で交代判定 | - |
| D039 | SKILL §6 / 交代は **前任が内容ブロックを後任へ直接送る** | 交代では前任が内容ブロックを後任へ直接送り、hub はエンベロープを書く | そのまま | SKILL.md | hub はエンベロープを書く | - |
| D040 | context ## 観測 | context 残量の観測の節 | そのまま | references/context-and-handover.md | context 残量の観測 | - |
| D041 | context 観測 / **第一は pane を外側から読む** | 第一は画面を外側から hc read で読む。worker の文脈を消費しない（agent read と pane read の 2 本立ては hc read に一本化） | 変える | references/context-and-handover.md | 外側から hc read | - |
| D042 | context 観測 / **Devin CLI（実測済み）** | Devin CLI は footer に使用率が常時描画される（Context: 127k / 262k tokens (48%)、2026-09-13 に旧来の `herdr` の実機で確認）。hc read で同じ値が読める前提で、hc 上では未再測定と明記する | 変える | references/context-and-handover.md | 127k / 262k tokens | - |
| D043 | context 観測 / **Claude / Codex は要実機確認** | Claude と Codex は常時表示が無い・読めないときの代替手段として、クライアント側 slash コマンド（Claude /context、Codex /status）を打ち込んで描画を読む。モデルの文脈を消費しない。読み終えたら hc keys で esc を送って閉じる | 変える | references/context-and-handover.md | /context | - |
| D044 | context 観測 / **それでも取れない agent kind はオンデマンド申告のみ** | それでも取れないエージェントはオンデマンド申告のみ。定期申告は禁止（往復自体が文脈を消費し、欄は捏造を招いた）。訊くときは hub が名指しし実測値の行ごと貼らせる | そのまま | references/context-and-handover.md | 定期申告は禁止 | - |
| D045 | context ## 処置の 3 択（判断は hub） | 処置の 3 択（続行・compact・交代）の判断は hub。compact は名前・roster・briefing が存続するので最も安い。「いま失って困るのは土地勘か独立性か」で選ぶ | そのまま | references/context-and-handover.md | 土地勘か独立性か | - |
| D046 | context ## 交代の手順 | 交代の手順の節 | そのまま | references/context-and-handover.md | ## 交代の手順 | - |
| D047 | context 交代の手順 / **使用率 `handoff_at`（既定 80% = 80% 使用）で交代判定** | 使用率 handoff_at（既定 80%）で交代判定する。roster で個別に上書きできる | そのまま | references/context-and-handover.md | handoff_at | - |
| D048 | context 交代の手順 / 閾値は使用率であり残量ではない | 閾値は使用率であり残量ではない。メーターの使用率をそのまま handoff_at と比べる | そのまま | references/context-and-handover.md | 使用率であり残量ではない | - |
| D049 | context 交代の手順 / auto-compact 済みを検出したら閾値無視で即交代 | auto-compact 済みを検出したら閾値を無視して即交代する（要約済み記憶から書く handoff は二次記述で劣る）。検出は hc read で、メーターの急落か compaction 通知行を見る | 変える | references/context-and-handover.md | 閾値を無視して即交代 | - |
| D050 | context 交代の手順 / 閾値は handoff を書くのに十分な残量が残っているうちに置く | 閾値は handoff を書くのに十分な残量が残るうちに置く。遅らせると handoff 品質のリスクを取る（交代コストの支配項は後任の再暖機で発火時期に依存しない） | そのまま | references/context-and-handover.md | 十分な残量が残るうち | - |
| D051 | context 交代の手順 / 前任生存中に後任を仮名で起動（実装で `<元の名前の短縮>-h<連番>` に確定。-next の連結はやめた） | 前任が生きている間に後任を仮名 <name>-next で起動する（名前は core 全体で一意のため同名を取れない） | そのまま | references/context-and-handover.md | -h<連番> | - |
| D052 | context 交代の手順 / briefing の内容ブロックは前任が後任へ直接送る | briefing の内容ブロックは前任が後任へ直接送る。前任が現在の状態・最初の一手・既知の罠を、hub が宛先 guard・役割・作法・境界・進め方を書く | そのまま | references/context-and-handover.md | 前任が後任へ直接送る | - |
| D053 | context 交代の手順 / 送信は roster と同じ transport 推定で | 送信は roster と同じ transport 推定で行う | 捨てる | - | - | transport の自動推定は旧来の `herdr` の仕組み。送信は hc send に一本化（spec 4.3） |
| D054 | context 交代の手順 / 前任 exit → 名の整理 | 前任の exit 後に名の整理を行う。正名を取るか、仮名のまま運用して台帳の記録を付け替えるか、どちらか一方は必ず行う（hc に端末の名前を変える操作が無いため、実装で仮名のまま運用に一本化） | 変える | references/context-and-handover.md | 仮名のまま運用する | - |
| D055 | context 交代の手順 / `agent rename` が変えるのは agent 名のみ | agent rename と pane rename・tab rename による正名の付け替え、pane ラベル・tab ラベルが追従しない問題 | 捨てる | - | - | 旧来の `herdr` の agent rename と pane・tab ラベルの仕組みそのもの。hc には起動後に名前を付ける操作が見当たらない（spec 4.3） |
| D056 | context ## 発火時コストを常時化して潰す | 発火時のコストを常時の記録で減らす節 | そのまま | references/context-and-handover.md | 発火時のコスト | - |
| D057 | context 発火時コスト / worker は進捗・判断・罠を log へ随時追記 | worker は進捗・判断・罠をログ file へ随時追記する（briefing の作法に含める）。置き場は hc-hub の名前空間に変える | 変える | references/context-and-handover.md | 随時追記する | - |
| D058 | context 発火時コスト / handoff は「ログのパス + 差分のひとこと」 | handoff は「ログのパス + 差分のひとこと」で済ませる。発火時の生成コストを 0 に近づけ、高い閾値でも書き切れるようにする | そのまま | references/context-and-handover.md | ログのパス + 差分のひとこと | - |
| D059 | context 発火時コスト / 揮発知識を随時ファイルへ逃がす | 揮発知識を随時ファイルへ逃がす。「引き継ぐものが無ければ handoff は不要」が成立する状態を保つ | そのまま | references/context-and-handover.md | 揮発知識を随時ファイルへ | - |
| D060 | context 発火時コスト / **試して駄目だったことを厚く残す** | 試して駄目だったことを厚く残す。成功手順は後任も発見するが、死に筋は書かないと同じ場所で時間を燃やす | そのまま | references/context-and-handover.md | 試して駄目だったことを厚く | - |
| D061 | context ## 恒久性クラス（何が生き残るか） | 情報の置き場を生存期間で分ける。恒久（hosted）・machine-local・揮発の 3 クラス。machine-local の例は hc-hub のログ・台帳・.hc-hub/ に変える | 変える | references/context-and-handover.md | machine-local | - |
| D062 | context 恒久性クラス / ⛔ **裁定・決定を揮発・machine-local のままにしない** | 裁定・決定を揮発層や machine-local のままにしない。届くべき相手が読める恒久層へ、逐語と裁定日で置く | そのまま | references/context-and-handover.md | 読める恒久層へ置く | - |
| D063 | context 恒久性クラス / **共有メモリ（複数 agent が読む置き場）の writer は hub 単独にする** | 共有メモリの writer は hub 単独にする。worker は自分のログを書き、共有置き場への転記は hub が行う | そのまま | references/context-and-handover.md | writer は hub 単独 | - |
| D064 | context ## hub 自身の交代 | hub 自身の交代の節。手での交代で、前任が引き継ぎを書いてから終了し、後任が起動する | 変える | references/context-and-handover.md | hub 自身の交代 | - |
| D065 | context hub 自身の交代 / **交代の合図** | 交代の合図は 3 つ。handoff_at 閾値、auto-compact 検出、フェーズの変化（閾値に依らず検討する。旧 hub が残ると新規判断と旧裁定の経緯が混ざる） | そのまま | references/context-and-handover.md | フェーズの変化 | - |
| D066 | context hub 自身の交代 / `.herdr-hub.yml` の **roster ファイルが新規 hub セッションの再開資材になる** | roster ファイルが新しい hub セッションの再開資材になる。後任は hc-hub start でレーン名を渡して起動する | 変える | references/context-and-handover.md | hc-hub start | - |
| D067 | context hub 自身の交代 / 新 hub は roster 検証で全 worker を再認識し「hub 交代の告知」を送る | 後任は台帳と照らして worker を再認識し、引き継いだ worker の全員へ自分のアドレスを新しい返信先として hc send で必ず知らせる | 変える | references/context-and-handover.md | 新しい返信先 | - |
| D068 | context hub 自身の交代 / 旧 hub は 3 種の引き継ぎを残す | 旧 hub は退く前に 3 種の引き継ぎを残す。裁定の経緯、却下した案、worker ごとの癖 | そのまま | references/context-and-handover.md | worker ごとの癖 | - |
| D069 | context hub 自身の交代 / 出所ラベル（旧 hub の判断である旨）を添える | 引き継ぎには出所ラベル（旧 hub の判断である旨）を添える。二次記述なので、無いと正典と同じ重みで読まれる | そのまま | references/context-and-handover.md | 出所ラベルを添える | - |
| D070 | context hub 自身の交代 / **引き継ぎの形は handoff file に限らない** | 引き継ぎの形は handoff file に限らない。恒久層から読めるものがほとんどなら新 hub への 1 便で足りる（揮発分が 5〜7 件程度の実績）。揮発分が多いときだけ file を介する | そのまま | references/context-and-handover.md | 揮発分が多いときだけ file | - |
| D071 | context ## 共有可変ポインタ（latest 系）の扱い | latest・current のような共有で可変なポインタは複数 writer で壊れる。file は絶対パス・固定 SHA で渡し、latest 系の更新は 1 箇所だけが行う | そのまま | references/context-and-handover.md | latest 系ポインタ | - |
| D072 | briefing ## 7 ブロック | briefing は 7 ブロックをこの順で書く（宛先 guard・役割と一元化・最初の一手・既知の罠・作法・境界・進め方） | そのまま | references/briefing.md | 7 ブロック | - |
| D073 | briefing 7 ブロック / 1. 宛先 guard | 宛先 guard: 「このメッセージは worker <名前> 宛です。あなたの名前が違うなら着手せず hub へ返信してください」。宛先はヘッダではなく名前とアドレスで示す | 変える | references/briefing.md | あなたの名前が違うなら | - |
| D074 | briefing 7 ブロック / 2. 役割と一元化 | 役割と一元化: roster 上の役割、指示は hub からのみ、人間への直接の質問はしない。role_def があれば hub がファイル内容を役割ブロックへそのまま注入する | そのまま | references/briefing.md | 指示は hub からのみ | - |
| D075 | briefing 7 ブロック / **担当の「外側」を書く** | 担当の「外側」を書く。何が含まれず、どこへ送られるか。送り先が書かれていない分割は「落ちた」のか「送った」のか区別できない | そのまま | references/briefing.md | 担当の「外側」を書く | - |
| D076 | briefing 7 ブロック / 3. 最初の一手（着手前に止まる） | 最初の一手: 何を・どこから始めるか。着手前に一度止まる、を既定にする | そのまま | references/briefing.md | 着手前に一度止まる | - |
| D077 | briefing 7 ブロック / 3. 最初の一手（節名・絶対パス） | 資料は節名で指す（行番号ポインタは腐る）。file は latest のような共有可変ポインタでなく絶対パスで渡す | そのまま | references/briefing.md | 資料を指すときは節名で | - |
| D078 | briefing 7 ブロック / 4. 既知の罠（必ず埋める） | 既知の罠は必ず埋める（最も効くブロック）。1 件ずつ「何が起きるか → なぜ検出できないか → どうするか」で書く | そのまま | references/briefing.md | 何が起きるか → なぜ検出できないか | - |
| D079 | briefing 7 ブロック / 4. 既知の罠（確認していない） | 誰も確認していない箇所は「確認していない」と明示する | そのまま | references/briefing.md | 「確認していない」と明示 | - |
| D080 | briefing 7 ブロック / 6. 境界 | 境界: やってよいこと・止まる条件。roster の rules（全段の union）があれば、各 file の本文を改変せず全文を注入し、出所パスを併記する。要約・抜粋・言い換えをしない。role に無関係な行も残す | そのまま | references/briefing.md | 本文を改変せず全文を注入 | - |
| D081 | briefing 7 ブロック / 7. 進め方 | 進め方: 報告の粒度・区切り・終了条件。一気に進めさせず、区切りごとに報告させる。担当の大きさを数字で伝える | そのまま | references/briefing.md | 一気に進めさせない | - |
| D082 | briefing ## worker の作法（⑤ に含めるもの） | 作法ブロックに含めるものの節 | そのまま | references/briefing.md | 作法ブロックに含める | - |
| D083 | briefing 作法 / **あなたの名前は `<name>`** | 作法に自分の名前を書く。返信・報告は hc send <hub のアドレス> で hub へ | 変える | references/briefing.md | あなたの名前は | - |
| D084 | briefing 作法 / roster 上の他 agent の名前と役割 | 同じレーンの他 agent の名前と役割を書く（誰に何を直送してよいかの判断材料） | 変える | references/briefing.md | 誰に何を直送してよいか | - |
| D085 | briefing 作法 / **進捗・判断・罠は `/tmp/herdr-hub/<name>.log` へ随時追記する** | 進捗・判断・罠はログ file へ随時追記させる（交代時の handoff はこれへの参照になる） | 変える | references/briefing.md | 随時追記する | - |
| D086 | briefing 作法 / **他 agent を `herdr agent wait` 等で監視しない** | 他の worker を hc wait 等で監視しない。待つべきものがあるときは「何を待っているか」を 1 行で hub へ投げてターンを終える | 変える | references/briefing.md | 何を待っているか | - |
| D087 | briefing 作法 / **新しい作業（issue・別タスク化）を自分で発行しない** | 新しい作業（issue・別タスク化）を自分で発行しない。「候補」として hub へ上げる | そのまま | references/briefing.md | 候補として hub へ上げる | - |
| D088 | briefing 作法 / **承認 UI で止まったときはそのまま待つ** | 承認 UI で止まったときはそのまま待つ。hub 側には blocked として見え、hub が approval の範囲で答える | 変える | references/briefing.md | そのまま待つ | - |
| D089 | briefing 作法 / 判断・裁定が必要に見えたら hub へ上げる | 判断・裁定が必要に見えたら hub へ上げる。自分の権限を越える決定をしない | そのまま | references/briefing.md | 権限を越える決定をしない | - |
| D090 | briefing 作法 / **hub へ問い合わせるときの作法** | hub へ問い合わせるときの作法（宛先の名指し・「決断が要る」の標識・裁定の着手確認・待ち方）を briefing に含める | そのまま | references/briefing.md | 問い合わせの作法 | - |
| D091 | briefing ### 報告の作法 | 報告の作法の節。報告の形は ① 結論 → ② 次のアクション → ③ 理由・裏取り | そのまま | references/briefing.md | 次のアクション | - |
| D092 | briefing 報告の作法 / **数値は実行出力の逐語のみ** | 数値は実行出力の逐語のみ。推測を書かない。数値が 1 つでも入るなら本文を書く前に全部測る。「編集の結果」を主張する文も編集後にその場で照会して出力を貼る | そのまま | references/briefing.md | 実行出力の逐語 | - |
| D093 | briefing 報告の作法 / **観測と解釈を分けて報告する** | 観測と解釈を分けて報告する | そのまま | references/briefing.md | 観測と解釈を分けて | - |
| D094 | briefing 報告の作法 / **`file:line` を書くときは ref（branch・commit）を明示する** | file:line を書くときは ref（branch・commit）を明示する。同時刻でも branch が違えば行番号が違う | そのまま | references/briefing.md | 行番号が違う | - |
| D095 | briefing 報告の作法 / **hub が渡した数値・区分・列挙はすべて未検証の入力として扱い、取り直してよい** | hub が渡した数値・区分・列挙はすべて未検証の入力として扱い、取り直してよい（むしろそうする） | そのまま | references/briefing.md | 未検証の入力として扱い | - |
| D096 | briefing 報告の作法 / **状態の数値を報告の主題にしない** | 状態（CI の緑/赤・失敗件数・進捗・使用率）の数値を報告の主題にしない。作者と CI が既に観測している。判定（主張の真偽）は独立に取り直す | そのまま | references/briefing.md | 状態の数値を報告の主題にしない | - |
| D097 | briefing 報告の作法 / 🔴 **context 使用率を「報告のたびに添える」欄を作らない** | context 使用率を報告のたびに添える欄を作らない（測らずに埋める圧力になり、捏造の実害があった）。停止条件は hub が持ち、必要なときに hub が名指しで訊く | そのまま | references/briefing.md | 報告のたびに添える欄 | - |
| D098 | briefing 報告の作法 / **hub が名指しした箇所の数は下限である** | hub が名指しした箇所の数は下限である。決定単位で全数走査し、名指しされていない箇所も直す。指示外を直したときは報告で明示する | そのまま | references/briefing.md | 名指しした箇所の数は下限 | - |
| D099 | briefing ## 「裁定」の明記 | hub が自分の推奨を送るときは「これは私の裁定であり人間の決定ではない」と本文に明記する | そのまま | references/briefing.md | 私の裁定であり人間の決定ではない | - |
| D100 | briefing 「裁定」の明記 / 人間の決定を転送するときは決定文を逐語で添える | 人間の決定を転送するときは決定文を逐語で添える。「承認済みの認識です」は転送ではない | そのまま | references/briefing.md | 決定文を逐語で添える | - |
| D101 | briefing ## review 担当への差分 | review を担う worker には最終ブロック（進め方）の前に追加する節 | そのまま | references/briefing.md | review 担当への差分 | - |
| D102 | briefing review / **対象を SHA で固定する** | 対象を SHA で固定する。head と base を渡し（head は着手時に取り直す）、review した SHA を報告に書かせる | そのまま | references/briefing.md | 対象を SHA で固定 | - |
| D103 | briefing review / **既に照会済みの範囲を書く** | 既に照会済みの範囲を書く（再指摘を減らす）。「あなたが最初の目です」ならそう書く | そのまま | references/briefing.md | 既に照会済みの範囲 | - |
| D104 | briefing review / **1 人目の reviewer が走行中に 2 人目を振るときは…** | 1 人目の reviewer が走行中に 2 人目を振るときは、先に 1 人目の「読んでいない file」を確認してから割る。軸の宣言ではなく未読範囲の実測で分ける | そのまま | references/briefing.md | 読んでいない file | - |
| D105 | briefing review / **「非同期に走っている補助作業…」を報告に必ず書かせる** | 非同期に走っている補助作業（追送・追加の確認）はあるか、を報告に必ず書かせる | そのまま | references/briefing.md | 非同期に走っている補助作業 | - |
| D106 | briefing review / **hub が下した裁定は、そう明示して「遠慮なく壊してください」と招く** | hub が下した裁定は明示して「遠慮なく壊してください」と招く。独立性が落ちる軸（材料が自分で渡したもの等）は先に申告させる | そのまま | references/briefing.md | 遠慮なく壊してください | - |
| D107 | briefing review / **挙げた観点に狭く当てさせない** | 挙げた観点に狭く当てさせない。「それ以外に見つけたものも出してください」を必ず書き、主張を出発点にせず全文を先に読んでから突き合わせさせる | そのまま | references/briefing.md | 挙げた観点に狭く当てさせない | - |
| D108 | briefing review / **定常観点に「実装の作用範囲…が正典の定義と一致するか」を含める** | 定常観点に「実装の作用範囲（対象集合・段）が正典の定義と一致するか」を含める。「導出元と一致するか」だけでは導出元が正典の集合かは測れない | そのまま | references/briefing.md | 実装の作用範囲 | - |
| D109 | briefing review / **期待値の事前登録** | 期待値の事前登録。review が修正前の baseline を実測してから修正を依頼し、「after が変化した」で効果を張る | そのまま | references/briefing.md | 期待値の事前登録 | - |
| D110 | briefing review / **複数巡になる review で…「直し方の方向」の各項も処置対象と明記する** | 複数巡の review で所見を実装側へ渡すときは、「直し方の方向」の各項も処置対象と明記する | そのまま | references/briefing.md | 直し方の方向 | - |
| D111 | briefing review / **完了・merge の通知が来たら、その対象への review 活動を止める** | 完了・merge の通知が来たら、その対象への review 活動を止める（並行起動した追走も）。例外は既に取り込まれた変更が壊す欠陥を見つけたときだけ | そのまま | references/briefing.md | review 活動を止める | - |
| D112 | briefing review / **ファイルを編集しない** | review 担当はファイルを編集しない（報告まで）。push しない・PR を作らない・merge しない | そのまま | references/briefing.md | PR を作らない | - |
| D113 | briefing ### 「測らない」ことを依頼文へ固定文で注入する / ## テストと CI は測らない（固定文） | 「測らない」を依頼文へ固定文で注入する。固定文「テストと CI は測らない」を依頼文・依頼 file にそのまま入れる | そのまま | references/briefing.md | テストと CI は測らない | - |
| D114 | briefing 測らない / **`<log の path>` は path だけを書く** | log の path は path だけを書く。hub が件数・pass 数を転記しない（測らずに埋める欄になる）。無ければ「無し」と書き、空欄にしない | そのまま | references/briefing.md | path だけを書く | - |
| D115 | briefing 測らない / ⚠ 免除されるのは「測ること」であって「読むこと」ではない | 免除されるのは「測ること」であって「読むこと」ではない。test が主張を識別できるかは reviewer の判定対象のまま | そのまま | references/briefing.md | 免除されるのは「測ること」 | - |
| D116 | briefing ### review thread の一次判断は worker（hub は却下の検算） | review thread の一次判断は worker が持ち、hub は却下の検算をする | そのまま | references/briefing.md | hub は却下の検算 | - |
| D117 | briefing review thread / **採用する指摘はそのまま直す** | 採用する指摘はそのまま直し、hub へ上げない。却下だけ全数走査の根拠つきで報告し、hub の検算を経てから閉じる | そのまま | references/briefing.md | 全数走査の根拠つき | - |
| D118 | briefing review thread / **返信で終わりにせず resolve まで打つ** | 返信で終わりにせず resolve まで打つ。resolve の前に何をしたか（修正 commit / 却下の根拠）を返信で残す | そのまま | references/briefing.md | resolve まで打つ | - |
| D119 | briefing review thread / **報告には `total N / unresolved M` を母集団ごと添える** | 報告には total N / unresolved M を母集団ごと添える。unresolved が 0 だけでは「解決済み」と「thread が 1 本も無い」を区別できない | そのまま | references/briefing.md | unresolved M | - |
| D120 | briefing ## 交代時・途中参加の分担 | 交代では briefing を 2 人で書く。hub が宛先 guard・役割・作法・境界・進め方、前任が現在の状態・最初の一手・既知の罠（落とした本人が最も詳しく、hub 中継は情報を落とす） | そのまま | references/briefing.md | 落とした本人が最も詳しく | - |
| D121 | briefing 交代時・途中参加 / 8 ブロック版 | 交代時と、稼働途中に動的追加された agent への briefing は、最初の一手の直前に「現在の状態」を挿入した 8 ブロック版を使う | そのまま | references/briefing.md | 8 ブロック版 | - |
| D122 | briefing 交代時・途中参加 / 前任が送る内容を書き換えない | 前任が送る内容を hub は検査してよいが、書き換えて自分の文にしない（中継の圧縮で本体が落ちる） | そのまま | references/briefing.md | 書き換えて自分の文にしない | - |
| D123 | messaging ## 送信 | 送信の作法の節。hc send に共通の作法を書く | そのまま | references/messaging.md | hc send 共通の作法 | - |
| D124 | messaging 送信 / **非同期が既定** | 非同期が既定。同期の待機は「送って即答が要る」照会だけに使い、普通の指示・裁定は投げたら送信側のターンを終える | 変える | references/messaging.md | 非同期が既定 | - |
| D125 | messaging 送信 / **送信前 guard** | 送信前に宛先を確認する。hc-hub guard でレーンを確かめる。「宛先が実在するか」だけでは足りず、実在確認を通って別人に届く | 変える | references/messaging.md | 実在確認を通って別人に届く | - |
| D126 | messaging 送信 / **本文中で他 agent を指すときも名前を併記する** | 本文中で他 agent を指すときも名前を併記する（guard が守るのは宛先だけで本文内の言及は守らない） | そのまま | references/messaging.md | 名前を併記する | - |
| D127 | messaging ## 返信 | 返信の作法の節。worker から hub へは hc send | 変える | references/messaging.md | hc send | - |
| D128 | messaging 返信 / briefing に「あなたの名前」「roster」「返信は hub 宛」を必ず書く | worker が返信経路を知るのは briefing だけなので、briefing に名前・roster・返信は hub 宛を必ず書く | そのまま | references/briefing.md | 返信は hub 宛 | - |
| D129 | messaging 返信 / **個別の依頼文にも返答経路（手段と宛先名）を明記する** | 個別の依頼文にも返答経路（手段と宛先名）を明記する。画面にだけ答えて送信を打たない失敗形があり、宛先が idle かつ自分に未着なら待たず hc read でその画面を読む | 変える | references/messaging.md | 個別の依頼文にも返答経路 | - |
| D130 | messaging 返信 / **判断・裁定・新規の指摘は hub 経由を維持する** | 承認済みの成果物・測定値は worker → worker 直送でよい。判断・裁定・新規の指摘は hub 経由を維持する | そのまま | references/messaging.md | hub 経由を維持する | - |
| D131 | messaging ## 待機・監視 | 待機と監視の節 | そのまま | references/messaging.md | 待機と監視の作法 | - |
| D132 | messaging 待機 / 🔴 **`herdr agent wait` で他者を監視する指示を出さない** | 他者を hc wait で監視する指示を出さない。ターンを終えた agent は何もせず、wait を回す agent は自分の文脈を監視に浪費する（hub 自身の hc wait --children any は除く） | 変える | references/messaging.md | 監視する指示を出さない | - |
| D133 | messaging 待機 / それ以外は「終わったらこちらへ報告せよ」を briefing/指示に書く | 終わったら報告させる指示を briefing や依頼に書く。起こすのは受け手であり、hc の親への自動通知（<hc> の通知）がそれを担う | 変える | references/messaging.md | 起こすのは受け手 | - |
| D134 | messaging 待機 / Claude 間では SendMessage の `notify_when_idle` を使う | Claude 間の SendMessage notify_when_idle による idle 通知の購読 | 捨てる | - | - | SendMessage は旧来の `herdr` のエージェントごとの経路。hc では親への自動通知と hc wait --children any が担う（spec 4.2・4.3） |
| D135 | messaging 待機 / 🔴 **「追います」「完了まで待ちます」を書かせない** | 「追います」「完了まで待ちます」を書かせない（worker にも hub 自身にも）。書くのは「いま何を区切ったか」と「次に誰が動くか」だけ | そのまま | references/messaging.md | 完了まで待ちます | - |
| D136 | messaging ## 完了の回収（SendMessage を持たない宛先） / **依頼文の末尾に完了合図の定型を書く** | SendMessage を持たない宛先の完了回収: 依頼文の末尾に完了合図の定型（herdr agent prompt hub で pane ID を添えて送る）を書かせる。回答の途中や todo の一項目として打たせない | 捨てる | - | - | 完了合図の定型は旧来の `herdr` で SendMessage を持たない宛先を補う仕組み。hc は子のターン終了を親へ自動で通知する（spec 4.2） |
| D137 | messaging 完了の回収 / 合図は「pane を読め」の合図 | 合図は「画面を読め」の合図であって完了の証拠ではない。状態が idle・done であることを確かめてから hc read で回収する（working なら背景で待つ） | 変える | references/messaging.md | 完了の証拠ではない | - |
| D138 | messaging 完了の回収 / 打ち忘れは起きる | 通知は取りこぼされうる。wait の戻り値だけで完了を数えず、返るたびに hc ls と hc get で全 worker の状態を取り直す | 変える | references/messaging.md | 状態を取り直す | - |
| D139 | messaging 完了の回収 / ⚠ hub 側を `agent wait` で張り付かせる形は、ターン終了で待機プロセスが死ぬので効かない | hub が wait で張り付く形は、ターンを終えると待機プロセスが死ぬので効かない。hc wait が同じ性質かは hc では未測定のため、断定せず注意として残す | 変える | references/messaging.md | 待機プロセス | - |
| D140 | messaging ## 中継は情報を落とす | hub の中継は圧縮の工程であり、受け手は「来なかったもの」を観測できない | そのまま | references/messaging.md | 来なかったもの | - |
| D141 | messaging 中継 / 列挙の一部が落ちる | 列挙の一部が落ちる型: 指示に「N 件のうち M」と集合を再掲する | そのまま | references/messaging.md | N 件のうち M | - |
| D142 | messaging 中継 / 参照だけ渡して本体が落ちる | 参照だけ渡して本体が落ちる型: 本文を同梱するか、「本人から直送させる」と明記する | そのまま | references/messaging.md | 本人から直送させる | - |
| D143 | messaging 中継 / 数えずに数を書く | 数えずに数を書く型: 行ごとの内訳を書いてから合計する | そのまま | references/messaging.md | 行ごとの内訳を書いてから合計 | - |
| D144 | messaging 中継 / 多義語を渡す | 多義語を渡す型: 状態は「生存 / 停止中 / 終了」等の限定語彙で書く | そのまま | references/messaging.md | 限定語彙で書く | - |
| D145 | messaging 中継 / **送信のたびに通し番号と総通数を添えさせる** | 送信のたびに通し番号と総通数を添えさせる（(a)(b)(c)… +「本便まで N 通」）。未達 1 通はこれだけで検出できる | そのまま | references/messaging.md | 通し番号と総通数 | - |
| D146 | messaging 中継 / **訂正・追補は「前便が生きているか」を 1 行目に書かせる** | 訂正・追補は「前便が生きているか」を 1 行目に書かせる | そのまま | references/messaging.md | 前便が生きているか | - |
| D147 | messaging 中継 / **worker に「私が渡した数値・区分は取り直せ」を毎回書く** | worker に「私が渡した数値・区分は取り直せ」を毎回書く | そのまま | references/messaging.md | 私が渡した数値・区分は取り直せ | - |
| D148 | messaging ## 往復を減らす | 往復を減らす節 | そのまま | references/messaging.md | 往復を減らす | - |
| D149 | messaging 往復を減らす / **ack を求めない** | ack を求めない。「待機します」は決定を運ばない。次の指示まで待機が既定 | そのまま | references/messaging.md | 「待機します」は決定を運ばない | - |
| D150 | messaging 往復を減らす / **訂正は次便に相乗りさせる** | 訂正は次便に相乗りさせる。単独で出すのは前便の結論が覆るときだけ | そのまま | references/messaging.md | 前便の結論が覆るときだけ | - |
| D151 | messaging 往復を減らす / **指摘は 1 便に合流させる** | 指摘は 1 便に合流させる。源が非同期に届くので、届いた順に流すと受け手は同じ対象を何度も直す。blocker だけ例外 | そのまま | references/messaging.md | 届いた順に流すと | - |
| D152 | messaging 往復を減らす / **照会には終了条件を始める前に書く** | 照会には終了条件を始める前に書く。巡回中に作った終了条件は gate の自己裁定。往復が伸びたら自分が渡した前提を疑う | そのまま | references/messaging.md | 巡回中に作った終了条件 | - |
| D153 | messaging ## 直列待ちを作らない | 複数の判定が open なとき、順に処理すると後ろの待ちが構造化される | そのまま | references/messaging.md | 直列待ちを作らない | - |
| D154 | messaging 直列待ち / **裁定には「誰が・いつ着手するか」を書く** | 裁定には「誰が・いつ着手するか」を書く。明示しないと worker は黙って「直ちに差し戻す」を選ぶ | そのまま | references/messaging.md | 誰が・いつ着手するか | - |
| D155 | messaging 直列待ち / **hub が判定できるものは hub が閉じる** | hub が判定できるものは hub が閉じる。未解決点ごとに hub / reviewer / worker へ向きを付けて同時に進める | そのまま | references/messaging.md | 未解決点ごとに | - |
| D156 | messaging 直列待ち / **並行に行けるものは同時に出す** | 並行に行けるものは同時に出す（別 agent なら条件付き待ちは直列化しない） | そのまま | references/messaging.md | 並行に行けるものは同時に出す | - |
| D157 | messaging 直列待ち / **idle を見たら理由を訊く** | idle を見たら理由を訊く。「ターンが終わった」か「指示を落としている」かは hub に分からない。沈黙を進行と読まない | そのまま | references/messaging.md | 沈黙を進行と読まない | - |
| D158 | messaging ### 解錠 ping（「1 通にまとめる」の唯一の例外） | 並行作業の発火材料になる最小情報（PR 番号 + head SHA、対象の固定点）だけは、本体の報告を待たず 1 行で先に投げてよい。報告を溜めてから投げない | そのまま | references/messaging.md | 報告を溜めてから投げない | - |
| D159 | messaging ## 逆方向（worker から問い合わせるとき — briefing に含める作法） | worker から hub へ問い合わせるときの作法の節。briefing に含める | そのまま | references/briefing.md | 問い合わせるときの作法 | - |
| D160 | messaging 逆方向 / **「誰宛か」を本文で名指しする** | 「誰宛か」を本文で名指しする（本文先頭に [<name> 宛]） | そのまま | references/briefing.md | 「誰宛か」を本文で名指し | - |
| D161 | messaging 逆方向 / **裁定を求める便は「決断が要る」と標識を付ける** | 裁定を求める便は「決断が要る」と標識を付ける。標識のない便が遅延する形になる | そのまま | references/briefing.md | 「決断が要る」 | - |
| D162 | messaging 逆方向 / **裁定が届いたら、着手してよいかまで確認する** | 裁定が届いたら、着手してよいかまで確認する（「指示と受け取ってよいか」） | そのまま | references/briefing.md | 指示と受け取ってよいか | - |
| D163 | messaging 逆方向 / **待つ間の代替作業を質問しない** | 待つ間の代替作業を質問しない。「X 待ちの間 Y をやってよいですか」は hub を 1 往復占有する。待つものは 1 行で投げてターンを終える | そのまま | references/briefing.md | 待つ間の代替作業を質問しない | - |
| D164 | messaging 逆方向 / **送信自体がエラー・timeout で止まったら、その事実を残して報告する** | hub への送信が失敗したら、その事実を残して報告する。黙って別経路を試さない。hc-hub では作業を進めず失敗の表示を画面に残して待ち、後任の hub が新しいアドレスを送ってくる | 変える | references/briefing.md | 黙って別経路を試さない | - |
| D165 | messaging ## 届いた事実を届いたタイミングで確認する | 返信・成果物が届いた事実の確認は、届いたタイミングの行動である。「あとで返ってくるはず」と時刻で読まない | そのまま | references/messaging.md | 届いたタイミングで確認 | - |
| D166 | messaging 届いた事実 / ⚠ 待ち時間を訂正対象にするのは… | 待ち時間を訂正対象にするのは「その待ちで人間の時間を燃やしているとき」だけ。なんでも直列化すれば早いわけではない | そのまま | references/messaging.md | 人間の時間を燃やしているとき | - |
| D167 | messaging ## go・承認は報告された版にだけ掛かる | go・承認は報告された版にだけ掛かる。hub が成果物に go を出すときは対象の版を pin する | そのまま | references/messaging.md | 報告された版にだけ掛かる | - |
| D168 | messaging go・承認 / worker の報告には対象の絶対パス + sha256sum の先頭 12 桁 | worker の報告には対象の絶対パス + sha256sum の先頭 12 桁を添えさせる | そのまま | references/messaging.md | sha256sum の先頭 12 桁 | - |
| D169 | messaging go・承認 / hub の go 文には同じ値を併記する | hub の go 文には同じ値を併記する（plan go <path> <sha256 先頭12>）。worker は受けたら手元の版と突合してから進み、一致しなければ進まず報告する | そのまま | references/messaging.md | plan go <path> | - |
| D170 | messaging go・承認 / go の後に対象を書き換えたら go は失効 | go の後に対象を書き換えたら go は失効する。再報告して取り直す | そのまま | references/messaging.md | 対象を書き換えたら go は失効 | - |
| D171 | messaging ## 着地 | 着地の作法の節。着地後は何も送らない | そのまま | references/messaging.md | 着地後は何も送らない | - |
| D172 | messaging 着地 / 担当分が着地し次の割り当てが無いなら何も送らない | 担当分が着地し次の割り当てが無いなら、その agent へは何も送らない。「終了です」通知も送らない。待機を既定とするのは常駐 agent だけで、動的な worker は結果を受け取ったら止める（2026-11-01） | 変える | references/messaging.md | 「終了です」通知も送らない | - |
| D173 | messaging 着地 / 着地報告への返信・受領確認・評価の擦り合わせはしない | 着地報告への返信・受領確認・評価の擦り合わせはしない | そのまま | references/messaging.md | 着地報告への返信 | - |
| D174 | messaging 着地 / **例外は 1 つ** | 例外は 1 つ: 走行中の review・照会を止める「停止」の 1 行。merge・完了を走行中の側は観測できない | そのまま | references/messaging.md | 例外は 1 つ | - |
| D175 | messaging ### 「agent を終わらせる」は pane close まで | 終了の完了形は、agent の exit ではなく後始末（hc kill → hc rm、台帳へ stop の記録）まで | 変える | references/messaging.md | 終了の完了形 | - |
| D176 | messaging 終わらせる / **worker が自分で終わるとき** | worker が最終報告の後に自分の pane を close して終わる手順（自 pane の close が自殺コマンドになる。tab close・workspace close は他を巻き込むので使わない） | 捨てる | - | - | pane・tab・workspace を閉じる旧来の `herdr` の仕組みそのもの。hc では hub が結果を受け取ってから hc kill → hc rm で片付ける（spec 4.5） |
| D177 | messaging 終わらせる / worker の停止を hub が結果を受け取ってから行う | 結果（最終報告）を受け取ってから hub が worker を止める。報告の前に止めない | 変える | references/messaging.md | 結果を受け取ってから | - |
| D178 | messaging 終わらせる / **hub が retire するとき** | hub が worker を retire するときは hc kill → hc rm で片付け、台帳に stop を記録する。人が tab を閉じて終了した worker も「終了した worker」として同様に扱う | 変える | references/messaging.md | hc kill → hc rm | - |
| D179 | messaging 終わらせる / hub が「pane を残せ」と指示した場合は閉じない | hub が「残せ」と指示した場合は片付けない（証跡参照・交代の名付け用） | 変える | references/messaging.md | 残せと指示した場合は片付けない | - |
| D180 | startup 冒頭 | roster は編成の意図。live に無く起動方法が解決できるエントリは起動対象、起動方法も無い未 live エントリは即エラー（typo 検出を守る） | 変える | references/startup.md | 起動方法が解決できる | - |
| D181 | startup ## agent の配置（2 形態 — roster の `placement` で選択。既定は `tab`） | 配置は placement で選ぶ。値は tab と hidden で、既定は tab（spec 4.10） | 変える | references/startup.md | placement で選ぶ | - |
| D182 | startup 配置 / ### `placement: tab`（既定）— 新規 tab に置く | tab 配置: hub は自分の herdr.space ラベルの値を読み、worker の起動時に --label herdr.space=<その値> を付ける。herdr.tab は付けない。ラベルが無いのに tab が解決されたら黙って hidden にせずエラー | 変える | references/startup.md | herdr.space | - |
| D183 | startup 配置 / 人数が増えても視認性が劣化しない | tab の名前は worker の名前にする。人数が増えても視認性が劣化せず、サイドバーで役割が読める | 変える | references/startup.md | tab の名前は worker の名前 | - |
| D184 | startup 配置 / export で tab label が役割の初期値になる関係とも相性がよい | export の雛形で tab label が役割の初期値になる関係との相性 | 捨てる | - | - | export は herdr tab list と agent list の突き合わせで、旧来の `herdr` の仕組みそのもの。hc-hub に export は持ち込まない |
| D185 | startup 配置 / ### `placement: pane` — 現 tab に分割 / **2〜3 名までが実用域** | pane 配置: 現 tab を split し、広い pane は right・狭い pane は down、2〜3 名まで | 捨てる | - | - | hub の tab を分割する pane 配置は持ち込まない（spec 4.10、設計者の判断）。split と layout は旧来の `herdr` の pane の仕組みそのもの |
| D186 | startup 配置 / ### 共通ルール・事後の移動 | 配置の共通ルールの節 | 変える | references/startup.md | 配置の共通ルール | - |
| D187 | startup 共通ルール / **`--no-focus` を付ける** | 人間のフォーカスを奪わない。worker は hc run --bg で起こす | 変える | references/startup.md | フォーカスを奪わない | - |
| D188 | startup 共通ルール / **`--cwd "$PWD"` を明示する** | 作業ディレクトリを hc run --cwd で明示し、呼び出し側の cwd を暗黙に引き継がない | 変える | references/startup.md | --cwd を明示する | - |
| D189 | startup 共通ルール / 新 pane ID は応答の `.result.pane.pane_id` を読む | 新しいアドレスは hc run の応答から読み、サイドバーの並びから推測しない | 変える | references/startup.md | 並びから推測しない | - |
| D190 | startup 共通ルール / 既存 pane を後から tab 化できる: `pane move` | pane move による後からの tab 化（--label と --tab-label の意味差が未検証） | 捨てる | - | - | 旧来の `herdr` の pane move そのもの。pane の移動と、移動後の新しい pane ID への追従は hc に無い |
| D191 | startup 共通ルール / workspace / worktree の新設は人間が明示した場合だけ | workspace や worktree の新設は人間が明示した場合だけ。hc に workspace は無く、worktree の新設は worktrees の規約に従う | 変える | references/startup.md | 新設は人間が明示した場合だけ | - |
| D192 | startup ## agent の起動 | 起動の節。agent start は利用可能な shell pane が前提で layout は作らない | 捨てる | - | - | shell pane を前提にする agent start は旧来の `herdr` の仕組み。hc run は pane を要らない |
| D193 | startup 起動 / 名前は `[a-z][a-z0-9_-]{0,31}`、live 間で一意 | 名前は core 全体で一意。動的な worker は <レーン>-<preset>-<連番> の規則で自動に付け、32 文字を超えるときの短縮規則を書く。重複は hc run の失敗としてエラーにし、黙って別名にしない | 変える | references/startup.md | core 全体で一意 | - |
| D194 | startup 起動 / kind 一覧とオプションは `--help` で確認 | エージェントの指定は command か template。引数とオプションの正典はインストール済みバイナリの hc run --help | 変える | references/startup.md | hc run --help | - |
| D195 | startup 起動 / agent 固有の引数は `--` 以降に渡す | エージェント固有の引数は command の argv に入れる | 変える | references/startup.md | command の argv | - |
| D196 | startup 起動 / 起動 timeout は既定 30 秒 | 最初の依頼は hc run に渡す。起動直後に hc get で状態の報告があるかを確かめ、無ければ人に知らせて止まる。agent_not_ready 相当の準備待ちでも名前は保持され、hc read は使える | 変える | references/startup.md | 最初の依頼は hc run に渡す | - |
| D197 | startup 起動 / ### kind 固有の起動引数 | エージェント固有の起動引数の節 | 変える | references/agents.md | 固有の起動引数 | - |
| D198 | startup 起動引数 / **`kind: devin` には `-- --permission-mode dangerous` を付ける** | Devin は permission-mode を省略すると auto で起き、tool 承認待ちで黙って停止する。dangerous はプロジェクトの deny list まで auto-approve する（deny を維持するなら hook 側で塞ぐ）。agents の例として残し、他のエージェントは利用者が書き足す | 変える | references/agents.md | --permission-mode | - |
| D199 | startup 起動引数 / **`kind: claude` には `-- --name <同名>`** | claude セッション名を agent 名と揃える --name の指定 | 捨てる | - | - | 命名規約の 3 系統を揃えるための指定。宛先名が別体系になる sendmessage を持ち込まないので不要（spec 4.3） |
| D200 | startup ### roster からの起動（`kind` を持つ未 live エントリ） | 起動対象と判定されたエントリを起動する手順の節 | 変える | references/startup.md | 起動対象と判定 | - |
| D201 | startup 起動手順 / 1. `agent list` で idle の live agent を棚卸し | 起動前に、同じレーンに idle で再利用できる worker がいないかを hc ls --label hc-hub.lane=<L> と hc get で見る。空きがあるのに新規を起動するのは文脈予算の浪費。独立した仕事は 1 人に積まない | 変える | references/startup.md | 再利用できる worker | - |
| D202 | startup 起動手順 / 2. 起動前に人間へ編成案を 1 行で確認する | 起動前の人間への編成案の確認は外し、人の承認を求めずに起こす。人の承認を外すぶん棚卸しの歯止めは残す | 変える | references/startup.md | 人の承認を求めずに起こす | - |
| D203 | startup 起動手順 / 3. `placement` に従い tab/pane を用意し `agent start` | 起動は hc-hub spawn-argv の出力をそのまま hc に渡す。--outlive-parent・ラベル・herdr.space は CLI が組み立て、手で hc run を組まない | 変える | references/startup.md | hc-hub spawn-argv | - |
| D204 | startup 起動手順 / 4. `agent list` で live 解決を再確認 → briefing 送信 | 依頼が届いたかを状態が working になる・ターンが進むことで確認する。届いてから台帳に spawn を記録し、briefing を送る（稼働途中の追加は「現在の状態」入り 8 ブロック版） | 変える | references/startup.md | 8 ブロック版 | - |
| D205 | startup ## 命名規約（重要） | agent 名・Claude セッション名・Codex セッション名の 3 系統の名前を揃え、宛先解決を 1 つの roster で済ませる | 捨てる | - | - | 3 系統は transport ごとの宛先名で、旧来の `herdr` の仕組みそのもの。hc は --name の 1 系統で、名前は自動付与の規則 1 つで決まる（spec 4.5） |
| D206 | startup ## 起動後 | 起動後は live を確認し、roster 検証へ進み、briefing を送る。briefing は hub が書き、人間に書かせない | 変える | references/startup.md | 人間に書かせない | - |
| D207 | startup ## 注意 | 起動に関する注意の節 | そのまま | references/startup.md | 起動に関する注意 | - |
| D208 | startup 注意 / 自動起動は `kind` を持つエントリ限定 + 人間の確認付き | 自動起動は command か template が解決できるエントリに限る。人間の確認は外す。起動方法の無い agent を hub が勝手に作らない（両方ある・どちらも無いはエラー） | 変える | references/startup.md | command か template | - |
| D209 | startup 注意 / `agent start` に失敗した pane は残る | 起動に失敗した、または依頼が届かなかった worker は、送り直しの上限（2 回）を使い切ったら hc kill → hc rm で片付けて人に上げる。記録の無い worker を残さない | 変える | references/startup.md | 使い切ったら | - |
| D210 | failure-modes # failure-modes（実害カタログ） | 何が起きたか / 区別できた最小の観測 / 打った手、の 3 列で書き、新しい失敗が出たら足す | そのまま | references/failure-modes.md | 区別できた最小の観測 | - |
| D211 | failure-modes ## herdr 固有 | Herdr 固有の失敗の節を hc 固有の罠の節に変える。Task 0 の実測で見つかった hc 固有の罠（信頼確認ダイアログで status が null のまま等）を足す | 変える | references/failure-modes.md | hc 固有の罠 | - |
| D212 | failure-modes herdr 固有 / `blocked` を完了と誤読 | blocked を完了と誤読する。承認・質問の画面であり完了ではない。hc read で画面を見て approval の範囲で答える | 変える | references/failure-modes.md | blocked を完了と誤読 | - |
| D213 | failure-modes herdr 固有 / `unknown` を完了と誤読 | 状態が報告されない（status が null のまま）ことを完了と読まない。信頼確認ダイアログ中は null のままで、wait も blocked の通知も来ない。hc read で画面を確かめる | 変える | references/failure-modes.md | 状態が null のまま | - |
| D214 | failure-modes herdr 固有 / timeout/stalled を未配送と誤読して再送 | timeout や stalled を未配送と読んで再送しない。配送は済んでいる可能性が高い。再送前に hc read で届いたか確認する | 変える | references/failure-modes.md | 再送前に hc read | - |
| D215 | failure-modes herdr 固有 / pane から応答が読めない | alternate screen 上で描画される応答は host scrollback に残らず、行数を増やしても読めない。受け手に応答をファイルに書いてパスだけ返すよう依頼する（hc read で同じ現象が起きるかは未確認） | 変える | references/failure-modes.md | 応答をファイルに書いて | - |
| D216 | failure-modes herdr 固有 / agent exit で名が消える | agent の exit で名が消え、交代・再起動で agent start により付け直す | 捨てる | - | - | 名が live agent に紐づく旧来の `herdr` の仕組みそのもの。hc は名前が terminal に付き、hc rm まで残る |
| D217 | failure-modes herdr 固有 / `session stop`→`attach` で全 agent 名が消える | session stop から attach で全 agent 名が消え、herdr-session で付け直す | 捨てる | - | - | 旧来の `herdr` の session の仕組みそのもの。herdr-core は再起動でプログラムが消え、名前を付け直す対象が無い（spec 4.1） |
| D218 | failure-modes herdr 固有 / `pane move` 後に旧 pane ID で宛先不明 | pane move の後に旧 pane ID が解決しない | 捨てる | - | - | pane の移動と pane ID は旧来の `herdr` の仕組みそのもの |
| D219 | failure-modes herdr 固有 / `agent wait --until idle` が作業中に返る | wait が作業中に返る。prompt 入力中の隙間で idle を観測して settled と判定する。回収には status だけでなく画面の文面の poll を併用する。wait が返ったら画面を読み、宣言だけで終わったか完了かを見分ける | 変える | references/failure-modes.md | 宣言だけで終わった | - |
| D220 | failure-modes herdr 固有 / Devin が permission prompt で停止 | エージェントが権限確認の画面で blocked になる。hub は approval の範囲で画面を読んで答え、範囲外は人に上げる（従来の「hub は UI を回答しない」から変える） | 変える | references/failure-modes.md | 画面に承認 UI | - |
| D221 | failure-modes herdr 固有 / `tab create` が別 workspace に作られる | tab の作成先を指定しないと、意図しない場所に tab が出る。hc-hub は hub 自身の herdr.space ラベルから決め、無ければエラーにする | 変える | references/failure-modes.md | 意図しない space に | - |
| D222 | failure-modes herdr 固有 / herdr 制御コマンドが permission に拒否される | 複合コマンド（cd・;・パイプ・echo >> の同梱）は permission allow の先頭一致から外れ、分類器に回って拒否される。制御コマンドは単独で打つ（roster・log の更新は別コマンドに分ける） | 変える | references/failure-modes.md | 制御コマンドは単独で打つ | - |
| D223 | failure-modes herdr 固有 / SendMessage / `codex queue` が別集団の同名 agent に届く | 名前解決がマシン全域で、別集団の同名 agent に届く。集団が混在する環境では宛先を限定する | 変える | references/failure-modes.md | 別集団の同名 | - |
| D224 | failure-modes herdr 固有 / agent 終了後に空の pane/tab が残る | agent の終了と後始末は別。hub の停止は hc kill → hc rm まで行い、台帳に記録する | 変える | references/failure-modes.md | 終了と後始末は別 | - |
| D225 | failure-modes ## SendMessage 固有 | SendMessage 固有の失敗の節 | 捨てる | - | - | SendMessage は持ち込まない（spec 4.3） |
| D226 | failure-modes SendMessage 固有 / メッセージが held で届かない | permission mode の組で held になり届かない | 捨てる | - | - | SendMessage の held 意味論そのもの |
| D227 | failure-modes SendMessage 固有 / 自分宛で拒否 | 自分宛の送信が拒否される | 捨てる | - | - | SendMessage の仕組みそのもの |
| D228 | failure-modes SendMessage 固有 / 届かない環境跨ぎ | コンテナ・WSL・別マシンは登録ファイルを共有せず届かない | 捨てる | - | - | SendMessage の登録ファイルの仕組みそのもの。別マシンは最初の版の非目標 |
| D229 | failure-modes SendMessage 固有 / サイズ/バースト超過 | サイズやバーストの超過で拒否される。長文はファイルに書いてパスを送る | 変える | references/briefing.md | 長文はファイルに書いてパスを送る | - |
| D230 | failure-modes ## codex queue 固有 | codex queue 固有の失敗の節 | 捨てる | - | - | codex-queue は持ち込まない（spec 4.3） |
| D231 | failure-modes codex queue 固有 / `--thread` が解決しない | --thread が名前不一致で解決しない | 捨てる | - | - | codex queue の仕組みそのもの |
| D232 | failure-modes codex queue 固有 / コマンドが無い | 古い版に queue コマンドが無い | 捨てる | - | - | codex queue の仕組みそのもの |
| D233 | failure-modes ## 運用固有 | 運用固有の失敗の節 | そのまま | references/failure-modes.md | 運用固有の罠 | - |
| D234 | failure-modes 運用固有 / hub の中継で情報が落ちる | 中継で情報が落ちる。件数・集合の再掲と本文同梱で防ぐ | そのまま | references/failure-modes.md | 中継で情報が落ちる | - |
| D235 | failure-modes 運用固有 / 「追います」「監視します」を書かせる | 「追います」「監視します」を書かせる。書くのは「いま何を区切ったか」「次に誰が動くか」だけ | そのまま | references/failure-modes.md | 「監視します」を書かせる | - |
| D236 | failure-modes 運用固有 / 指摘が非同期に届き受け手が何度も直す | 指摘が非同期に届き受け手が何度も直す。1 便に合流し、blocker のみ例外 | そのまま | references/failure-modes.md | 受け手が何度も直す | - |
| D237 | failure-modes 運用固有 / auto-compact 後に handoff を書く | auto-compact 後に handoff を書くと二次記述で品質が劣る。検出で即交代する | そのまま | references/failure-modes.md | 二次記述で品質が劣る | - |
| D238 | failure-modes 運用固有 / 着地後の挨拶往復 | 着地後の挨拶往復。着地したら何も送らず、例外は「停止」1 行だけ | そのまま | references/failure-modes.md | 着地後の挨拶往復 | - |
| D239 | failure-modes 運用固有 / 直列待ちが構造化される | 直列待ちが構造化される。裁定に「誰が・いつ着手」を書き、hub が閉じられるものは閉じる | そのまま | references/failure-modes.md | 直列待ちが構造化される | - |
| D240 | failure-modes 運用固有 / worker の枠組みを hub が追認する | 裁定文に worker の数値がそのまま入り、母集団違いが後で発覚する。書く直前に「何を測った値か」「baseline は」と 1 問訊く | そのまま | references/failure-modes.md | 枠組みを hub が追認する | - |
| D241 | failure-modes 運用固有 / hub の出力が検算されず成果物へ入る | hub が書いた symbol・パス・数値を worker が転記する。hub は自分の出力に照会出力を添える | そのまま | references/failure-modes.md | 検算されず成果物へ入る | - |
| D242 | failure-modes 運用固有 / `file:line` の ref 不一致 | worker の branch と hub の checkout で行番号が違う。ref を併記し、作業 ref は git show <branch>:<path> で読む | そのまま | references/failure-modes.md | ref 不一致 | - |
| D243 | failure-modes 運用固有 / 母集団を検索範囲で切る | 「見つかった N 件」が実は検索パターンの当たり数。母集団の定義を独立に確認してから数える | そのまま | references/failure-modes.md | 母集団を検索範囲で切る | - |
| D244 | failure-modes 運用固有 / 規約の手順を目的から切り離して適用 | 規約の手順を目的から切り離して適用する。問うべきは「照会できたか」でなく規約が守っている物。上界が桁で離れているときだけ推測が照会の代わりになる | そのまま | references/failure-modes.md | 目的から切り離して適用 | - |
| D245 | failure-modes 運用固有 / 空きがあるのに新規 agent を起動 | idle の live agent が居るのに新規を起動する。起動前に idle を棚卸しし「既存で足りないか」を問う | そのまま | references/failure-modes.md | 空きがあるのに新規 | - |
| D246 | failure-modes 運用固有 / review が進行中 branch で腐る | 指摘した時点の SHA と実装の head がずれて指摘が stale になる。SHA で pin し、動く branch は報告直前に再取得させる | そのまま | references/failure-modes.md | 進行中 branch で腐る | - |
| D247 | failure-modes 運用固有 / `gh issue comment --edit-last` が他人のコメントを上書き | 全 agent の author が同一なので --edit-last は他人のコメントを掴む。comment ID 指定の gh api -X PATCH を使う | そのまま | references/failure-modes.md | --edit-last | - |
| D248 | failure-modes 運用固有 / `pgrep -f` が自分自身を拾う | pgrep -f は自分のコマンド行にパターンが入って自分を拾う。ブラケット記法で自分を除外する | そのまま | references/failure-modes.md | ブラケット記法 | - |
| D249 | failure-modes 運用固有 / 「確かめる」と「走らせる」を 1 コマンドに並べる | 確かめる処理と走らせる処理を 1 コマンドに並べると、結果を読む前に走り始める。別コマンドに分け、出力を読んでから走らせる | そのまま | references/failure-modes.md | 別コマンドに分け | - |
| D250 | failure-modes 運用固有 / merge 済みかを ancestry で判定 | squash・rebase merge は祖先を切るので ancestry では未 merge に見える。PR 側から引く（gh pr list --state all） | そのまま | references/failure-modes.md | PR 側から引く | - |
| D251 | failure-modes 運用固有 / `2>/dev/null` 付き照会の 0 件 | 「無い」と「訊けなかった」が同じ出力になる。0 件を不在の証拠にしない。エラー出力を落とさない | そのまま | references/failure-modes.md | 0 件を不在の証拠にしない | - |
| D252 | roster 冒頭 | roster の正は編成の意図（desired state）で、live はその記述に合わせて照合・起動される | そのまま | references/roster.md | 正は編成の意図 | - |
| D253 | roster ## 与え方と優先順位 | roster の与え方は --roster <path> の明示指定と、既定の .hc-hub.yml。起動引数で渡せるのはレーン名だけ | 変える | references/roster.md | --roster <path> | - |
| D254 | roster 与え方 / 1. 起動引数（最優先） | 起動引数で「名前: 役割」を渡す経路は持たず、起動引数はレーン名を受ける | 変える | references/roster.md | 起動引数で渡せるのはレーン名 | - |
| D255 | roster 与え方 / 2. `--roster <path>` | --roster <path> で YAML を明示指定する | そのまま | references/roster.md | 明示指定する | - |
| D256 | roster 与え方 / 3. 既定パス | 既定パスは cwd の .hc-hub.yml。ledger が必須のため、存在しないときに引数のみで動く形は持たず、roster が無ければ明示エラー | 変える | references/roster.md | roster が無ければ明示エラー | - |
| D257 | roster 与え方 / 起動引数では role の短いラベルしか渡せない | role_def・rules・preset・command・template を使うなら YAML 経路限定 | 変える | references/roster.md | YAML 経路限定 | - |
| D258 | roster ## YAML スキーマ | YAML スキーマの節。presets・defaults・ledger・lanes を持つ（スキーマは spec 4.7）。テンプレートは同梱の .hc-hub.yml.example | 変える | references/roster.md | .hc-hub.yml.example | - |
| D259 | roster ### agent 個別フィールド | agent 個別フィールドの表。role・role_def・rules・preset・command・template・handoff_at・placement・approval | 変える | references/roster.md | 個別フィールド | - |
| D260 | roster 個別フィールド / `role` | role は役割の短いラベルで必須（preset が与えてもよい）。briefing にそのまま使う | そのまま | references/roster.md | briefing にそのまま使う | - |
| D261 | roster 個別フィールド / `role_def` | role_def は長文の役割定義 .md へのパス。roster ファイルのあるディレクトリ基準の相対。worker には briefing の役割ブロックへ内容をそのまま注入し、hub のものは hub が起動時に読む | そのまま | references/roster.md | ファイルのあるディレクトリ基準 | - |
| D262 | roster 個別フィールド / `rules` | rules はその agent が従う規律 file（群）。delivery は宛先で分かれる | そのまま | references/roster.md | 規律 file（群） | - |
| D263 | roster 個別フィールド / `preset` | preset は presets のキー名。未定義の preset は即エラー | そのまま | references/roster.md | 未定義の preset | - |
| D264 | roster 個別フィールド / `kind` | kind は廃止し command（argv の配列）か template（hc の template 名）のどちらか一方に置き換える。書かれていたら未知のキーとしてエラーにし、置き換え先を表示する | 変える | references/roster.md | 置き換え先を表示 | - |
| D265 | roster 個別フィールド / `transport` | transport（herdr・sendmessage・codex-queue・auto）の送信経路指定 | 捨てる | - | - | hc send に一本化したため廃止（spec 4.3・4.7）。transport は経路選択そのもので旧来の `herdr` の仕組み |
| D266 | roster 個別フィールド / `handoff_at` | handoff_at は 0〜1 の交代判定の使用率閾値（既定 0.8） | そのまま | references/roster.md | 交代判定の使用率閾値 | - |
| D267 | roster 個別フィールド / `placement` | placement は tab か hidden で、既定は tab。それ以外の値はエラー | 変える | references/roster.md | hidden | - |
| D268 | roster 個別フィールド / **解決順序** | 解決順序は defaults → レーン → preset → 個別で、後のものが優先する。rules だけは union | 変える | references/roster.md | 後のものが優先 | - |
| D269 | roster 解決順序 / defaults が与えられるのは限られたフィールドのみ | defaults が与えられるのは限られたフィールドのみ。role・role_def・preset・command・template は preset か個別に限る。defaults で role を許すと必須フィールド検証を潜り抜け、起動方法を許すと typo まで起動対象になる | 変える | references/roster.md | 必須フィールド検証を潜り抜け | - |
| D270 | roster ### rules の merge（union） | rules だけは上書きでなく union（連結）。規律は共通 + 役割固有 + 個人固有の重ね合わせで、個別指定が共通を潰すと境界が消える。全段をこの順に連結する | そのまま | references/roster.md | union（連結） | - |
| D271 | roster rules の merge / 重複するパスは 1 度だけ適用する | 重複するパスは 1 度だけ適用する | そのまま | references/roster.md | 重複するパスは 1 度だけ | - |
| D272 | roster rules の merge / ⚠ 他フィールドの「個別が優先」と merge 規則が違う | 他フィールドの「個別が優先」と merge 規則が違う。混同しない | そのまま | references/roster.md | merge 規則が違う | - |
| D273 | roster ### rules の delivery（宛先で届け方が違う） | rules の delivery は宛先で違う。worker は briefing の境界ブロックへ本文を注入し file パスも併記する。hub は起動時に自分で読む | そのまま | references/roster.md | hub が起動時に自分で読む | - |
| D274 | roster rules の delivery / ⚠ worker に file のパスだけを渡して済ませない | worker に file のパスだけを渡して済ませない。注入が本経路でパスは再読み用の補助。読まなくても規律が届いている状態にする | そのまま | references/roster.md | パスだけを渡して済ませない | - |
| D275 | roster ### role_def（旧 role_file） | role_file は未知のキーとして即エラーにし、role_def への改名を案内する。別名として黙って読まない | 変える | references/roster.md | 別名として黙って読まない | - |
| D276 | roster ## 起動時検証（必須） | 起動時検証は必須。roster を得たら各エントリを 3 分岐で処理する | そのまま | references/roster.md | 起動時検証は必須 | - |
| D277 | roster 起動時検証 / live に解決できる | live に解決できるエントリはそのまま（live の判定は hc ls --label と hc get） | 変える | references/roster.md | hc ls --label | - |
| D278 | roster 起動時検証 / live に無い + `kind` が解決できる | live に無く起動方法が解決できるエントリは起動対象。起動後に live 解決を再確認する | 変える | references/roster.md | 解決できれば起動 | - |
| D279 | roster 起動時検証 / live に無い + `kind` 無し | live に無く起動方法も無いエントリは即エラー。黙ってスキップ・警告で続行しない | そのまま | references/roster.md | 黙ってスキップ・警告で続行しない | - |
| D280 | roster 起動時検証 / ⚠ **`kind` 無しの未解決を起動対象にしない** | 起動方法の不在は名前の typo か陳腐化の可能性。黙って起動すると間違った名前の agent が spawn する。typo の検出を守るため、この分岐は厳密に | そのまま | references/roster.md | typo の検出を守る | - |
| D281 | roster 起動時検証 / **`preset` 参照が `presets:` で定義されていること** | preset 参照が presets で定義されていること。未定義名は即エラー | そのまま | references/roster.md | preset 参照 | - |
| D282 | roster 起動時検証 / **`role_def` / `rules` で参照される file がすべて存在し読めること** | role_def と rules で参照される file がすべて存在し読めること（preset・defaults 経由の分も含む）。不在・不可読は即エラー | そのまま | references/roster.md | 存在し読めること | - |
| D283 | roster 起動時検証 / **返信宛先 `hub` が live に解決すること** | worker の返信宛先の hub が live に解決することを確かめる。返信先は briefing に書く hub のアドレスで示す | 変える | references/roster.md | 返信宛先の hub が live | - |
| D284 | roster 起動時検証 / 返信宛先の改名（`agent rename <self-pane> hub`・sendmessage の名前） | 自分の agent 名を hub に改名して返信宛先を揃える手順と、sendmessage の受け手名を hub に揃える手順 | 捨てる | - | - | agent rename は旧来の `herdr` の仕組みそのもの。hc には起動後に名前を付ける操作が見当たらず、hub はラベルとアドレスで識別する（spec 4.3） |
| D285 | roster 起動時検証 / 逆方向も見る | live だが roster に無い agent は名簿の陳腐化として扱う。hub の起動時点検では、ラベルはあるのに台帳に無い worker を引き継がずに人に上げる | 変える | references/roster.md | 名簿の陳腐化 | - |
| D286 | roster 起動時検証 / roster が古い・矛盾する場合の修復は人間の判断 | roster が古い・矛盾する場合の修復は人間の判断で、hub が勝手に roster を書き換えない。動的な worker は roster に書かないので、動的追加という例外は持たない | 変える | references/roster.md | 勝手に roster を書き換えない | - |
| D287 | roster ## 動的追加（稼働中に agent を足す） | 稼働中の worker の追加は roster への追記ではなく台帳への記録で扱う。動的な worker は roster に書かない（名簿と台帳を分ける） | 変える | references/roster.md | roster に書かない | - |
| D288 | roster 動的追加 / 2. 起動時検証と同じ 3 分岐をそのエントリに適用 | 起動方法が解決できるなら起動、無ければエラーという同じ検証を動的な worker にも適用する | 変える | references/roster.md | 同じ検証を動的な worker | - |
| D289 | roster 動的追加 / 3. briefing を送る（8 ブロック版） | 稼働途中の参加なので「現在の状態」ブロックを含む 8 ブロック版の briefing を送る | そのまま | references/roster.md | 稼働途中の参加 | - |
| D290 | roster 動的追加 / ⛔ **追記せずに live にだけ追加しない** | 記録せずに live にだけ追加しない。起こした worker は台帳に記録し、記録の無い worker を残さない（記録に失敗したら片付けて人に上げる） | 変える | references/roster.md | 記録の無い worker を残さない | - |
| D291 | roster ## export（現在の配置から雛形を作る） | herdr tab list と agent list の JSON を突き合わせ、tab label を role の初期値にした YAML 雛形を生成する export | 捨てる | - | - | 旧来の `herdr` の herdr tab list・agent list の出力を結合する手順そのもの。spec に hc-hub の export は無い |
| D292 | roster ## 交代時の仮名 | 交代では前任生存中に後任を仮名 <name>-next で起動し、前任の exit 後に後任へ付け替える | そのまま | references/roster.md | 後任へ付け替える | - |
| D293 | transports 冒頭・## 解決の優先順位 | 宛先ごとに transport を上から最初に合致した規則で解決する（個別指定・Claude から Claude は sendmessage・宛先が Codex は codex-queue・defaults.transport・既定は herdr）。transport: auto の扱い | 捨てる | - | - | 宛先ごとの経路選択は旧来の `herdr` の transport の仕組みそのもの。hc send に一本化（spec 4.3） |
| D294 | transports ### `defaults.transport` の効き方 | defaults.transport は native 経路を持たない宛先にだけ効く代替の指定 | 捨てる | - | - | transport の仕組みそのもの。hc send に一本化（spec 4.3） |
| D295 | transports ## `herdr`（既定・汎用） | herdr agent prompt による非同期送信（既定）と --wait による同期照会、宛先は live agent name または pane ID | 変える | references/messaging.md | 宛先は名前かアドレス | - |
| D296 | transports herdr / `agent_blocked` | 宛先が承認・質問 UI で待っている間、送信は行われない。画面を読んでから人に判断を仰ぐ。hc send は blocked の宛先を exit 9 で拒否し、答えるなら画面を読んで hc keys か hc send --force | 変える | references/approvals.md | hc send --force | - |
| D297 | transports herdr / `agent_prompt_stalled` と `timeout` | stalled と timeout は未配送の証明ではない。再送前に画面を読んで届いたか確認する | 変える | references/messaging.md | 未配送の証明ではない | - |
| D298 | transports herdr / `unknown` 状態 | 分類不能な状態は完了の証明ではない | 変える | references/failure-modes.md | 完了の証明ではない | - |
| D299 | transports herdr / `pane read` の罠 | alternate screen 上のエージェントの応答は取れない。取れなければ受け手に完全な応答をファイルに書いてパスだけ返すよう依頼する | 変える | references/failure-modes.md | 完全な応答をファイルに書いて | - |
| D300 | transports herdr / 応答の読み取り | 応答の読み取りは hc read で画面を読む（agent read --source recent-unwrapped の代わり） | 変える | references/messaging.md | hc read で応答を読む | - |
| D301 | transports ## `sendmessage`（Claude → Claude） / **held / refused 意味論** / **`notify_when_idle`** | Claude から Claude への SendMessage ツールによる送信。要件・held と refused の意味論・notify_when_idle・宛先名・制約・発見 | 捨てる | - | - | エージェントごとの経路で、マシン全域で名前を解決しレーンの分離をすり抜ける（spec 4.3） |
| D302 | transports ## `codex-queue`（任意 → Codex） / **CLI コマンド**なので送り手は codex でなくてよい | codex queue による Codex への送信（--thread と --remote、公式リファレンス未掲載） | 捨てる | - | - | エージェントごとの経路で、マシン全域で名前を解決しレーンの分離をすり抜ける（spec 4.3）。--remote は別マシンで、最初の版の非目標 |
| D303 | transports ## 名前解決のスコープ | native 経路の名前解決がマシン全域で session・workspace を跨ぐことと、集団が混在する環境で宛先を限定する運用。干渉は自分のレーン内に留める | 変える | references/lanes.md | 干渉は自分のレーン内に留める | - |
| D304 | transports 名前解決 / `herdr --session` / `--machine` / `--remote` | 自分の継承コンテキスト外のソケットへ接続する使い方も同じ穴。別マシンを指す指定（hc run --on など）は使わず、roster に書かれていたらエラー | 変える | references/lanes.md | 別マシンを指す指定 | - |
