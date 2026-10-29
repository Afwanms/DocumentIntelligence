import pandas as pd
import pymupdf
from config import RAW_DIR

MIN_CHARS = 10

def classify_page(page, text):
    char_count = len(text.strip())
    if char_count < MIN_CHARS:
        if page.get_images():
            return "scan"
        else:
            return "kosong"
    return "digital"

def parse_pdf(path):
    pages = []
    problem_pages = []
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text()
            category = classify_page(page, text)
            pages.append((page_number, text, category))
            if category != "digital":
                problem_pages.append((page_number, category))
    return pages, problem_pages
    
def main():
    rows = []
    for pdf_path in sorted(RAW_DIR.glob("*.pdf")):
        try:
            pages, problem_pages = parse_pdf(pdf_path)
        except Exception as e:
            print(f"GAGAL: {pdf_path.name} -> {e}")
            rows.append({"nama_file": pdf_path.stem, "status": "gagal"})
            continue
        rows.append({
            "nama_file": pdf_path.stem,
            "status": "ok",
            "jumlah_halaman": len(pages),
            "halaman_kosong": [n for n, kategori in problem_pages if kategori == "kosong"],
            "halaman_scan": [n for n, kategori in problem_pages if kategori == "scan"],
        })

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

if __name__ == "__main__":
    main()