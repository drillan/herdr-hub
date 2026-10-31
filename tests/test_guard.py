from pathlib import Path

import pytest
from fake_hc import make_fake_hc, run_cli
from hc_hub_lib.guard import GUARDED_OPS, GuardError, check, check_placement_tab

L = "hc-hub.lane"
R = "hc-hub.role"


def test_same_lane_allows_every_guarded_op() -> None:
    for op in GUARDED_OPS:
        check(op, {L: "be", R: "hub"}, {L: "be", R: "impl"})


def test_cross_lane_hub_only_send() -> None:
    check("send", {L: "be", R: "hub"}, {L: "fe", R: "hub"})
    for op in GUARDED_OPS - {"send"}:
        with pytest.raises(GuardError):
            check(op, {L: "be", R: "hub"}, {L: "fe", R: "hub"})


def test_cross_lane_worker_target_refused() -> None:
    with pytest.raises(GuardError):
        check("send", {L: "be", R: "hub"}, {L: "fe", R: "impl"})


def test_worker_self_cannot_cross_even_to_hub() -> None:
    with pytest.raises(GuardError):
        check("send", {L: "be", R: "impl"}, {L: "fe", R: "hub"})


def test_unlabeled_target_refused() -> None:
    with pytest.raises(GuardError, match="ラベル"):
        check("send", {L: "be", R: "hub"}, {})


@pytest.mark.parametrize(
    ("self_labels", "target"),
    [
        ({}, {}),
        ({}, {L: "be", R: "impl"}),
        ({L: "be"}, {L: "be", R: "impl"}),
    ],
)
def test_self_without_lane_or_role_refused(
    self_labels: dict[str, str], target: dict[str, str]
) -> None:
    with pytest.raises(GuardError, match="hc-hub start"):
        check("send", self_labels, target)


def test_unknown_op_refused() -> None:
    with pytest.raises(GuardError, match="exec"):
        check("exec", {L: "be", R: "hub"}, {L: "be", R: "impl"})


def test_placement_tab_requires_space_label() -> None:
    assert check_placement_tab({"herdr.space": "sp1"}) == "sp1"
    with pytest.raises(GuardError, match=r"herdr\.space"):
        check_placement_tab({L: "be"})


def test_cli_space_prints_value_or_exits_2(tmp_path: Path) -> None:
    hc = make_fake_hc(
        tmp_path,
        {"t5": {"labels": {"herdr.space": "sp1"}}, "t6": {"labels": {L: "be"}}},
        [],
    )
    ok = run_cli("space", "--hc", str(hc), env_extra={"HC_TERMINAL_ID": "t5"})
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == "sp1"
    ng = run_cli("space", "--hc", str(hc), env_extra={"HC_TERMINAL_ID": "t6"})
    assert ng.returncode == 2
    assert "herdr.space" in ng.stderr


def test_cli_guard_uses_hc_get(tmp_path: Path) -> None:
    hc = make_fake_hc(
        tmp_path,
        {
            "t5": {"labels": {L: "be", R: "hub"}},
            "t9": {"labels": {L: "fe", R: "impl"}},
            "t8": {"labels": {L: "be", R: "impl"}},
        },
        [],
    )
    env = {"HC_TERMINAL_ID": "t5"}
    ng = run_cli("guard", "--op", "send", "--hc", str(hc), "t9", env_extra=env)
    assert ng.returncode == 2
    assert ng.stderr.startswith("hc-hub:")
    ok = run_cli("guard", "--op", "send", "--hc", str(hc), "t8", env_extra=env)
    assert ok.returncode == 0, ok.stderr


def test_cli_guard_hc_failure_is_error_not_empty_labels(tmp_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {L: "be", R: "hub"}}}, [])
    p = run_cli(
        "guard",
        "--op",
        "send",
        "--hc",
        str(hc),
        "t404",
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 2
    assert "fake: get t404 --json" in p.stderr


def test_cli_guard_without_terminal_id(tmp_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {}, [])
    p = run_cli("guard", "--op", "send", "--hc", str(hc), "t9")
    assert p.returncode == 2
    assert "HC_TERMINAL_ID" in p.stderr


def test_keep_is_guarded() -> None:
    assert "keep" in GUARDED_OPS
    check("keep", {L: "be", R: "hub"}, {L: "be", R: "impl"})
    with pytest.raises(GuardError):
        check("keep", {L: "be", R: "hub"}, {L: "fe", R: "impl"})
