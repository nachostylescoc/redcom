from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import crear_tablas, conectar
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'redcom_clave_secreta'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024 # 20MB maximo
os.makedirs('static/uploads', exist_ok=True)

crear_tablas()

@app.route('/')
def index():
    conn = conectar()

    tipo = request.args.get('tipo', '')
    materia = request.args.get('materia', '')

    query = '''
        SELECT posts.*, usuarios.nombre as autor
        FROM posts
        JOIN usuarios ON posts.usuario_id = usuarios.id
        WHERE 1=1
    '''
    params = []

    if tipo:
        query += ' AND posts.tipo = ?'
        params.append(tipo)

    if materia:
        query += ' AND posts.materia LIKE ?'
        params.append(f'%{materia}%')

    query += ' ORDER BY posts.fecha DESC'

    lista = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', posts=lista, tipo_activo=tipo, materia_activa=materia)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = conectar()
        try:
            conn.execute('INSERT INTO usuarios (nombre, email, password) VALUES (?, ?, ?)',
                        (nombre, email, password))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return render_template('registro.html', error='El email ya està registrado')
        finally:
            conn.close()
        
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = conectar()
        usuario = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = usuario['id']
            session['usuario_nombre'] = usuario['nombre']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Email o contraseña incorrectos')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/subir', methods=['GET', 'POST'])
def subir():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        tipo = request.form['tipo']
        materia = request.form['materia']
        archivo = request.files['archivo']
        nombre_archivo = None

        if archivo and archivo.filename !='':
            nombre_archivo = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo))

        conn = conectar()
        conn.execute('''
            INSERT INTO posts (titulo, descripcion, tipo, materia, archivo, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (titulo, descripcion, tipo, materia, nombre_archivo, session['usuario_id']))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/posts')
def posts():
    conn = conectar()
    lista = conn.execute('''
        SELECT posts.*, usuarios.nombre as autor
        FROM posts
        JOIN usuarios ON posts.usuario_id = usuarios.id)
        ORDER BY posts.fecha DESC
    ''').fetchall()
    conn.close()
    return render_template('index.html', posts=lista)

@app.route('/post/<int:id>', methods=['GET', 'POST']) # post singular
def post(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = conectar()

    if request.method == 'POST':
        contenido = request.form['contenido']
        conn.execute('''
            INSERT INTO comentarios (contenido, post_id, usuario_id)
            VALUES (?, ?, ?)
        ''', (contenido, id, session['usuario_id']))
        conn.commit()

    p = conn.execute('''
        SELECT posts.*, usuarios.nombre as autor
        FROM posts
        JOIN usuarios ON posts.usuario_id = usuarios.id
        WHERE posts.id = ?
    ''', (id,)).fetchone()

    comentarios = conn.execute('''
        SELECT comentarios.*, usuarios.nombre as autor
        FROM comentarios
        JOIN usuarios ON comentarios.usuario_id = usuarios.id
        WHERE comentarios.post_id = ?
        ORDER BY comentarios.fecha ASC
    ''', (id,)).fetchall()

    conn.close()
    return render_template('post.html', post=p, comentarios=comentarios)

@app.route('/perfil/<int:id>')
def perfil(id):
    conn = conectar()
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (id,)).fetchone()
    posts = conn.execute('''
        SELECT * FROM posts WHERE usuario_id = ?
        ORDER BY fecha DESC
    ''', (id,)).fetchall()
    conn.close()
    return render_template('perfil.html', usuario=usuario, posts=posts)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (id,)).fetchone()

    if post['usuario_id'] != session['usuario_id']:
        conn.close()
        return redirect(url_for('index'))

    conn.execute('DELETE FROM comentarios WHERE post_id = ?', (id,))
    conn.execute('DELETE FROM posts WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

if __name__ =='__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)