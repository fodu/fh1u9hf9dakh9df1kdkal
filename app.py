from flask import Flask, render_template, request, url_for, redirect, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma_chave_muito_secreta_aqui_pode_trocar' # Troque isso depois
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.getcwd(), 'data', 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelo do Usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Pra ver se o cara é admin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Cria o banco se não existir
with app.app_context():
    db.create_all()

# --- INICIO DAS ROTAS DE LOGIN ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username já existe.', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        flash('Conta criada! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login inválido.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- FIM DAS ROTAS DE LOGIN ---

DATA = os.path.join(os.getcwd(), "data")
ADMIN_PASTES = os.path.join(os.getcwd(), "data", "admin")
ANON_PASTES = os.path.join(os.getcwd(), "data", "other")

with open(os.path.join(DATA, "template"), "r", encoding="utf-8") as temp_file:
    _DEFAULT_POST_TEMPLATE = temp_file.read()

admin_posts_list = []
anon_posts_list = []
loosers_list = []

def refreshLoosers():
    global loosers_list
    with open(os.path.join(DATA, "hol.json"), "r", encoding="utf-8") as file:
        data = json.load(file)
    if not(len(loosers_list) == len(data["loosers"])):
        loosers_list = []
        for looser in data["loosers"]:
            if isinstance(looser, dict):
                loosers_list.append(looser)

def refreshAdminPosts():
    global admin_posts_list
    admin_posts_file_list = os.listdir(ADMIN_PASTES)
    if not(len(admin_posts_list) == len(admin_posts_file_list)):
        for admin_post_file_name in admin_posts_file_list:
            admin_post_file_name_path = os.path.join(ADMIN_PASTES, admin_post_file_name)
            if os.path.isfile(admin_post_file_name_path):
                admin_post_file_name_stats = os.stat(admin_post_file_name_path)
                admin_posts_list.append({
                    "name": admin_post_file_name,
                    "size": bytes2KB(admin_post_file_name_stats.st_size),
                    "creation_date": datetime.utcfromtimestamp(int(admin_post_file_name_stats.st_mtime)).strftime('%d-%m-%Y'),
                    "creation_time": datetime.utcfromtimestamp(int(admin_post_file_name_stats.st_mtime)).strftime('%H:%M:%S')
                })

def refreshAnonPosts():
    global anon_posts_list
    anon_posts_file_list = os.listdir(ANON_PASTES)
    if not(len(anon_posts_list) == len(anon_posts_file_list)):
        for anon_post_file_name in anon_posts_file_list:
            anon_post_file_name_path = os.path.join(ANON_PASTES, anon_post_file_name)
            if os.path.isfile(anon_post_file_name_path):
                anon_post_file_name_stats = os.stat(anon_post_file_name_path)
                anon_posts_list.append({
                    "name": anon_post_file_name,
                    "size": bytes2KB(anon_post_file_name_stats.st_size),
                    "creation_date": datetime.utcfromtimestamp(int(anon_post_file_name_stats.st_mtime)).strftime('%d-%m-%Y'),
                    "creation_time": datetime.utcfromtimestamp(int(anon_post_file_name_stats.st_mtime)).strftime('%H:%M:%S')
                })

def bytes2KB(value):
    return value / 1000

@app.route("/")
def index():
    global admin_posts_list, anon_posts_list
    refreshAdminPosts()
    refreshAnonPosts()
    return render_template("index.html", admin_posts_list=admin_posts_list, anon_posts_list=anon_posts_list)

@app.route("/new")
@login_required # Obriga a estar logado pra criar post
def new_paste():
    return render_template("new.html", paste_template_text=_DEFAULT_POST_TEMPLATE)

@app.route("/new_paste", methods=['POST'])
@login_required
def new_paste_form_post():
    global _DEFAULT_POST_TEMPLATE
    try:
        args = request.values
        pasteTitle = str(args.get('pasteTitle')).replace("/", "%2F")
        pasteContent = args.get('pasteContent')
    except Exception as e:
        return f"Error: {e}"

    # Quem é admin salva na pasta admin, quem é user normal salva na other
    save_path = ADMIN_PASTES if current_user.is_admin else ANON_PASTES
    
    with open(os.path.join(save_path, pasteTitle), "w", encoding="utf-8") as file:
        file.write(pasteContent)
    return redirect(url_for('index'))

@app.route("/post/<file>")
def post(file):
    filename = os.path.join(ANON_PASTES, file)
    with open(filename, "r", encoding="utf-8") as filec:
        content = filec.read()
    stats = os.stat(filename)
    creation_date = datetime.utcfromtimestamp(int(stats.st_mtime)).strftime('%d-%m-%Y')
    creation_time = datetime.utcfromtimestamp(int(stats.st_mtime)).strftime('%H:%M:%S')
    size = bytes2KB(stats.st_size)
    return render_template("post.html", filename=file, file_content=content, creation_date=creation_date, creation_time=creation_time, size=size)

@app.route("/admin/<file>")
def admin_post(file):
    filename = os.path.join(ADMIN_PASTES, file)
    with open(filename, "r", encoding="utf-8") as filec:
        content = filec.read()
    stats = os.stat(filename)
    creation_date = datetime.utcfromtimestamp(int(stats.st_mtime)).strftime('%d-%m-%Y')
    creation_time = datetime.utcfromtimestamp(int(stats.st_mtime)).strftime('%H:%M:%S')
    size = bytes2KB(stats.st_size)
    return render_template("admin.html", filename=file, file_content=content, creation_date=creation_date, creation_time=creation_time, size=size)

@app.route("/tos")
def tos():
    with open(os.path.join(DATA, "tos"), "r", encoding="utf-8") as file:
        filec = file.read()
    return render_template("tos.html", file_content=filec)

@app.route("/hol")
def hall_of_loosers():
    global loosers_list
    refreshLoosers()
    return render_template("hol.html", loosers_list=loosers_list)

@app.route("/links")
@app.route("/pages")
def list_of_pages():
    return render_template("pages.html")

if __name__ == "__main__":
    app.run("0.0.0.0", port=8080, debug=False)
