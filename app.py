import os
import random
import datetime
from datetime import date
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

app = Flask(__name__)

# 🔐 CHIAVI PROTETTE (Prese dal file .env)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'chiave-di-emergenza-locale-bomber')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# 📅 DATABASE SCONTRI DEL GIORNO (Predefiniti)
SCONTRI_DEL_GIORNO = [
    {"film_a": "Interstellar 🚀", "film_b": "Inception 🌀"},
    {"film_a": "Pulp Fiction 🍔", "film_b": "Fight Club 🧼"},
    {"film_a": "Il Cavaliere Oscuro 🦇", "film_b": "Spider-Man 2 🕷️"},
    {"film_a": "The Matrix 🕶️", "film_b": "Avatar 🌊"},
    {"film_a": "Il Signore degli Anelli 💍", "film_b": "Harry Potter ⚡"},
    {"film_a": "Ritorno al Futuro 🚗", "film_b": "Star Wars V 🌌"},
    {"film_a": "Titanic 🚢", "film_b": "La La Land 🎹"},
    {"film_a": "Shutter Island 🏝️", "film_b": "Se7en 📦"},
    {"film_a": "Django Unchained 🤠", "film_b": "Bastardi Senza Gloria 🪖"},
    {"film_a": "Alien 👽", "film_b": "La Cosa ❄️"},
    {"film_a": "Il Gladiatore ⚔️", "film_b": "Braveheart 🏴󠁧󠁢󠁳󠁣󠁴󠁿"},
    {"film_a": "Joker 🤡", "film_b": "Taxi Driver 🚕"},
    {"film_a": "The Truman Show 📺", "film_b": "Eternal Sunshine 🧠"}
]

def get_scontro_odierno():
    today = date.today()
    day_num = today.timetuple().tm_yday
    idx = day_num % len(SCONTRI_DEL_GIORNO)
    return SCONTRI_DEL_GIORNO[idx], today

