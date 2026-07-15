import mysql.connector
import os
from dotenv import load_dotenv

# Carichiamo le variabili dal .env
load_dotenv()

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=os.getenv('DB_PORT'),
            # Alcuni provider cloud richiedono SSL, se dà errore prova ad aggiungere:
            # ssl_ca='ca.pem' (solo se il provider ti dà un certificato)
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Errore di connessione: {err}")
        return None