from airflow.sdk import dag, task      # lihat catatan versi di bawah

@dag(dag_id="hello_dag", schedule=None)
def hello_dag():
    @task
    def say_hello():
        print("Hello, Airflow!")

    @task
    def say_done():
        print("Done!")
        
    say_hello() >> say_done()

hello_dag()