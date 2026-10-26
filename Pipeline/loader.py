import os
import psycopg
import pandas as pd
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from pdf_parser import parse_pdf, RAW_DIR

load_dotenv()

DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "ojk_db"
DB_USER = "ojk_user"
EXCEL_PATH = Path("Data/Metadata/dokumen_ojk.xlsx")
EXPECTED_COLUMNS = [
    "file_name", 
    "title", 
    "total_page", 
    "url_source", 
    "download_date", 
    "has_table", 
    "status", 
    "effective_date", 
    "revoked_by"
]
REQUIRED_COLUMNS = [col for col in EXPECTED_COLUMNS if col not in ["revoked_by"]]

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

def read_metadata():
    df = pd.read_excel(EXCEL_PATH)
    missing_columns = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Kolom yang hilang di file Excel: {missing_columns}")
    return df

def convert_date(value):
    if pd.isna(value):
        return None
    return pd.to_datetime(value, errors="raise").date()

def convert_boolean(value):
    if pd.isna(value):
        raise ValueError("Nilai boolean tidak boleh kosong")
    value = str(value).strip().lower()
    if value == "ya":
        return True
    elif value == "tidak":
        return False
    else:
        raise ValueError(f"Nilai boolean tidak valid: {value}")

def convert_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None

def hash_file(path):
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

def build_document_row(row, pdf_path):
    if pd.isna(row["total_page"]):
        raise ValueError(f"total_page tidak boleh kosong untuk file {row['file_name']}")
    excel_pages = int(row["total_page"])
    pages, _ = parse_pdf(pdf_path)
    if len(pages) != excel_pages:
        raise ValueError(f"Excel mencatat {excel_pages} halaman, PDF punya {len(pages)}")
    document = {
        "file_hash": hash_file(pdf_path),
        "file_name": convert_text(row["file_name"]),
        "title": convert_text(row["title"]),
        "total_page": len(pages),
        "url_source": convert_text(row["url_source"]),
        "download_date": convert_date(row["download_date"]),
        "has_table": convert_boolean(row["has_table"]),
        "status": convert_text(row["status"]),
        "effective_date": convert_date(row["effective_date"]),
        "revoked_by": convert_text(row["revoked_by"])
    }
    for column in REQUIRED_COLUMNS:
        if document[column] is None:
            raise ValueError(f"Kolom {column} tidak boleh kosong untuk file {row['file_name']}")
    return document

def build_all_documents():
    df = read_metadata()
    documents = []
    for _, row in df.iterrows():
        file_name = str(row["file_name"]).strip()
        pdf_path = RAW_DIR / f"{file_name}.pdf"
        try:
            documents.append(build_document_row(row, pdf_path))
        except Exception as e:
            raise ValueError(f"{file_name}: {e}") from e
    return documents

def insert_document(cur, row):
    cur.execute(
        """
        INSERT INTO documents (
            file_hash, file_name, title, total_page, url_source,
            download_date, has_table, status, effective_date, revoked_by
        ) VALUES (
            %(file_hash)s, %(file_name)s, %(title)s, %(total_page)s, %(url_source)s,
            %(download_date)s, %(has_table)s, %(status)s, %(effective_date)s, %(revoked_by)s
        )
        ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, revoked_by = EXCLUDED.revoked_by, title = EXCLUDED.title, effective_date = EXCLUDED.effective_date, url_source = EXCLUDED.url_source
        RETURNING document_id
        """,
        row,
    )
    return cur.fetchone()[0]

if __name__ == "__main__":
    documents = build_all_documents()
    print(f"Jumlah dokumen siap dimuat: {len(documents)}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            for document in documents:
                insert_document(cur, document)
            cur.execute("SELECT count(*) FROM documents;")
            print(cur.fetchone())