# 🏠 1. HOME FEED (Con Carosello dei Film di Tendenza, Classifica & Scontro del Giorno)
@app.route('/')
def home():
    search_query = request.args.get('search', '')
    feed_filter = request.args.get('feed', 'all')
    utente_loggato_id = session.get('id_utente')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 🔥 RECUPERO FILM DI TENDENZA DA TMDB PER IL CAROSELLO
    trending_movies = []
    try:
        url_trending = f"{TMDB_BASE_URL}/trending/movie/day"
        risposta = requests.get(url_trending, params={'api_key': TMDB_API_KEY, 'language': 'it-IT'})
        if risposta.status_code == 200:
            dati_t = risposta.json()
            for film in dati_t.get('results', [])[:10]:
                id_copertina = film.get('poster_path')
                trending_movies.append({
                    'titolo': film.get('title'),
                    'locandina': f"https://image.tmdb.org/t/p/w500{id_copertina}" if id_copertina else "https://via.placeholder.com/500x750?text=No+Cover",
                    'anno': film.get('release_date', '')[:4] if film.get('release_date') else 'N.D.'
                })
    except Exception as e:
        print(f"Errore caricamento trending: {e}")

    # 👑 CLASSIFICA "RE DEL POPCORN" (Top 5 utenti per numero di post)
    leaderboard = []
    try:
        query_leaderboard = """
        SELECT utenti.id_utente, utenti.nickname, utenti.avatar, COUNT(post.id_post) AS post_count
        FROM utenti
        LEFT JOIN post ON utenti.id_utente = post.id_utente
        GROUP BY utenti.id_utente
        ORDER BY post_count DESC
        LIMIT 5;
        """
        cursor.execute(query_leaderboard)
        leaderboard = cursor.fetchall()
    except Exception as e:
        print(f"Errore caricamento leaderboard: {e}")

    # 🗳️ RECUPERO SCONTRO DEL GIORNO
    scontro_oggi, data_oggi = get_scontro_odierno()
    voti_a, voti_b = 0, 0
    scelta_utente = None
    try:
        cursor.execute("SELECT scelta, COUNT(*) as tot FROM scontro_voti WHERE data_voto = %s GROUP BY scelta", (data_oggi,))
        voti_rows = cursor.fetchall()
        for row in voti_rows:
            if row['scelta'] == 'A': voti_a = row['tot']
            elif row['scelta'] == 'B': voti_b = row['tot']
            
        if utente_loggato_id:
            cursor.execute("SELECT scelta FROM scontro_voti WHERE id_utente = %s AND data_voto = %s", (utente_loggato_id, data_oggi))
            voto_user = cursor.fetchone()
            if voto_user: scelta_utente = voto_user['scelta']
    except Exception as e:
        print(f"Errore caricamento scontro del giorno: {e}")
        
    tot_voti_scontro = voti_a + voti_b
    perc_a = round((voti_a / tot_voti_scontro) * 100) if tot_voti_scontro > 0 else 50
    perc_b = round((voti_b / tot_voti_scontro) * 100) if tot_voti_scontro > 0 else 50

    id_seguiti = []
    if utente_loggato_id:
        cursor.execute("SELECT id_seguito FROM segui WHERE id_seguitore = %s", (utente_loggato_id,))
        id_seguiti = [row['id_seguito'] for row in cursor.fetchall()]

    query_base = """
    SELECT post.id_post, post.id_utente, post.id_film, utenti.nickname, utenti.avatar, 
           film.titolo, film.immagine AS locandina, post.didascalia, post.voto_utente, post.contatore_like
    FROM post
    JOIN utenti ON post.id_utente = utenti.id_utente
    JOIN film ON post.id_film = film.id_film
    """
    
    parametri = []
    condizioni = []

    if feed_filter == 'seguiti' and utente_loggato_id:
        if id_seguiti:
            placeholders = ','.join(['%s'] * len(id_seguiti))
            condizioni.append(f"post.id_utente IN ({placeholders})")
            parametri.extend(id_seguiti)
        else:
            condizioni.append("1=0")

    if search_query:
        condizioni.append("(film.titolo LIKE %s OR utenti.nickname LIKE %s)")
        parametri.extend([f"%{search_query}%", f"%{search_query}%"])

    if condizioni:
        query_base += " WHERE " + " AND ".join(condizioni)
        
    query_base += " ORDER BY post.data_creazione DESC;"
    
    cursor.execute(query_base, tuple(parametri))
    tutti_i_post = cursor.fetchall()
    
    cursor.execute("SELECT id_film, titolo FROM film ORDER BY titolo ASC;")
    tutti_i_film = cursor.fetchall()
    
    query_commenti = """
    SELECT commenti.id_commento, commenti.id_post, commenti.testo, utenti.nickname
    FROM commenti
    JOIN utenti ON commenti.id_utente = utenti.id_utente
    ORDER BY commenti.data_creazione ASC;
    """
    cursor.execute(query_commenti)
    tutti_i_commenti = cursor.fetchall()
    
    commenti_per_post = {}
    for commento in tutti_i_commenti:
        id_p = commento['id_post']
        if id_p not in commenti_per_post:
            commenti_per_post[id_p] = []
        commenti_per_post[id_p].append(commento)
        
    watchlist_id_film = []
    post_piaciuti = [] 
    if utente_loggato_id:
        cursor.execute("SELECT id_film FROM watchlist WHERE id_utente = %s", (utente_loggato_id,))
        watchlist_id_film = [r['id_film'] for r in cursor.fetchall()]
        
        # Recupera gli ID dei post a cui l'utente loggato ha già messo Like
        cursor.execute("SELECT id_post FROM likes WHERE id_utente = %s", (utente_loggato_id,))
        post_piaciuti = [r['id_post'] for r in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template(
        'index.html',
        posts=tutti_i_post,
        films=tutti_i_film,
        commenti_per_post=commenti_per_post,
        search_query=search_query,
        feed_filter=feed_filter,
        id_seguiti=id_seguiti,
        trending_movies=trending_movies,
        watchlist_ids=watchlist_id_film,
        post_piaciuti=post_piaciuti, 
        utente_loggato=session.get('nickname'),
        id_utente_loggato=utente_loggato_id,
        leaderboard=leaderboard,
        scontro=scontro_oggi,          # 👈 RISOLTO: Rinominato da 'scontro_oggi' a 'scontro' per combaciare con index.html
        scelta_utente=scelta_utente,
        perc_a=perc_a,
        perc_b=perc_b,
        tot_voti_scontro=tot_voti_scontro
    )


# 🗳️ REGISTRA VOTO SCONTRO DEL GIORNO
@app.route('/vota_scontro', methods=['POST'])
def vota_scontro():
    if 'id_utente' not in session:
        return redirect(url_for('login'))
    
    id_utente = session['id_utente']
    scelta = request.form.get('scelta')
    if scelta not in ['A', 'B']:
        return "Scelta non valida", 400
        
    _, data_oggi = get_scontro_odierno()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO scontro_voti (id_utente, data_voto, scelta) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE scelta = %s",
            (id_utente, data_oggi, scelta, scelta)
        )
        conn.commit()
    except Exception as e:
        print(f"Errore voto scontro: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('home'))


# 🏆 GIOCO CINE-CUP: TORNEO 16 FILM
@app.route('/cinecup', methods=['GET', 'POST'])
def cinecup():
    if 'id_utente' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'GET' and 'continue' not in request.args:
        # Inizializziamo il torneo con 16 film famosi da TMDB
        films = []
        try:
            res = requests.get(f"{TMDB_BASE_URL}/movie/popular", params={'api_key': TMDB_API_KEY, 'language': 'it-IT', 'page': random.randint(1, 3)})
            if res.status_code == 200:
                results = res.json().get('results', [])
                random.shuffle(results)
                for f in results[:16]:
                    id_copertina = f.get('poster_path')
                    films.append({
                        'id_tmdb': f.get('id'),
                        'titolo': f.get('title'),
                        'locandina': f"https://image.tmdb.org/t/p/w500{id_copertina}" if id_copertina else "https://via.placeholder.com/500x750?text=No+Cover"
                    })
        except Exception as e:
            print(f"Errore caricamento cinecup TMDB: {e}")
            
        # Se TMDB ha problemi, usiamo un elenco di emergenza di 16 capolavori
        if len(films) < 16:
            emergenza = ["Inception", "Interstellar", "Pulp Fiction", "The Matrix", "Il Gladiatore", "Avatar", "Fight Club", "Joker", "Seven", "Shutter Island", "Django Unchained", "Titanic", "Memento", "Alien", "I Soliti Sospetti", "The Departed"]
            films = [{'id_tmdb': i, 'titolo': tit, 'locandina': "https://via.placeholder.com/500x750?text=" + tit.replace(" ", "+")} for i, tit in enumerate(emergenza)]
            
        matches = [[films[i], films[i+1]] for i in range(0, 16, 2)]
        session['cinecup_matches'] = matches
        session['cinecup_current_match'] = 0
        session['cinecup_next_round'] = []
        session['cinecup_round_name'] = "Ottavi di Finale ⚔️"
        
    # Se POST, processa il voto per il scontro corrente
    if request.method == 'POST':
        vincitore_id = int(request.form.get('vincitore_id'))
        matches = session.get('cinecup_matches', [])
        current_match_idx = session.get('cinecup_current_match', 0)
        next_round = session.get('cinecup_next_round', [])
        
        current_match = matches[current_match_idx]
        vincitore_film = current_match[0] if current_match[0]['id_tmdb'] == vincitore_id else current_match[1]
        next_round.append(vincitore_film)
        session['cinecup_next_round'] = next_round
        
        current_match_idx += 1
        session['cinecup_current_match'] = current_match_idx
        
        # Finito il round corrente?
        if current_match_idx >= len(matches):
            if len(next_round) == 1:
                session['cinecup_winner'] = next_round[0]
                return redirect(url_for('cinecup_winner_page'))
                
            # Prepara il prossimo round
            new_matches = [[next_round[i], next_round[i+1]] for i in range(0, len(next_round), 2)]
            session['cinecup_matches'] = new_matches
            session['cinecup_current_match'] = 0
            session['cinecup_next_round'] = []
            
            r_len = len(new_matches)
            if r_len == 4: session['cinecup_round_name'] = "Quarti di Finale ⚔️"
            elif r_len == 2: session['cinecup_round_name'] = "Semifinali 🔥"
            elif r_len == 1: session['cinecup_round_name'] = "Finalissima 👑"
            
    matches = session.get('cinecup_matches', [])
    current_match_idx = session.get('cinecup_current_match', 0)
    film_a = matches[current_match_idx][0]
    film_b = matches[current_match_idx][1]
    
    return render_template(
        'cinecup.html',
        film_a=film_a,
        film_b=film_b,
        match_num=current_match_idx + 1,
        tot_matches=len(matches),
        round_name=session.get('cinecup_round_name')
    )


# 🏆 VINCITORE CINE-CUP & PUBBLICAZIONE POST AUTOMATICO
@app.route('/cinecup/vincitore', methods=['GET', 'POST'])
def cinecup_winner_page():
    if 'id_utente' not in session or 'cinecup_winner' not in session:
        return redirect(url_for('home'))
        
    winner = session['cinecup_winner']
    
    if request.method == 'POST':
        id_utente = session['id_utente']
        didascalia = f"🏆 Ho completato il torneo Cine-Cup ed il mio film vincitore indiscusso è: {winner['titolo']}! Che capolavoro totale! Voi siete d'accordo? 🍿🎬"
        voto_utente = 10
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_film FROM film WHERE titolo = %s", (winner['titolo'],))
        film_locale = cursor.fetchone()
        
        if film_locale:
            id_film = film_locale['id_film']
        else:
            # Recuperiamo un genere verosimile per il vincitore
            genere_film = "Film"
            try:
                res_cerca = requests.get(f"{TMDB_BASE_URL}/search/movie", params={'api_key': TMDB_API_KEY, 'query': winner['titolo'], 'language': 'it-IT'})
                if res_cerca.status_code == 200:
                    results = res_cerca.json().get('results', [])
                    if results and results[0].get('genre_ids'):
                        mappa_generi = {28: "Azione", 12: "Avventura", 16: "Animazione", 35: "Commedia", 80: "Crime", 18: "Dramma", 27: "Horror", 10749: "Romantico", 878: "Fantascienza", 53: "Thriller", 14: "Fantasy"}
                        genere_film = mappa_generi.get(results[0]['genre_ids'][0], "Film")
            except: pass
            
            cursor.execute("INSERT INTO film (titolo, immagine, genere) VALUES (%s, %s, %s)", (winner['titolo'], winner['locandina'], genere_film))
            conn.commit()
            id_film = cursor.lastrowid
            
        cursor.execute(
            "INSERT INTO post (id_utente, id_film, didascalia, voto_utente) VALUES (%s, %s, %s, %s)", 
            (id_utente, id_film, didascalia, voto_utente)
        )
        conn.commit()
        cursor.close(); conn.close()
        
        # Pulisce la sessione di gioco
        session.pop('cinecup_winner', None)
        return redirect(url_for('home'))
        
    return render_template('cinecup_winner.html', winner=winner)


# 🎲 ROULETTE DEL CINEMA (Cosa guardo stasera?)
@app.route('/roulette', methods=['GET', 'POST'])
def roulette():
    movie_scelto = None
    generi = {
        "28": "Azione", "12": "Avventura", "35": "Commedia", 
        "27": "Horror", "878": "Sci-Fi", "1074": "Romantico"
    }
    
    if request.method == 'POST':
        genere_id = request.form.get('genere')
        url = f"{TMDB_BASE_URL}/discover/movie"
        params = {
            "api_key": TMDB_API_KEY,
            "with_genres": genere_id,
            "vote_average.gte": 7.0,
            "language": "it-IT",
            "page": random.randint(1, 3)
        }
        try:
            res = requests.get(url, params=params)
            if res.status_code == 200:
                film_list = res.json().get('results', [])
                if film_list:
                    movie_scelto = random.choice(film_list)
        except Exception as e:
            print(f"Errore roulette: {e}")
            
    return render_template('roulette.html', generi=generi, movie=movie_scelto)


# 🗓️ BACHECA "HYPE MOVIE" (Film in arrivo)
@app.route('/hype')
def hype_board():
    url = f"{TMDB_BASE_URL}/movie/upcoming"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "it-IT",
        "region": "IT"
    }
    upcoming_movies = []
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            upcoming_movies = res.json().get('results', [])[:8]
    except Exception as e:
        print(f"Errore caricamento hype: {e}")
        
    voti_hype = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        for movie in upcoming_movies:
            m_id = movie['id']
            cursor.execute("SELECT livello, COUNT(*) as tot FROM hype_voti WHERE id_film_tmdb = %s GROUP BY livello", (m_id,))
            rows = cursor.fetchall()
            
            counts = {"Basso": 0, "Medio": 0, "Fuori di testa!": 0}
            for row in rows:
                if row['livello'] in counts:
                    counts[row['livello']] = row['tot']
            voti_hype[m_id] = counts
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Errore conteggio voti hype: {e}")
        
    return render_template('hype.html', movies=upcoming_movies, voti=voti_hype)


