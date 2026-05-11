import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'andalucia_2026_final_fix'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
DB_NAME = 'diario_andalucia.db'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- LOGIN CONFIG ---
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

def conectar_db():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
    return conn

def generar_id_unico(nombre, provincia):
    prefijo = provincia[:2].upper()
    iniciales = "".join([n[0].upper() for n in nombre.split() if n])[:3]
    base = f"{prefijo}-{iniciales}"
    with conectar_db() as conn:
        count = conn.execute('SELECT COUNT(*) FROM usuarios WHERE user_id_login LIKE ?', (f"{base}%",)).fetchone()[0]
        return f"{base}-{str(count + 1).zfill(2)}"

def inicializar_db():
    provincias = ["Almería", "Cádiz", "Córdoba", "Granada", "Huelva", "Jaén", "Málaga", "Sevilla"]
    with conectar_db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS noticias (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, entradilla TEXT, contenido TEXT, autor TEXT, provincia TEXT, fecha TEXT, imagen_url TEXT, pie_foto TEXT, categoria TEXT, estado TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id_login TEXT UNIQUE, nombre_prensa TEXT, password TEXT, provincia TEXT, role TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)')
        conn.execute('CREATE TABLE IF NOT EXISTS prov_data (nombre TEXT UNIQUE)')
        for p in provincias:
            conn.execute('INSERT OR IGNORE INTO prov_data (nombre) VALUES (?)', (p,))
        try:
            conn.execute('INSERT INTO usuarios (user_id_login, nombre_prensa, password, provincia, role) VALUES (?,?,?,?,?)',
                         ('ADMIN-01', 'Director General', 'admin123', 'Andalucía', 'admin'))
        except: pass
        conn.commit()

# --- RUTAS PÚBLICAS ---
@app.route('/')
def home():
    with conectar_db() as conn:
        noticias = conn.execute('SELECT * FROM noticias WHERE estado IN ("publicar", "publicado") ORDER BY id DESC').fetchall()
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('index.html', noticias=noticias, categorias_nav=cats, fecha_hoy=datetime.now().strftime("%d/%m/%Y"))

@app.route('/noticia/<int:id>')
def ver_noticia(id):
    with conectar_db() as conn:
        noticia = conn.execute('SELECT * FROM noticias WHERE id = ?', (id,)).fetchone()
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    if not noticia: return "Noticia no encontrada", 404
    return render_template('post.html', noticia=noticia, categorias_nav=cats)

# --- REDACCIÓN Y MESA DE TRABAJO ---
@app.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_post():
    if request.method == 'POST':
        accion = request.form.get('accion')
        file = request.files.get('imagen_file')
        img_url = ""
        if file and file.filename != '':
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = url_for('uploaded_file', filename=filename)

        with conectar_db() as conn:
            conn.execute('''INSERT INTO noticias (titulo, entradilla, contenido, autor, provincia, fecha, imagen_url, pie_foto, categoria, estado) 
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (request.form.get('titulo', 'Sin título'), request.form.get('entradilla', ''), 
                 request.form.get('contenido', ''), current_user.nombre_prensa, current_user.provincia, 
                 datetime.now().strftime("%d/%m/%Y"), img_url, request.form.get('pie', ''), 
                 request.form.get('cat', 'GENERAL'), accion))
            conn.commit()
        return redirect(url_for('home' if accion == 'publicar' else 'mis_borradores'))
    
    with conectar_db() as conn:
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('editor.html', categorias=cats)

@app.route('/borradores')
@login_required
def mis_borradores():
    with conectar_db() as conn:
        if current_user.role == 'admin':
            borrs = conn.execute('SELECT * FROM noticias WHERE estado="borrador" ORDER BY id DESC').fetchall()
        else:
            borrs = conn.execute('SELECT * FROM noticias WHERE estado="borrador" AND autor=? ORDER BY id DESC', (current_user.nombre_prensa,)).fetchall()
    return render_template('borradores.html', borradores=borrs)

@app.route('/eliminar/<int:id>')
@login_required
def eliminar_noticia(id):
    with conectar_db() as conn:
        conn.execute('DELETE FROM noticias WHERE id=?', (id,))
        conn.commit()
    return redirect(request.referrer or url_for('home'))

# --- ADMIN: USUARIOS Y CATEGORÍAS ---
@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
def gestionar_usuarios():
    if current_user.role != 'admin': return redirect(url_for('home'))
    with conectar_db() as conn:
        if request.method == 'POST':
            nombre, prov, pw, role = request.form.get('nombre'), request.form.get('prov'), request.form.get('pw'), request.form.get('role')
            if nombre and pw:
                uid = generar_id_unico(nombre, prov)
                conn.execute('INSERT INTO usuarios (user_id_login, nombre_prensa, password, provincia, role) VALUES (?,?,?,?,?)', (uid, nombre, pw, prov, role))
                conn.commit()
        usrs = conn.execute('SELECT * FROM usuarios').fetchall()
        provs = conn.execute('SELECT * FROM prov_data').fetchall()
    return render_template('usuarios.html', usuarios=usrs, provincias=provs)

@app.route('/admin/usuarios/borrar/<int:id>')
@login_required
def borrar_usuario(id):
    if current_user.role == 'admin':
        with conectar_db() as conn: 
            conn.execute('DELETE FROM usuarios WHERE id=? AND user_id_login!="ADMIN-01"', (id,))
            conn.commit()
    return redirect(url_for('gestionar_usuarios'))

@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
def gestionar_categorias():
    if current_user.role != 'admin': return redirect(url_for('home'))
    with conectar_db() as conn:
        if request.method == 'POST':
            nom = request.form.get('nombre', '').upper().strip()
            if nom: 
                conn.execute('INSERT OR IGNORE INTO categorias (nombre) VALUES (?)', (nom,))
                conn.commit()
        cats = conn.execute('SELECT * FROM categorias').fetchall()
    return render_template('categorias.html', categorias=cats)

@app.route('/admin/categorias/borrar/<int:id>')
@login_required
def borrar_categoria(id):
    if current_user.role == 'admin':
        with conectar_db() as conn: 
            conn.execute('DELETE FROM categorias WHERE id=?', (id,))
            conn.commit()
    return redirect(url_for('gestionar_categorias'))

# --- LOGIN / SISTEMA ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uid, pw = request.form.get('uid'), request.form.get('pw')
        with conectar_db() as conn:
            u = conn.execute('SELECT * FROM usuarios WHERE user_id_login=? AND password=?', (uid, pw)).fetchone()
        if u:
            login_user(User(u['id'], u['user_id_login'], u['nombre_prensa'], u['provincia'], u['role']))
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('home'))

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    inicializar_db()
    app.run(debug=True)