from collections.abc import Mapping, Sequence

LANE = "hc-hub.lane"
ROLE = "hc-hub.role"
HUB_ROLE = "hub"
SPACE = "herdr.space"
# hc-session の SessionStart hook が端末に付ける
SESSION = "claude.session"

GUARDED_OPS: frozenset[str] = frozenset(
    {
        "send",
        "keys",
        "interrupt",
        "kill",
        "rm",
        "label",
        "put",
        "attach",
        "wait",
        "read",
        "keep",
    }
)


class GuardError(Exception):
    pass


def check(
    op: str, self_labels: Mapping[str, str], target_labels: Mapping[str, str]
) -> None:
    if op not in GUARDED_OPS:
        msg = f"ガード対象外の操作 {op!r}。対象: {', '.join(sorted(GUARDED_OPS))}"
        raise GuardError(msg)
    if LANE not in self_labels or ROLE not in self_labels:
        msg = f"自分に {LANE} か {ROLE} が無い。先に hc-hub start を実行する"
        raise GuardError(msg)
    if LANE not in target_labels or ROLE not in target_labels:
        msg = f"宛先に {LANE} か {ROLE} のラベルが無く、レーンを判定できない"
        raise GuardError(msg)
    if self_labels[LANE] == target_labels[LANE]:
        return
    cross_hub_send = (
        op == "send"
        and self_labels[ROLE] == HUB_ROLE
        and target_labels[ROLE] == HUB_ROLE
    )
    if not cross_hub_send:
        msg = (
            f"レーン {self_labels[LANE]} から別レーン {target_labels[LANE]} への "
            f"{op} は不可（別レーンへは hub 同士の send のみ）"
        )
        raise GuardError(msg)


def check_placement_tab(self_labels: Mapping[str, str]) -> str:
    if SPACE not in self_labels:
        msg = f"自分に {SPACE} ラベルが無く、worker を置く space を決められない"
        raise GuardError(msg)
    return self_labels[SPACE]


def check_own_terminal(
    me: str, self_labels: Mapping[str, str], same_session: Sequence[str]
) -> None:
    # 再起動の後、hub のセッションが worker の端末で再開したことがある（2026-11-11）。
    # そのまま hub として動くと、guard を通って別のセッションを止めうる
    role = self_labels.get(ROLE)
    if role is not None and role != HUB_ROLE:
        msg = (
            f"この端末（{me}）は {ROLE}={role} の worker の端末。"
            "hub のセッションが worker の端末で再開していないかを"
            " hc-session status で確かめる"
        )
        raise GuardError(msg)
    if same_session:
        msg = (
            f"自分のセッション（{SESSION}）が別の live な端末"
            f" {', '.join(same_session)} にもある。"
            "同じセッションを 2 か所で再開していないかを hc-session status で確かめる"
        )
        raise GuardError(msg)
