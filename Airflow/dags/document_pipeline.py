from airflow.sdk import dag, task
from ocr_step import ocr_pending_pages
from loader import load_all_documents

@dag(dag_id="ojk_pipeline", schedule=None)
def ojk_pipeline():
    @task
    def load_documents():
        return load_all_documents()

    @task
    def ocr_pages():
        return ocr_pending_pages()

    load_documents() >> ocr_pages()

ojk_pipeline()