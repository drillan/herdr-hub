from pathlib import Path

import pytest
from fake_hc import run_cli
from hc_hub_lib.preflight import PreflightError, run_preflight


def env_for(tmp_path: Path, config: str | None) -> dict[str, str]:
    if config is not None:
        d = tmp_path / "herdr-core"
        d.mkdir()
        (d / "config.toml").write_text(config)
    return {"HC_TERMINAL_ID": "t5", "XDG_CONFIG_HOME": str(tmp_path)}


def test_missing_terminal_id_raises() -> None:
    with pytest.raises(PreflightError, match="herdr-core の管理下ではない"):
        run_preflight({})


def test_notes_false_raises(tmp_path: Path) -> None:
    with pytest.raises(PreflightError, match="notes"):
        run_preflight(env_for(tmp_path, "notes = false\n"))


def test_notes_true_passes(tmp_path: Path) -> None:
    run_preflight(env_for(tmp_path, "notes = true\n"))


def test_notes_not_bool_raises(tmp_path: Path) -> None:
    with pytest.raises(PreflightError, match="notes"):
        run_preflight(env_for(tmp_path, 'notes = "no"\n'))


def test_config_without_notes_key_passes(tmp_path: Path) -> None:
    run_preflight(env_for(tmp_path, 'other = "x"\n'))


def test_no_config_file_passes(tmp_path: Path) -> None:
    run_preflight(env_for(tmp_path, None))


def test_unreadable_config_raises(tmp_path: Path) -> None:
    with pytest.raises(PreflightError, match=r"config\.toml"):
        run_preflight(env_for(tmp_path, "notes = = ["))


def test_home_config_used_when_xdg_unset(tmp_path: Path) -> None:
    d = tmp_path / ".config/herdr-core"
    d.mkdir(parents=True)
    (d / "config.toml").write_text("notes = false\n")
    with pytest.raises(PreflightError, match="notes"):
        run_preflight({"HC_TERMINAL_ID": "t5", "HOME": str(tmp_path)})


def test_cli_preflight(tmp_path: Path) -> None:
    ok = run_cli(
        "preflight",
        env_extra={"HC_TERMINAL_ID": "t5", "XDG_CONFIG_HOME": str(tmp_path)},
    )
    assert ok.returncode == 0, ok.stderr
    ng = run_cli("preflight", env_extra={"XDG_CONFIG_HOME": str(tmp_path)})
    assert ng.returncode == 2
    assert "管理下ではない" in ng.stderr