# 🗳️ REGISTRA VOTO HYPE
@app.route('/vote_hype/<int:movie_id>', methods=['POST'])
def vote_hype(movie_id):
    level = request.form.get('level')
    title = request.form.get('title')
    if level and title:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO hype_voti (id_film_tmdb, titolo_film, livello) VALUES (%s, %s, %s)",
                (movie_id, title, level)
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Errore inserimento voto hype: {e}")
    return redirect(url_for('hype_board'))


# ✍️ 2. CREA POST
@app.route('/create_post', methods=['POST'])
def create_post():
    if 'id_utente' not in session:
        return redirect(url_for('login'))
        
    id_utente = session['id_utente']
    didascalia = request.form['didascalia']
    voto_utente = request.form['voto_utente']
    
    id_film = request.form.get('id_film')
    titolo_tmdb = request.form.get('titolo_film_tmdb')
    locandina_tmdb = request.form.get('locandina_film_tmdb')
    
    if not id_film and not titolo_tmdb:
        return "<h3>Errore: Seleziona un film prima di pubblicare!</h3><br><a href='/'>Indietro</a>", 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if titolo_tmdb:
        cursor.execute("SELECT id_film FROM film WHERE titolo = %s", (titolo_tmdb,))
        film_locale = cursor.fetchone()
        
        if film_locale:
            id_film = film_locale['id_film']
        else:
            # 🧠 Dynamic Genre Fetcher: Recupera il genere da TMDB per la statistica dei profili
            genere_film = "Dramma" # Default sicuro
            try:
                res_cerca = requests.get(f"{TMDB_BASE_URL}/search/movie", params={'api_key': TMDB_API_KEY, 'query': titolo_tmdb, 'language': 'it-IT'})
                if res_cerca.status_code == 200:
                    results = res_cerca.json().get('results', [])
                    if Math_gen := results[0].get('genre_ids'):
                        mappa_generi = {28: "Azione", 12: "Avventura", 16: "Animazione", 35: "Commedia", 80: "Crime", 18: "Dramma", 27: "Horror", 10749: "Romantico", 878: "Fantascienza", 53: "Thriller", 14: "Fantasy"}
                        genere_film = mappa_generi.get(Math_gen[0], "Film")
            except: pass
            
            cursor.execute("INSERT INTO film (titolo, immagine, genere) VALUES (%s, %s, %s)", (titolo_tmdb, locandina_tmdb, genere_film))
            conn.commit()
            id_film = cursor.lastrowid
            
    cursor.execute(
        "INSERT INTO post (id_utente, id_film, didascalia, voto_utente) VALUES (%s, %s, %s, %s)", 
        (id_utente, id_film, didascalia, voto_utente)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('home'))


