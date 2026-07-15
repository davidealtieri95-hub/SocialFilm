import os
import random
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

# 🏠 1. HOME FEED (Con Carosello dei Film di Tendenza & Classifica)
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
    if utente_loggato_id:
        cursor.execute("SELECT id_film FROM watchlist WHERE id_utente = %s", (utente_loggato_id,))
        watchlist_id_film = [r['id_film'] for r in cursor.fetchall()]
    
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
        utente_loggato=session.get('nickname'),
        id_utente_loggato=utente_loggato_id,
        leaderboard=leaderboard
    )


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
            cursor.execute("INSERT INTO film (titolo, immagine) VALUES (%s, %s)", (titolo_tmdb, locandina_tmdb))
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
            cursor.execute("INSERT INTO film (titolo, immagine) VALUES (%s, %s)", (titolo, locandina))
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


# 👤 4. PAGINE PROFILO CON STATISTICHE & WATCHLIST
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
        id_utente_loggato=session.get('id_utente')
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
        # ✅ RISOLTO: Sostituito il vecchio WHERE errato con la sintassi INSERT corretta
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
    # 💥 VERIFICA/CREAZIONE TABELLA HYPE NEL TUO DB ATTUALE
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hype_voti (
            id_voto INT AUTO_INCREMENT PRIMARY KEY,
            id_film_tmdb INT NOT NULL,
            titolo_film VARCHAR(200) NOT NULL,
            livello VARCHAR(20) NOT NULL
        );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Tabella 'hype_voti' controllata/creata con successo nel tuo database!")
    except Exception as e:
        print(f"⚠️ Impossibile verificare la tabella hype_voti: {e}")

    # Gestione dinamica e sicura del Debug basata sul file .env
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=is_debug)