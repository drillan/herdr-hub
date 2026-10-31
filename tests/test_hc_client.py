import stat
import sys
from pathlib import Path

import pytest
from hc_hub_lib import hc_client
from hc_hub_lib.hc_client import HcError, run_hc


def _sleeping_hc(tmp_path: Path) -> Path:
    script = tmp_path / "slow-hc"
    script.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_timeout_is_thirty_seconds() -> None:
    assert hc_client.HC_TIMEOUT_SECONDS == 30


def test_hung_hc_raises_hc_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hc_client, "HC_TIMEOUT_SECONDS", 0.5)
    with pytest.raises(HcError, match="タイムアウト"):
        run_hc(str(_sleeping_hc(tmp_path)), ["get", "t1"])