# 📌 3. INTERACTION WATCHLIST
@app.route('/toggle_watchlist', methods=['POST'])
def toggle_watchlist():
    if 'id_utente' not in session:
        return {"error": "Devi effettuare il login"}, 401
        
    id_utente = session['id_utente']
    id_film = request.form.get('id_film')
    titolo = request.form.get('titolo')
    locandina = request.form.get('locandina')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if not id_film and titolo:
        cursor.execute("SELECT id_film FROM film WHERE titolo = %s", (titolo,))
        f_locale = cursor.fetchone()
        if f_locale:
            id_film = f_locale['id_film']
        else:
            # dynamic genre
            genere_film = "Dramma"
            try:
                res_cerca = requests.get(f"{TMDB_BASE_URL}/search/movie", params={'api_key': TMDB_API_KEY, 'query': titolo, 'language': 'it-IT'})
                if res_cerca.status_code == 200:
                    results = res_cerca.json().get('results', [])
                    if results and results[0].get('genre_ids'):
                        mappa_generi = {28: "Azione", 12: "Avventura", 16: "Animazione", 35: "Commedia", 80: "Crime", 18: "Dramma", 27: "Horror", 10749: "Romantico", 878: "Fantascienza", 53: "Thriller", 14: "Fantasy"}
                        genere_film = mappa_generi.get(results[0]['genre_ids'][0], "Film")
            except: pass
            
            cursor.execute("INSERT INTO film (titolo, immagine, genere) VALUES (%s, %s, %s)", (titolo, locandina, genere_film))
            conn.commit()
            id_film = cursor.lastrowid

    if not id_film:
        return {"error": "Film non valido"}, 400
        
    cursor.execute("SELECT * FROM watchlist WHERE id_utente = %s AND id_film = %s", (id_utente, id_film))
    esistente = cursor.fetchone()
    
    if esistente:
        cursor.execute("DELETE FROM watchlist WHERE id_utente = %s AND id_film = %s", (id_utente, id_film))
        stato = "rimosso"
    else:
        cursor.execute("INSERT INTO watchlist (id_utente, id_film) VALUES (%s, %s)", (id_utente, id_film))
        stato = "aggiunto"
        
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": stato, "id_film": id_film}


