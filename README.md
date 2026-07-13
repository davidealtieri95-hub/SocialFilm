# 🎬 SocialFilm

SocialFilm è un'applicazione web social dedicata ai cinefili. Gli utenti possono registrarsi, cercare film tramite l'API di TMDB, recensire pellicole, assegnare voti dettagliati, commentare e mettere "Like" ai post altrui, seguire altri utenti e gestire la propria Watchlist personale.

Include anche funzionalità speciali come la **Roulette del Cinema** (per scegliere un film casuale in base al genere) e la bacheca **Hype Movies** (per i film in arrivo nelle sale).

---

## 🛠️ Tecnologie Utilizzate

*   **Backend:** Python 3 (Flask)
*   **Database:** MySQL (strutturato con tabelle relazionali e vincoli d'integrità `ON DELETE CASCADE`)
*   **API Esterna:** The Movie Database (TMDB) API v3
*   **Sicurezza:** Criptazione delle password tramite `werkzeug.security` (PBKDF2) e isolamento delle chiavi sensibili con variabili d'ambiente (`python-dotenv`).

---

## 🗄️ Struttura del Database (Schema SQL)

Il database si chiama `socialfilm`. Di seguito lo schema DDL completo per rigenerare la struttura su MySQL Workbench:

```sql
CREATE DATABASE IF NOT EXISTS socialfilm DEFAULT CHARACTER SET utf8mb4;
USE socialfilm;

CREATE TABLE IF NOT EXISTS utenti (
    id_utente INT AUTO_INCREMENT PRIMARY KEY,
    nickname VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    data_di_nascita DATE,
    avatar VARCHAR(50) DEFAULT '🍿'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS film (
    id_film INT AUTO_INCREMENT PRIMARY KEY,
    titolo VARCHAR(255) NOT NULL,
    immagine TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS post (
    id_post INT AUTO_INCREMENT PRIMARY KEY,
    id_utente INT,
    id_film INT,
    didascalia TEXT NOT NULL,
    voto_utente INT NOT NULL,
    contatore_like INT DEFAULT 0,
    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(id_utente) REFERENCES utenti(id_utente) ON DELETE CASCADE,
    FOREIGN KEY(id_film) REFERENCES film(id_film) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS likes (
    id_utente INT,
    id_post INT,
    PRIMARY KEY (id_utente, id_post),
    FOREIGN KEY(id_utente) REFERENCES utenti(id_utente) ON DELETE CASCADE,
    FOREIGN KEY(id_post) REFERENCES post(id_post) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS commenti (
    id_commento INT AUTO_INCREMENT PRIMARY KEY,
    id_post INT,
    id_utente INT,
    testo TEXT NOT NULL,
    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(id_post) REFERENCES post(id_post) ON DELETE CASCADE,
    FOREIGN KEY(id_utente) REFERENCES utenti(id_utente) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS segui (
    id_seguitore INT,
    id_seguito INT,
    PRIMARY KEY (id_seguitore, id_seguito),
    FOREIGN KEY(id_seguitore) REFERENCES utenti(id_utente) ON DELETE CASCADE,
    FOREIGN KEY(id_seguito) REFERENCES utenti(id_utente) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS watchlist (
    id_utente INT,
    id_film INT,
    PRIMARY KEY (id_utente, id_film),
    FOREIGN KEY(id_utente) REFERENCES utenti(id_utente) ON DELETE CASCADE,
    FOREIGN KEY(id_film) REFERENCES film(id_film) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hype_voti (
    id_voto INT AUTO_INCREMENT PRIMARY KEY,
    id_film_tmdb INT NOT NULL,
    titolo_film VARCHAR(200) NOT NULL,
    livello VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

---

## 🚀 Installazione e Avvio Locale

Per far girare il progetto sul tuo computer, segui questi passaggi:

1. **Clona il repository:**
   ```bash
   git clone [https://github.com/IL_TUO_NOME_UTENTE/SocialFilm.git](https://github.com/IL_TUO_NOME_UTENTE/SocialFilm.git)
   cd SocialFilm
   CREA AMBIENTE VIRTUALE
python -m venv venv
# Attiva (Windows):
.\venv\Scripts\activate
# Attiva (Mac/Linux):
source venv/bin/activate

Installa le dipendenze:

pip install -r requirements.txt

Configura il file .env

TMDB_API_KEY=LaTuaChiaveAPI
FLASK_SECRET_KEY=LaTuaChiaveSegreta
FLASK_DEBUG=True

Avvio

python app.py

