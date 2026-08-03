from app import config


def test_daily_limits_defaults():
    assert isinstance(config.DAILY_MODEL_CALL_LIMIT, int)
    assert config.DAILY_MODEL_CALL_LIMIT >= 1
    assert isinstance(config.DAILY_UNPARSED_LIMIT, int)
    assert config.DAILY_UNPARSED_LIMIT >= 1