# 👤 4. PAGINE PROFILO CON STATISTICHE, WATCHLIST & BADGE GENERI
@app.route('/profilo')
def mio_profilo():
    if 'id_utente' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('profilo_utente', id_utente=session['id_utente']))

@app.route('/profilo/<int:id_utente>')
def profilo_utente(id_utente):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id_utente, nickname, email, data_di_nascita, avatar FROM utenti WHERE id_utente = %s", (id_utente,))
    dati_utente = cursor.fetchone()
    if not dati_utente:
        cursor.close()
        conn.close()
        return "Utente non trovato", 404
        
    cursor.execute("SELECT COUNT(*) as tot, AVG(voto_utente) as media FROM post WHERE id_utente = %s", (id_utente,))
    res_stats = cursor.fetchone()
    tot_post = res_stats['tot'] or 0
    voto_medio = round(res_stats['media'], 1) if res_stats['media'] else 0.0
    
    if tot_post >= 15:
        badge = "Regista Premio Oscar 🏆"
    elif tot_post >= 5:
        badge = "Cinefilo Avanzato 🎬"
    else:
        badge = "Spettatore Serale 🍿"
        
    # 🏅 GENERI PREFERITI & BADGE DI GENERE DINAMICI
    generi_pref = []
    badges_generi = []
    try:
        cursor.execute("""
            SELECT film.genere, COUNT(*) as tot 
            FROM post 
            JOIN film ON post.id_film = film.id_film 
            WHERE post.id_utente = %s AND film.genere IS NOT NULL AND film.genere != ''
            GROUP BY film.genere
            ORDER BY tot DESC
        """, (id_utente,))
        generi_count = cursor.fetchall()
        
        # Estraiamo i generi preferiti principali
        generi_pref = [f"{g['genere']} ({g['tot']} post)" for g in generi_count[:3]]
        
        # Mappa per l'assegnazione dei super-badge di genere (minimo 3 recensioni dello stesso genere)
        diz_generi = {g['genere']: g['tot'] for g in generi_count}
        if diz_generi.get('Horror', 0) >= 3: badges_generi.append("Scream Queen 🔪")
        if diz_generi.get('Fantascienza', 0) >= 3: badges_generi.append("Esploratore dello Spazio 🚀")
        if diz_generi.get('Azione', 0) >= 3: badges_generi.append("Stuntman Professionista 💥")
        if diz_generi.get('Commedia', 0) >= 3: badges_generi.append("Re della Risata 🤡")
        if diz_generi.get('Dramma', 0) >= 3: badges_generi.append("Anima Sensibile 🎭")
        if diz_generi.get('Thriller', 0) >= 3: badges_generi.append("Agente Segreto 🕵️‍♂️")
        if diz_generi.get('Romantico', 0) >= 3: badges_generi.append("Cuore Incurabile 💖")
    except Exception as e:
        print(f"Errore calcolo badge generi: {e}")
        
    cursor.execute("SELECT COUNT(*) as tot FROM segui WHERE id_seguito = %s", (id_utente,))
    follower_count = cursor.fetchone()['tot']
    
    cursor.execute("SELECT COUNT(*) as tot FROM segui WHERE id_seguitore = %s", (id_utente,))
    following_count = cursor.fetchone()['tot']
    
    sta_seguendo = False
    if 'id_utente' in session:
        cursor.execute("SELECT * FROM segui WHERE id_seguitore = %s AND id_seguito = %s", (session['id_utente'], id_utente))
        if cursor.fetchone():
            sta_seguendo = True

    query_miei_post = """
    SELECT post.id_post, film.titolo, film.immagine AS locandina, post.didascalia, post.voto_utente, post.contatore_like
    FROM post
    JOIN film ON post.id_film = film.id_film
    WHERE post.id_utente = %s
    ORDER BY post.data_creazione DESC;
    """
    cursor.execute(query_miei_post, (id_utente,))
    miei_post = cursor.fetchall()
    
    query_watchlist = """
    SELECT film.id_film, film.titolo, film.immagine AS locandina 
    FROM watchlist
    JOIN film ON watchlist.id_film = film.id_film
    WHERE watchlist.id_utente = %s;
    """
    cursor.execute(query_watchlist, (id_utente,))
    mia_watchlist = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(
        'profilo.html',
        utente=dati_utente,
        posts=miei_post,
        watchlist=mia_watchlist,
        tot_post=tot_post,
        voto_medio=voto_medio,
        badge=badge,
        follower_count=follower_count,
        following_count=following_count,
        sta_seguendo=sta_seguendo,
        utente_loggato=session.get('nickname'),
        id_utente_loggato=session.get('id_utente'),
        generi_pref=generi_pref,
        badges_generi=badges_generi
    )

