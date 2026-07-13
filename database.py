import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',         # Utente di default di MySQL
        password='Altieri3807',         # Metti la tua password di MySQL Workbench (se l'hai messa, altrimenti lascia vuoto '')
        database='social_film_db' # Il nome del database che useremo
    )
    return connection