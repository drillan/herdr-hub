import pytest
from _paths import HERDR1, REFS, ROOT, SHARED


@pytest.mark.parametrize("name", SHARED)
def test_shared_reference_identical(name: str) -> None:
    herdr1 = ROOT / "skills/herdr-hub/references" / name
    assert (REFS / name).read_bytes() == herdr1.read_bytes()


def test_shared_references_have_no_herdr1_commands() -> None:
    for name in SHARED:
        assert not HERDR1.search((REFS / name).read_text())