# 🔄 5. SISTEMA AVATAR EMOJI CINEMATOGRAFICI
@app.route('/scegli_avatar', methods=['POST'])
def scegli_avatar():
    if 'id_utente' not in session: 
        return redirect(url_for('login'))
        
    id_utente = session['id_utente']
    nuovo_avatar = request.form.get('personaggio')
    
    personaggi_validi = ['🍿', '🤡', '🕶️', '🤠', '🤖', '👽', '🧙‍♂️', '👑']
    
    if nuovo_avatar in personaggi_validi:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE utenti SET avatar = %s WHERE id_utente = %s", (nuovo_avatar, id_utente))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Errore database cambio avatar: {e}")
            return f"Errore: {e}", 500
            
    return redirect(url_for('mio_profilo'))

# 🔧 6. UTILITY INTERNE (EDIT, DELETE, LIKE, COMMENT, AUTH)
@app.route('/edit_post/<int:id_post>', methods=['POST'])
def edit_post(id_post):
    if 'id_utente' not in session: return redirect(url_for('login'))
    nuova_didascalia = request.form['didascalia']
    nuovo_voto = request.form['voto_utente']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_utente FROM post WHERE id_post = %s", (id_post,))
    post = cursor.fetchone()
    if post and post['id_utente'] == session['id_utente']:
        cursor.execute("UPDATE post SET didascalia = %s, voto_utente = %s WHERE id_post = %s", (nuova_didascalia, nuovo_voto, id_post))
        conn.commit()
    cursor.close(); conn.close()
    return redirect(url_for('home'))

