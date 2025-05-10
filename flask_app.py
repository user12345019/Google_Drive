from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from sqlalchemy.orm import aliased

app = Flask(__name__)
app.config['SECRET_KEY'] = 'onetwothreefour'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messaging.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    messages = db.relationship('Message', backref='sender', lazy=True)
    sent_private_messages = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.sender_id', backref='sender', lazy=True)
    received_private_messages = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.recipient_id', backref='recipient', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def chat():
    messages = Message.query.order_by(Message.timestamp).all()
    users = User.query.filter(User.id != session['user_id']).all()
    return render_template('chat.html', messages=messages, users=users)

@app.route('/send', methods=['POST'])
@login_required
def send():
    message_text = request.form['message']
    if message_text.strip():
        new_message = Message(sender_id=session['user_id'], message_text=message_text)
        db.session.add(new_message)
        db.session.commit()
    return redirect(url_for('chat'))

@app.route('/private_chat/<int:user_id>')
@login_required
def private_chat(user_id):
    other_user = User.query.get_or_404(user_id)
    current_user_id = session['user_id']
    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == current_user_id) & (PrivateMessage.recipient_id == user_id)) |
        ((PrivateMessage.sender_id == user_id) & (PrivateMessage.recipient_id == current_user_id))
    ).order_by(PrivateMessage.timestamp).all()
    return render_template('private_chat.html', messages=messages, other_user=other_user, current_user_id=current_user_id)

@app.route('/send_private/<int:recipient_id>', methods=['POST'])
@login_required
def send_private(recipient_id):
    message_text = request.form['message']
    if message_text.strip():
        new_message = PrivateMessage(sender_id=session['user_id'], recipient_id=recipient_id, message_text=message_text)
        db.session.add(new_message)
        db.session.commit()
    return redirect(url_for('private_chat', user_id=recipient_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return 'Username already exists'
        password_hash = generae_password_hash(password)
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('chat'))
        return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():

    user = User.query.get(session['user_id'])
    if not user or user.username != 'admin':
        abort(403)

    users = User.query.all()

    public_messages = (
        db.session.query(
            Message.id.label('id'),
            User.username.label('sender'),
            Message.message_text.label('text'),
            Message.timestamp.label('timestamp')
        )
        .join(User, Message.sender_id == User.id)
        .order_by(Message.timestamp.desc())
        .all()
    )

    sender_alias = aliased(User)
    recipient_alias = aliased(User)
    private_messages = (
        db.session.query(
            PrivateMessage.id.label('id'),
            sender_alias.username.label('sender'),
            recipient_alias.username.label('recipient'),
            PrivateMessage.message_text.label('text'),
            PrivateMessage.timestamp.label('timestamp')
        )
        .join(sender_alias, PrivateMessage.sender_id == sender_alias.id)
        .join(recipient_alias, PrivateMessage.recipient_id == recipient_alias.id)
        .order_by(PrivateMessage.timestamp.desc())
        .all()
    )

    return render_template('admin_dashboard.html', users=users, public_messages=public_messages, private_messages=private_messages)

if __name__ == '__main__':
    app.run(debug=True)
