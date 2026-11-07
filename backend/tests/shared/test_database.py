"""add_missing_columns: the startup schema upgrade."""
from sqlalchemy import create_engine, inspect, text

from app.shared.database import add_missing_columns


def test_add_missing_columns_upgrades_old_tables_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # the schema as it was before name/note existed
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL)"))
        conn.execute(text("INSERT INTO customers (email) VALUES ('old@x.com')"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # second run is a no-op
    columns = {c["name"] for c in inspect(engine).get_columns("customers")}
    assert "name" in columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM customers")).scalar() is None
    engine.dispose()


def test_add_missing_columns_also_creates_their_indexes(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # orders as it was before completed_at existed
        conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, order_number INTEGER NOT NULL, "
                          "customer_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL, total INTEGER NOT NULL, "
                          "created_at DATETIME NOT NULL)"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # idempotent
    indexes = {i["name"] for i in inspect(engine).get_indexes("orders")}
    assert "ix_orders_completed_at" in indexes
    assert "ix_orders_created_at" not in indexes  # existing columns are left alone
    engine.dispose()
