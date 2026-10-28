import pymupdf
import pytesseract
from loader import get_connection, hash_file
from pdf_parser import RAW_DIR
from PIL import Image

OCR_LANG = "ind"
OCR_DPI = 300
OCR_MIN_CHARS = 10

def ocr_image(image):
    return pytesseract.image_to_string(image, lang=OCR_LANG)

def update_page(cur, page_id, text):
    cur.execute(
        """
        UPDATE pages
        SET page_text = %(page_text)s, type_page = 'ocr'
        WHERE page_id = %(page_id)s AND type_page = 'scan'
        """,
        {"page_id": page_id, "page_text": text},
    )

def get_scan_page(cur):
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

def render_page(pdf_path, page_number):
    with pymupdf.open(pdf_path) as pdf:
        if page_number < 1 or page_number > len(pdf):
            raise ValueError(f"Halaman {page_number} tidak ada dalam file {pdf_path}")
        page = pdf[page_number - 1]
        pix = page.get_pixmap(dpi=OCR_DPI)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image

def ocr_pending_page():
    skipped = 0
    done = 0
    checked_files = set()
    with get_connection() as conn:
        with conn.cursor() as cur:
            scan_pages = get_scan_page(cur)
            if not scan_pages:
                print("Tidak ada halaman scan yang perlu di-ocr.")
                return
            for page_id, file_hash, file_name, page_number in scan_pages:
                try:
                    pdf_path = RAW_DIR / f"{file_name}.pdf"
                    if not pdf_path.exists():
                        raise FileNotFoundError(f"File PDF tidak ditemukan: {pdf_path}")
                    if file_name not in checked_files:
                        if hash_file(pdf_path) != file_hash:
                            raise ValueError(f"File PDF telah berubah: {pdf_path}")
                    checked_files.add(file_name)
                    text = ocr_image(render_page(pdf_path, page_number)).strip()
                    if len(text) < OCR_MIN_CHARS:
                        print(f"Halaman {page_number} dari {file_name} tidak memiliki cukup teks setelah OCR.")
                        skipped += 1
                        continue
                    if update_page(cur, page_id, text) == 0:
                        print(f"Berhasil melakukan OCR pada halaman {page_number} dari {file_name}.")
                        skipped += 1
                        continue
                    conn.commit()
                    done += 1
                    print(f"Berhasil melakukan OCR pada halaman {page_number} dari {file_name}.")
                except Exception as e:
                    conn.rollback()
                    print(f"Gagal melakukan OCR pada halaman {page_number} dari {file_name}: {e}")
    print(f"OCR selesai. Berhasil: {done}, Dilewati: {skipped}")

if __name__ == "__main__":
    ocr_pending_page()
