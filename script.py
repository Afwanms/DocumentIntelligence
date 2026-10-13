from pathlib import Path

import pandas as pd
import pymupdf

RAW_DIR = Path("Data/Raw")
PROCESSED_DIR = Path("Data/Processed")
MIN_CHARS = 10


def parse_pdf(path):
    pages = []
    problem_pages = []
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text()
            pages.append((page_number, text))
            category = classify_page(page, text)
            if category != "Ok":
                problem_pages.append((page_number, category))
    return pages, problem_pages


def save_text(pages, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for page_number, text in pages:
            f.write(f"=== Halaman {page_number} ===\n")
            f.write(text)
            f.write("\n\n")


def classify_page(page, text):
    char_count = len(text.strip())
    if char_count < MIN_CHARS:
        if page.get_images():
            return "Scan"
        else:
            return "Kosong"
    return "Ok"
    
def main():
    rows = []
    for pdf_path in sorted(RAW_DIR.glob("*.pdf")):
        try:
            pages, problem_pages = parse_pdf(pdf_path)
        except Exception as e:
            print(f"GAGAL: {pdf_path.name} -> {e}")
            rows.append({"nama_file": pdf_path.stem, "status": "gagal"})
            continue
        save_text(pages, PROCESSED_DIR / f"{pdf_path.stem}.txt")
        rows.append({
            "nama_file": pdf_path.stem,
            "status": "ok",
            "jumlah_halaman": len(pages),
            "halaman_kosong": [n for n, kategori in problem_pages if kategori == "Kosong"],
            "halaman_scan": [n for n, kategori in problem_pages if kategori == "Scan"],
        })

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))
    summary.to_csv(PROCESSED_DIR / "parse_summary.csv", index=False)


if __name__ == "__main__":
    main()