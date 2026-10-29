import pymupdf
import pytesseract
from loader import get_connection, hash_file
from PIL import Image
from config import RAW_DIR

OCR_LANG = "ind"
OCR_DPI = 300
OCR_MIN_CHARS = 10

def ocr_image(image):
    return pytesseract.image_to_string(image, lang=OCR_LANG)

def get_scan_pages(cur):
    cur.execute(
        """
        SELECT p.page_id, d.file_hash, d.file_name, p.page_number
        FROM pages as p
        JOIN documents as d
        ON p.document_id = d.document_id
        WHERE p.type_page = 'scan'
        ORDER BY d.file_name, p.page_number
        """,
    )
    return cur.fetchall()

def update_page(cur, page_id, text):
    cur.execute(
        """
        UPDATE pages
        SET page_text = %(page_text)s, type_page = 'ocr'
        WHERE page_id = %(page_id)s AND type_page = 'scan'
        """,
        {"page_id": page_id, "page_text": text},
    )
    return cur.rowcount

def render_page(pdf_path, page_number):
    with pymupdf.open(pdf_path) as pdf:
        if page_number < 1 or page_number > len(pdf):
            raise ValueError(f"Halaman {page_number} tidak ada dalam file {pdf_path}")
        page = pdf[page_number - 1]
        pix = page.get_pixmap(dpi=OCR_DPI)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image

def ocr_pending_pages():
    done = 0
    skipped = 0
    failed = []
    checked_files = set()
    with get_connection() as conn:
        with conn.cursor() as cur:
            scan_pages = get_scan_pages(cur)
            if not scan_pages:
                print("Tidak ada halaman scan yang perlu di-OCR.")
                return {"done": 0, "skipped": 0, "failed": 0}
            for page_id, file_hash, file_name, page_number in scan_pages:
                try:
                    pdf_path = RAW_DIR / f"{file_name}.pdf"
                    if not pdf_path.exists():
                        raise FileNotFoundError(f"File PDF tidak ditemukan: {pdf_path}")
                    if file_name not in checked_files:
                        if hash_file(pdf_path) != file_hash:
                            raise ValueError("hash PDF di Raw berbeda dari yang tersimpan di database")
                        checked_files.add(file_name)
                    text = ocr_image(render_page(pdf_path, page_number)).strip()
                    if len(text) < OCR_MIN_CHARS:
                        print(f"Teks OCR terlalu pendek, tetap scan: {file_name} halaman {page_number}")
                        skipped += 1
                        continue
                    if update_page(cur, page_id, text) == 0:
                        print(f"Peringatan, halaman bukan scan lagi: {file_name} halaman {page_number}")
                        skipped += 1
                        continue
                    conn.commit()
                    done += 1
                    print(f"OCR selesai: {file_name} halaman {page_number}")
                except Exception as e:
                    conn.rollback()
                    failed.append(f"{file_name} halaman {page_number}: {e}")
                    print(f"GAGAL: {file_name} halaman {page_number}: {e}")
    summary = {"done": done, "skipped": skipped, "failed": len(failed)}
    print(f"OCR selesai: {summary}")
    if failed:
        raise RuntimeError(f"{len(failed)} halaman gagal di-OCR. Contoh: {failed[0]}")
    return summary

if __name__ == "__main__":
    print(ocr_pending_pages())
