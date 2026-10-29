import psycopg
import pandas as pd
import hashlib
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, EXCEL_PATH, RAW_DIR
from pdf_parser import parse_pdf

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
    password = DB_PASSWORD
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

def build_document_row(row, pdf_path, pages):
    if pd.isna(row["total_page"]):
        raise ValueError(f"total_page tidak boleh kosong untuk file {row['file_name']}")
    excel_pages = int(row["total_page"])
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

def build_page_rows(pages):
    return [
        {
            "page_number": nomor,
            "page_text": teks if kategori == "digital" else None,
            "type_page": kategori,
        }
        for nomor, teks, kategori in pages
    ]

def load_document(conn, row, pdf_path):
    pages, _ = parse_pdf(pdf_path)
    document_row = build_document_row(row, pdf_path, pages)
    page_rows = build_page_rows(pages)
    new_pages = 0
    with conn.cursor() as cur:
        document_id = insert_document(cur, document_row)
        for page_row in page_rows:
            page_row["document_id"] = document_id
            new_pages += insert_page(cur, page_row)
    return len(pages), new_pages

def collect_documents():
    df = read_metadata()
    documents = []
    for _, row in df.iterrows():
        file_name = str(row["file_name"]).strip()
        pdf_path = RAW_DIR / f"{file_name}.pdf"
        if not pdf_path.exists():
            raise FileNotFoundError(f"File PDF tidak ditemukan: {pdf_path}")
        documents.append((file_name, row, pdf_path))
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

def insert_page(cur, row):
    cur.execute(
        """
        INSERT INTO pages (
            document_id, page_number, page_text, type_page
        ) VALUES (
            %(document_id)s, %(page_number)s, %(page_text)s, %(type_page)s
        )
        ON CONFLICT (document_id, page_number) DO NOTHING
        """,
        row,
    )
    return cur.rowcount

def load_all_documents():
    documents = collect_documents()
    summary = {"documents": 0, "pages_total": 0, "pages_new": 0}
    with get_connection() as conn:
        for file_name, row, pdf_path in documents:
            try:
                pages_total, pages_new = load_document(conn, row, pdf_path)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise ValueError(f"{file_name}: {e}") from e
            summary["documents"] += 1
            summary["pages_total"] += pages_total
            summary["pages_new"] += pages_new
            print(f"OK: {file_name}")
    return summary

if __name__ == "__main__":
    print(load_all_documents())