@app.route('/delete_post/<int:id_post>', methods=['POST'])
def delete_post(id_post):
    if 'id_utente' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_utente FROM post WHERE id_post = %s", (id_post,))
    post = cursor.fetchone()
    if post and post['id_utente'] == session['id_utente']:
        cursor.execute("DELETE FROM post WHERE id_post = %s", (id_post,))
        conn.commit()
    cursor.close(); conn.close()
    return redirect(url_for('home'))

@app.route('/like/<int:id_post>', methods=['POST'])
def like_post(id_post):
    if 'id_utente' not in session: return {"error": "Devi login"}, 401
    id_utente = session['id_utente']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM likes WHERE id_utente = %s AND id_post = %s", (id_utente, id_post))
    if cursor.fetchone():
        cursor.execute("DELETE FROM likes WHERE id_utente = %s AND id_post = %s", (id_utente, id_post))
        cursor.execute("UPDATE post SET contatore_like = contatore_like - 1 WHERE id_post = %s", (id_post,))
    else:
        cursor.execute("INSERT INTO likes (id_utente, id_post) VALUES (%s, %s)", (id_utente, id_post))
        cursor.execute("UPDATE post SET contatore_like = contatore_like + 1 WHERE id_post = %s", (id_post,))
    conn.commit()
    cursor.execute("SELECT contatore_like FROM post WHERE id_post = %s", (id_post,))
    nuovo_conteggio = cursor.fetchone()['contatore_like']
    cursor.close(); conn.close()
    return {"likes": nuovo_conteggio}

@app.route('/create_comment/<int:id_post>', methods=['POST'])
def create_comment(id_post):
    if 'id_utente' not in session: return {"error": "Devi loggarti"}, 401
    id_utente = session['id_utente']
    testo_commento = request.form.get('testo')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("INSERT INTO commenti (id_post, id_utente, testo) VALUES (%s, %s, %s)", (id_post, id_utente, testo_commento))
    conn.commit()
    cursor.execute("SELECT nickname FROM utenti WHERE id_utente = %s", (id_utente,))
    utente = cursor.fetchone()
    cursor.close(); conn.close()
    return jsonify({"testo": testo_commento, "nickname": utente['nickname']})

