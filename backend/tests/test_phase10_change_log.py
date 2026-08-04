from app.models.transaction_change_log import TransactionChangeLog


def test_change_log_model_tablename():
    assert TransactionChangeLog.__tablename__ == "transaction_change_logs"
