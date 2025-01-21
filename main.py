import os
from dotenv import load_dotenv
from pathlib import Path
from flask import Flask, redirect, render_template, request, abort, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage

# Don't forget to set values to the .env file
load_dotenv()

# Info to send emails
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Role variables
GUEST_ROLE = 1
DETECTIVE_ROLE = 2
BOSS_ROLE = 3 # Default Boss User e-mail and password are: admin@email.com and 1234
              # If it doesn't exist, you will have to create it yourself in the database

# Errors
SAME_EMAIL_ERROR = 'There\'s already an account linked to this e-mail'

# Gets file path and domain
PATH_LOCATION = Path(__file__).absolute().parent
DOMAIN = os.getenv('DOMAIN')

# Creates application and database
app = Flask(__name__, instance_path=PATH_LOCATION)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Login settings
login_manager = LoginManager(app)
login_manager.login_view = 'login'
bcrypt = Bcrypt(app)

# E-mail settings
app.config['MAIL_SERVER'] = EMAIL_HOST
app.config['MAIL_PORT'] = EMAIL_PORT
app.config['MAIL_USERNAME'] = EMAIL_ACCOUNT
app.config['MAIL_PASSWORD'] = EMAIL_PASSWORD
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    _id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Integer, nullable=True)
    detective_id = db.Column(db.String(100), nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    cases = db.relationship('Case', backref='user')

    def __init__(self, name, last_name, password, email, role, detective_id, approved):
        self.name = name
        self.last_name = last_name
        self.password = password
        self.email = email
        self.role = role
        self.detective_id = detective_id
        self.approved = approved
    
    def get_id(self):
        return (self._id)

# Case model
class Case(db.Model):
    __tablename__ = 'cases'

    _id = db.Column('id', db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text(), nullable=True)
    content = db.Column(db.Text(), nullable=False)

    def __init__(self, uid, title, description, content):
        self.uid = uid
        self.title = title
        self.description = description
        self.content = content

# Starts login manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Homepage
@app.route('/')
@login_required
def index():
    cases = Case.query.all()
    return render_template('index.html', cases=cases)

# Guest registering page
@app.route('/register_guest', methods=['GET', 'POST'])
def register_guest():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    register_type = 'register_guest'
    if request.method == 'GET':
        return render_template('register.html', register_type=register_type)
    elif request.method == 'POST':
        name = request.form.get('name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')

        password_hashed = bcrypt.generate_password_hash(password)
        has_email = User.query.filter_by(email=email).first()

        # Checks if e-mail already in database
        if has_email:
            return render_template('register.html', register_type=register_type, error=SAME_EMAIL_ERROR)

        user = User(name=name, last_name=last_name, email=email, password=password_hashed, role=GUEST_ROLE, detective_id=None, approved=True)

        db.session.add(user)
        db.session.commit()
        return redirect(url_for('index'))

# Detective registering page
@app.route('/register_detective', methods=['GET', 'POST'])
def register_detective():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    register_type = 'register_detective'
    if request.method == 'GET':
        return render_template('register.html', register_type=register_type)
    elif request.method == 'POST':
        name = request.form.get('name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        detective_id = request.form.get('detective_id')

        password_hashed = bcrypt.generate_password_hash(password)
        has_email = User.query.filter_by(email=email).first()

        # Checks if e-mail already in database
        if has_email:
            return render_template('register.html', register_type=register_type, error=SAME_EMAIL_ERROR)

        # Sends user as not approved, because the Boss has to approve it first
        user = User(name=name, last_name=last_name, email=email, password=password_hashed, role=DETECTIVE_ROLE, detective_id=detective_id, approved=False)

        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login', new_user=True))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        # Checa se usuário existe
        if not user:
            return redirect(url_for('login'))

        # Checa se o hash da senha do formulário é o mesmo que no banco de dados
        if bcrypt.check_password_hash(user.password, password):
            # Checa se o usuário já foi aprovado
            if user.approved is True:
                login_user(user)
                return redirect(url_for('index'))
            else:
                return redirect(url_for('login')) 
        else:
            return redirect(url_for('login'))

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# User list
@app.route('/users')
@login_required
def users():
    if current_user.role not in [DETECTIVE_ROLE, BOSS_ROLE]:
        return redirect(url_for('index'))
    user_list = User.query.all()
    return render_template('users.html', users=user_list)

# User pages
@app.route('/users/<uid>', methods=['GET', 'POST'])
@login_required
def user_page(uid):
    if request.method == 'GET':
        user = User.query.filter_by(_id=uid).first()
        if not user:
            return abort(404)
        
        if current_user.role in [DETECTIVE_ROLE, BOSS_ROLE] or current_user == user:
            return render_template('user_page.html', user=user)
        else:
            return redirect(url_for('index'))
    elif request.method == 'POST':
        user = User.query.filter_by(_id=uid).first()

        user.name = request.form.get('name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')

        db.session.commit()
        return redirect(url_for('user_page', uid=uid))

# Delete users
@app.route('/users/delete/<uid>', methods=['GET', 'POST'])
@login_required
def delete_user(uid):
    if request.method == 'GET':
        return redirect(url_for('index'))
    elif request.method == 'POST':
        if current_user.role != BOSS_ROLE:
            return redirect(url_for('index'))
        
        user = User.query.filter_by(_id=uid).first()

        if user:
            db.session.delete(user)
        else:
            return redirect(url_for('index'))

        db.session.commit()
        return redirect(url_for('users'))

# Users to be approved list
@app.route('/users/pending')
@login_required
def approvals():
    if current_user.role != BOSS_ROLE:
        return redirect(url_for('index'))
    user_list = User.query.filter_by(approved=False)
    return render_template('users.html', users=user_list, approvals=True)

# Approve users
@app.route('/users/<uid>/approved', methods=['GET', 'POST'])
@login_required
def approve(uid):
    if request.method == 'GET':
        return redirect(url_for('index'))
    elif request.method == 'POST':
        if current_user.role != BOSS_ROLE:
            return redirect(url_for('index'))
        
        user = User.query.filter_by(_id=uid).first()

        if user:
            user.approved = True
            try:
                # Sends an e-mail if account is approved
                msg = EmailMessage('Account approved', f'Your account has been approved!' 
                                f'Login to use the website: {DOMAIN}/login', EMAIL_ACCOUNT, [f'{user.email}'])
                msg.send()
            except:
                print('There\s something wrong with your e-mail settings\n')
        else:
            return redirect(url_for('index'))

        db.session.commit()
        return redirect(url_for('approvals'))

# Creates a new case
@app.route('/case/new', methods=['GET', 'POST'])
@login_required
def new_case():
    if current_user.role not in [DETECTIVE_ROLE, BOSS_ROLE]:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('new_case.html')
    elif request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        content = request.form.get('content')
        uid = current_user._id

        created_case = Case(uid=uid, title=title, description=description, content=content)

        db.session.add(created_case)
        db.session.commit()
        return redirect(url_for('index'))

# Case page
@app.route('/case/<cid>', methods=['GET', 'POST'])
@login_required
def case_page(cid):
    if request.method == 'GET':
        case = Case.query.filter_by(_id=cid).first()
        if not case:
            return abort(404)
        return render_template('case_page.html', case=case)
    elif request.method == 'POST':
        case = Case.query.filter_by(_id=cid).first()

        case.title = request.form.get('title')
        case.description = request.form.get('description')
        case.content = request.form.get('content')

        db.session.commit()
        return redirect(url_for('case_page', cid=cid))

# Delete cases
@app.route('/case/delete/<cid>', methods=['GET', 'POST'])
@login_required
def delete_case(cid):
    if request.method == 'GET':
        return redirect(url_for('index'))
    elif request.method == 'POST':  
        case_to_delete = Case.query.filter_by(_id=cid).first()
    
        if (current_user.role == BOSS_ROLE or current_user == case_to_delete.user) and case_to_delete:
            db.session.delete(case_to_delete)
        else:
            return redirect(url_for('index'))

        db.session.commit()
        return redirect(url_for('index'))

if __name__ == '__main__':
    # Creates database
    app.app_context().push()
    db.create_all()

    # Starts application
    app.run(debug=True)