@app.route('/follow/<int:id_utente_dest>', methods=['POST'])
def follow_user(id_utente_dest):
    if 'id_utente' not in session: return {"error": "Devi login"}, 401
    id_seguitore = session['id_utente']
    if id_seguitore == id_utente_dest: return {"error": "No self-follow"}, 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM segui WHERE id_seguitore = %s AND id_seguito = %s", (id_seguitore, id_utente_dest))
    if cursor.fetchone():
        cursor.execute("DELETE FROM segui WHERE id_seguitore = %s AND id_seguito = %s", (id_seguitore, id_utente_dest))
        stato = "unfollowed"
    else:
        cursor.execute("INSERT INTO segui (id_seguitore, id_seguito) VALUES (%s, %s)", (id_seguitore, id_utente_dest))
        stato = "followed"
    conn.commit(); cursor.close(); conn.close()
    return {"status": stato}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nickname = request.form['nickname']; email = request.form['email']
        password = request.form['password']; data_nascita = request.form['data_nascita']
        password_criptata = generate_password_hash(password)
        try:
            conn = get_db_connection(); cursor = conn.cursor()
            cursor.execute("INSERT INTO utenti (nickname, email, password, data_di_nascita) VALUES (%s, %s, %s, %s)", (nickname, email, password_criptata, data_nascita))
            conn.commit(); cursor.close(); conn.close()
            return redirect(url_for('login'))
        except: return "Errore: Nickname o Email già in uso!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']; password_inserita = request.form['password']
        conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM utenti WHERE email = %s", (email,))
        utente = cursor.fetchone(); cursor.close(); conn.close()
        if utente and check_password_hash(utente['password'], password_inserita):
            session['id_utente'] = utente['id_utente']
            session['nickname'] = utente['nickname']
            return redirect(url_for('home'))
        else: return "Credenziali errate!"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/cerca_film_api', methods=['GET'])
def cerca_film_api():
    titolo_cercato = request.args.get('query', '')
    if not titolo_cercato: return jsonify([])
    url_ricerca = f"{TMDB_BASE_URL}/search/movie"
    parametri = {'api_key': TMDB_API_KEY, 'query': titolo_cercato, 'language': 'it-IT'}
    try:
        risposta = requests.get(url_ricerca, params=parametri)
        dati = risposta.json()
        film_formattati = []
        for film in dati.get('results', [])[:5]:
            id_copertina = film.get('poster_path')
            link_locandina = f"https://image.tmdb.org/t/p/w500{id_copertina}" if id_copertina else "https://via.placeholder.com/500x750?text=No+Cover"
            film_formattati.append({'titolo': film.get('title'), 'anno': film.get('release_date', '')[:4] if film.get('release_date') else 'N.D.', 'locandina': link_locandina})
        return jsonify(film_formattati)
    except: return jsonify([]), 500

if __name__ == '__main__':
    # 💥 VERIFICA/CREAZIONE TABELLE NEL TUO DB ATTUALE (Hype, Scontro del Giorno e colonna Genere)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabella Hype
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hype_voti (
            id_voto INT AUTO_INCREMENT PRIMARY KEY,
            id_film_tmdb INT NOT NULL,
            titolo_film VARCHAR(200) NOT NULL,
            livello VARCHAR(20) NOT NULL
        );
        """)
        
        # Tabella Scontro del Giorno
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scontro_voti (
            id_voto INT AUTO_INCREMENT PRIMARY KEY,
            id_utente INT NOT NULL,
            data_voto DATE NOT NULL,
            scelta VARCHAR(10) NOT NULL,
            UNIQUE KEY un_voto_al_giorno (id_utente, data_voto)
        );
        """)
        
        # Tentativo silenzioso di aggiornare la tabella dei Film con il campo 'genere'
        try:
            cursor.execute("ALTER TABLE film ADD COLUMN genere VARCHAR(100);")
        except Exception:
            pass # Se esiste già, andiamo avanti tranquilli
            
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database sincronizzato correttamente con tutte le nuove tabelle!")
    except Exception as e:
        print(f"⚠️ Impossibile sincronizzare il database: {e}")

    # Gestione dinamica e sicura del Debug basata sul file .env
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=is_debug)