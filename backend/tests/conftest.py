import pytest


@pytest.fixture(autouse=True)
def _activity_tracking_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Activity accounting opens its own DB connection; most tests run inside a
    rolled-back transaction, so it is off unless a test enables it explicitly
    (see tests/admin_helpers.py::activity_on)."""
    from app.services import activity

    monkeypatch.setattr(activity, "TRACKING_ENABLED", False)
    activity.reset_cache()
