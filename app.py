from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pericia_andalucia_2026_final'
DB_NAME = 'diario_andalucia.db'

# --- CONFIGURACIÓN DE LOGIN ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, user_id_login, nombre_prensa, provincia, role):
        self.id, self.user_id_login, self.nombre_prensa, self.provincia, self.role = id, user_id_login, nombre_prensa, provincia, role

@login_manager.user_loader
def load_user(user_id):
    with conectar_db() as conn:
        u = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    return User(u['id'], u['user_id_login'], u['nombre_prensa'], u['provincia'], u['role']) if u else None

# --- UTILIDADES ---
def conectar_db():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    return conn

def generar_id_unico(nombre, provincia):
    iniciales = "".join([n[0].upper() for n in nombre.split() if n])[:3]
    prefijo = provincia[:2].upper()
    base = f"{prefijo}-{iniciales}"
    with conectar_db() as conn:
        count = conn.execute('SELECT COUNT(*) FROM usuarios WHERE user_id_login LIKE ?', (f"{base}%",)).fetchone()[0]
        return f"{base}-{str(count + 1).zfill(2)}"

def inicializar_sistema():
    with conectar_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, entradilla TEXT, contenido TEXT, 
            autor TEXT, provincia TEXT, fecha TEXT, imagen_url TEXT, pie_foto TEXT, categoria TEXT, estado TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id_login TEXT UNIQUE, nombre_prensa TEXT, 
            password TEXT, provincia TEXT, role TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''')
        try:
            conn.execute('INSERT INTO usuarios (user_id_login, nombre_prensa, password, provincia, role) VALUES (?,?,?,?,?)',
                         ('ADMIN-01', 'Director General', 'admin123', 'Andalucía', 'admin'))
            conn.commit()
        except: pass

inicializar_sistema()

# --- RUTAS PÚBLICAS ---
@app.route('/')
def home():
    with conectar_db() as conn:
        noticias = conn.execute('SELECT * FROM noticias ORDER BY id DESC').fetchall()
        recientes = conn.execute('SELECT * FROM noticias ORDER BY id DESC LIMIT 5').fetchall()
        categorias = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('index.html', noticias=noticias, noticias_recientes=recientes, categorias_nav=categorias, fecha_hoy=datetime.now().strftime("%d/%m/%Y"), titulo_filtro="Portada")

@app.route('/post/<int:post_id>')
def ver_post(post_id):
    with conectar_db() as conn:
        post = conn.execute('SELECT * FROM noticias WHERE id = ?', (post_id,)).fetchone()
        categorias = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('post.html', post=post, categorias_nav=categorias)

@app.route('/categoria/<nombre>')
def filtro_categoria(nombre):
    with conectar_db() as conn:
        noticias = conn.execute('SELECT * FROM noticias WHERE categoria = ? ORDER BY id DESC', (nombre,)).fetchall()
        recientes = conn.execute('SELECT * FROM noticias ORDER BY id DESC LIMIT 5').fetchall()
        categorias = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('index.html', noticias=noticias, noticias_recientes=recientes, categorias_nav=categorias, titulo_filtro=nombre, fecha_hoy=datetime.now().strftime("%d/%m/%Y"))

# --- RUTAS PRIVADAS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        with conectar_db() as conn:
            u = conn.execute('SELECT * FROM usuarios WHERE user_id_login=? AND password=?', (request.form['uid'], request.form['pw'])).fetchone()
        if u:
            login_user(User(u['id'], u['user_id_login'], u['nombre_prensa'], u['provincia'], u['role']))
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_post():
    if request.method == 'POST':
        with conectar_db() as conn:
            conn.execute('INSERT INTO noticias (titulo, entradilla, contenido, autor, provincia, fecha, imagen_url, pie_foto, categoria, estado) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (request.form['titulo'], request.form['entradilla'], request.form['contenido'], current_user.nombre_prensa, current_user.provincia, datetime.now().strftime("%d/%m/%Y"), request.form['img'], request.form['pie'], request.form['cat'], 'publicado'))
            conn.commit()
        return redirect(url_for('home'))
    with conectar_db() as conn:
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('editor.html', categorias=cats)

@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
def gestionar_usuarios():
    if current_user.role != 'admin': return redirect(url_for('home'))
    if request.method == 'POST':
        uid = generar_id_unico(request.form['nombre'], request.form['prov'])
        with conectar_db() as conn:
            conn.execute('INSERT INTO usuarios (user_id_login, nombre_prensa, password, provincia, role) VALUES (?,?,?,?,?)',
                (uid, request.form['nombre'], request.form['pw'], request.form['prov'], request.form['role']))
            conn.commit()
        flash(f"ÉXITO: ID GENERADO -> {uid}")
    with conectar_db() as conn:
        usrs = conn.execute('SELECT * FROM usuarios').fetchall()
    return render_template('usuarios.html', usuarios=usrs)

@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
def gestionar_categorias():
    if current_user.role != 'admin': return redirect(url_for('home'))
    if request.method == 'POST':
        with conectar_db() as conn:
            conn.execute('INSERT OR IGNORE INTO categorias (nombre) VALUES (?)', (request.form['nombre'].upper(),))
            conn.commit()
    with conectar_db() as conn:
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('categorias.html', categorias=cats)

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('home'))

if __name__ == '__main__': app.run(debug=True)