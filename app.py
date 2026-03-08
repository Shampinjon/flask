from flask import Flask, render_template, request, redirect, url_for, session, flash
import smtplib
from email.mime.text import MIMEText
import sqlite3
import hashlib
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import random
import os
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = 'sqkqsiqsjqjsqjsjj10100101009898898s'

conn = sqlite3.connect('users.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            verified BOOLEAN NOT NULL DEFAULT FALSE, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS genres(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            genre_id INTEGER,
            image_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (genre_id) REFERENCES genres(id)
)''')

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

default_genres = ['Программирование', 'Наука', 'Искусство', 'Музыка', 'Кино', 'Литература', 'Игры', 'Технологии']
for genre in default_genres:
    cur.execute('INSERT OR IGNORE INTO genres(name) VALUES (?)', [genre])
conn.commit()

def send_welcome_email(to_email, username):
    from_email = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")    
    verify_code = str(random.randint(100000, 999999))
    session['verify_code'] = verify_code
    
    if not from_email or not password:
        return False
        
    subject = "Добро пожаловать в наш блог!"
    body = f"""
    Привет, {username}!
    Спасибо за регистрацию в нашем блоге.
    Будьте добры подтвердить почту: {verify_code}
    С уважением,
    Команда блога
    """
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()        
        return True
    except Exception as e:
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def add_user(name, email, password):
    try:
        password_hash = hash_password(password)
        cur.execute('INSERT INTO users(name, email, password) VALUES (?, ?, ?)', 
                   [name, email, password_hash])
        conn.commit()
        send_welcome_email(email, name)
        return True
    except sqlite3.IntegrityError:
        return False

def get_user_by_email(email):
    cur.execute('SELECT * FROM users WHERE email = ?', [email])
    return cur.fetchone()

def get_user_by_id(user_id):
    cur.execute('SELECT * FROM users WHERE id = ?', [user_id])
    return cur.fetchone()

def check_password(user, password):
    password_hash = hash_password(password)
    return user[3] == password_hash

def update_last_login(user_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('UPDATE users SET last_login = ? WHERE id = ?', [now, user_id])
    conn.commit()

def add_new_post(title, content, user_id, genre_id, image_filename=None):
    cur.execute('INSERT INTO posts(title, content, user_id, genre_id, image_filename) VALUES (?, ?, ?, ?, ?)', 
               [title, content, user_id, genre_id, image_filename])
    conn.commit()

def get_posts(sort_by='newest', genre_id=None):
    query = '''
        SELECT 
            p.id, p.title, p.content, p.user_id, p.genre_id, p.image_filename, p.created_at,
            COALESCE(u.name, 'Аноним') as author_name, g.name as genre_name
        FROM posts p
        LEFT JOIN users u ON p.user_id = u.id
        LEFT JOIN genres g ON p.genre_id = g.id
    '''
    params = []
    if genre_id and genre_id != 'all':
        query += ' WHERE p.genre_id = ?'
        params.append(int(genre_id))
    
    if sort_by == 'newest': query += ' ORDER BY p.created_at DESC'
    elif sort_by == 'oldest': query += ' ORDER BY p.created_at ASC'
    elif sort_by == 'title_asc': query += ' ORDER BY p.title ASC'
    elif sort_by == 'title_desc': query += ' ORDER BY p.title DESC'
    else: query += ' ORDER BY p.created_at DESC'
    
    cur.execute(query, params)
    posts = cur.fetchall()
    formatted_posts = []
    for post in posts:
        formatted_posts.append({
            'id': post[0], 'title': post[1], 'content': post[2], 'user_id': post[3],
            'genre_id': post[4], 'image_filename': post[5], 'created_at': post[6],
            'author_name': post[7], 'genre_name': post[8]
        })
    return formatted_posts

def get_all_genres():
    cur.execute('SELECT * FROM genres ORDER BY name')
    genres_data = cur.fetchall()
    return [{'id': g[0], 'name': g[1]} for g in genres_data]

@app.route('/')
def main():
    sort_by = request.args.get('sort', 'newest')
    genre_id = request.args.get('genre', None)
    if genre_id == 'all' or genre_id == '': genre_id = None
    posts = get_posts(sort_by, genre_id)
    genres = get_all_genres()
    return render_template('main.html', posts=posts, genres=genres, 
                          current_sort=sort_by, current_genre=genre_id)

@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if len(name) < 2: flash('Имя должно содержать не менее 2 символов', 'error')
        elif len(email) < 5 or '@' not in email: flash('Введите корректный email', 'error')
        elif len(password) < 6: flash('Пароль должен содержать не менее 6 символов', 'error')
        elif get_user_by_email(email): flash('Пользователь с таким email уже существует', 'error')
        else:
            if add_user(name, email, password):
                user = get_user_by_email(email)
                session['user_id'] = user[0]
                session['name'] = user[1]
                update_last_login(user[0])
                flash('Регистрация успешна! Пожалуйста, подтвердите почту.', 'info')
                return redirect(url_for('profile'))
            else: flash('Ошибка при регистрации', 'error')
    return render_template('register.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        user = get_user_by_email(email)
        if user and check_password(user, password):
            session['user_id'] = user[0]
            session['name'] = user[1]
            update_last_login(user[0])
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('profile'))
        else: flash('Неверный email или пароль', 'error')
    return render_template('login.html')

@app.route('/profile/', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    if request.method == 'POST':
        if "verify" in request.form:
            code_form = request.form.get('code-form', '')
            if code_form == session.get('verify_code'):
                user = get_user_by_id(user_id)
                cur.execute('UPDATE users SET verified = TRUE WHERE id = ?', [user_id])
                conn.commit()

                flash('Успешно проверено!', 'success')
            else:
                flash('Неверный код!', 'error')
        
        if "resend-code" in request.form:
            user = get_user_by_id(user_id)
            send_welcome_email(user[2], user[1])
            flash('Код отправлен повторно', 'info')

    user = get_user_by_id(user_id)
    cur.execute('''
        SELECT p.id, p.title, p.content, p.user_id, p.genre_id, p.image_filename, p.created_at, g.name as genre_name
        FROM posts p LEFT JOIN genres g ON p.genre_id = g.id
        WHERE p.user_id = ? ORDER BY p.created_at DESC
    ''', [user_id])
    user_posts = []
    for post in cur.fetchall():
        user_posts.append({
            'id': post[0], 'title': post[1], 'content': post[2], 'user_id': post[3],
            'genre_id': post[4], 'image_filename': post[5], 'created_at': post[6], 'genre_name': post[7]
        })
    return render_template('profile.html', name=session['name'], user=user, posts=user_posts, genres=get_all_genres())

@app.route('/add_post/', methods=['GET', 'POST'])
@login_required
def add_post():
    genres = get_all_genres()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        genre_id = request.form.get('genre', '').strip()
        image = request.files.get('image')
        image_filename = None
        if image and image.filename != '' and allowed_file(image.filename):
            import uuid
            image_filename = f"{uuid.uuid4()}.{image.filename.rsplit('.', 1)[1].lower()}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        
        if not title or len(title) < 3: flash('Заголовок короткий', 'error')
        elif not content or len(content) < 10: flash('Контент короткий', 'error')
        else:
            add_new_post(title, content, session['user_id'], int(genre_id), image_filename)
            flash('Пост добавлен!', 'success')
            return redirect(url_for('main'))
    return render_template('new_post.html', genres=genres)

@app.route('/logout/')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main'))

if __name__ == '__main__':
    app.run(debug=True)