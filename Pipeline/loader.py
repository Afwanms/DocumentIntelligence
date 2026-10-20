import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "ojk_db"
DB_USER = "ojk_user"


def get_connection():
    password = os.getenv("POSTGRES_PASSWORD")
    if password is None:
        raise RuntimeError("POSTGRES_PASSWORD belum diatur di .env")
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=password,
    )


if __name__ == "__main__":
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documents;")
            print(cur.fetchone())