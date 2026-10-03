import sqlite3


def create_user():
    connection = sqlite3.connect(":memory:")
    connection.cursor().execute("select 1")
    return {"id": 1}
