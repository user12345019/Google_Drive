from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    jsonify,
)
import humanize
from sqlalchemy import desc
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from sqlalchemy.orm import aliased
import pytz
import os
from flask_socketio import SocketIO, join_room
import json
from werkzeug.utils import secure_filename
import random
from PIL import Image, ImageDraw
import colorsys
from sqlalchemy import text

timezone = pytz.timezone("America/Chicago")

app = Flask(__name__)
app.config["SECRET_KEY"] = "onetwothreefour"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///messages.db"
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "users")
db = SQLAlchemy(app)
socketio = SocketIO(app)


os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


online_users = set()

def generate_random_pattern_image(size=200):
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    
    num_colors = random.randint(3, 5)
    colors = []
    for _ in range(num_colors):
        h = random.random()
        s = random.uniform(0.5, 0.8)
        v = random.uniform(0.7, 0.9)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    
    
    pattern_type = random.choice(['circles', 'stripes', 'dots'])
    
    if pattern_type == 'circles':
       
        for i in range(num_colors):
            radius = size * (1 - i/num_colors) / 2
            center = size // 2
            draw.ellipse(
                [center - radius, center - radius, 
                 center + radius, center + radius],
                fill=colors[i]
            )
    
    elif pattern_type == 'stripes':
      
        stripe_width = size // num_colors
        for i in range(num_colors):
            for j in range(0, size * 2, stripe_width):
                draw.polygon(
                    [(j, 0), (j + stripe_width, 0),
                     (j - size, size), (j - size + stripe_width, size)],
                    fill=colors[i]
                )
    
    else:  
       
        for i in range(num_colors):
            num_dots = random.randint(20, 40)
            for _ in range(num_dots):
                x = random.randint(0, size)
                y = random.randint(0, size)
                dot_size = random.randint(5, 15)
                draw.ellipse(
                    [x - dot_size, y - dot_size,
                     x + dot_size, y + dot_size],
                    fill=colors[i]
                )
    
    return image

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(
        db.String(50), nullable=False
    )  
    content = db.Column(db.Text, nullable=False) 
    data = db.Column(db.Text, nullable=True) 
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(timezone)
    )
    read = db.Column(
        db.Boolean, default=False
    ) 

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(timezone))
    messages = db.relationship("Message", backref="sender", lazy=True)
    sent_private_messages = db.relationship(
        "PrivateMessage",
        foreign_keys="PrivateMessage.sender_id",
        backref="sender",
        lazy=True,
    )
    received_private_messages = db.relationship(
        "PrivateMessage",
        foreign_keys="PrivateMessage.recipient_id",
        backref="recipient",
        lazy=True,
    )
    suggestions = db.relationship("Suggestion", backref="sender", lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(timezone)
    )

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(timezone)
    )

class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    suggestion_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(timezone)
    )
    completed = db.Column(db.Boolean, default=False)

if not os.path.exists("messages.db"):
    with app.app_context():
        db.create_all()
else:
 
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN last_seen DATETIME"))
                conn.commit()
        except Exception as e:
        
            pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function

def get_user_images():
    return [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith(('.png', '.jpg', '.jpeg'))]

@app.route("/")
@login_required
def chat():
    messages = Message.query.order_by(Message.timestamp).all()
    users = User.query.filter(User.id != session["user_id"]).all()
    user = User.query.get(session["user_id"])
    is_admin = user.username == "admin" 
    user_images = get_user_images()
    return render_template(
        "chat.html", messages=messages, users=users, user=user, is_admin=is_admin, user_images=user_images
    )

@app.route("/get_messages")
@login_required
def get_messages():
    messages = Message.query.order_by(Message.timestamp).all()
    messages_data = [
        {
            "sender_id": message.sender.id,  # <--- Add this line
            "username": message.sender.username,
            "text": message.message_text,
            "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M"),
        }
        for message in messages
    ]
    return jsonify(messages_data)

@app.route("/get_private_messages/<int:user_id>")
def get_private_messages(user_id):
    current_user_id = session.get("user_id")
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401

    messages = (
        PrivateMessage.query.filter(
            (
                (PrivateMessage.sender_id == current_user_id)
                & (PrivateMessage.recipient_id == user_id)
            )
            | (
                (PrivateMessage.sender_id == user_id)
                & (PrivateMessage.recipient_id == current_user_id)
            )
        )
        .order_by(PrivateMessage.timestamp)
        .all()
    )

    messages_data = [
        {
            "sender_id": message.sender_id,
            "sender": message.sender.username,
            "text": message.message_text,
            "timestamp": message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        for message in messages
    ]
    return jsonify(messages_data)

@app.route("/private_chat/<int:user_id>")
@login_required
def private_chat(user_id):
    other_user = User.query.get_or_404(user_id)
    current_user_id = session["user_id"]
    current_user = User.query.get(current_user_id)

    messages = (
        PrivateMessage.query.filter(
            (
                (PrivateMessage.sender_id == current_user_id)
                & (PrivateMessage.recipient_id == user_id)
            )
            | (
                (PrivateMessage.sender_id == user_id)
                & (PrivateMessage.recipient_id == current_user_id)
            )
        )
        .order_by(PrivateMessage.timestamp)
        .all()
    )
    user_images = get_user_images()
    return render_template(
        "private_chat.html",
        messages=messages,
        other_user=other_user,
        current_user_id=current_user_id,
        user=current_user,
        user_images=user_images
    )

@app.route("/send", methods=["POST"])
@login_required
def send():
    message_text = request.form["message"]
    if message_text.strip():
        new_message = Message(sender_id=session["user_id"], message_text=message_text)
        db.session.add(new_message)
        db.session.commit()
        sender = User.query.get(session["user_id"])
        socketio.emit(
            "new_public_message",
            {
                "sender_id": sender.id,
                "username": sender.username,
                "text": message_text,
                "timestamp": new_message.timestamp.strftime("%Y-%m-%d %H:%M"),
            },
        )
        users = User.query.filter(User.id != session["user_id"]).all()
        for user in users:
            content = f"New message from {sender.username} in public chat"
            new_notification = Notification(
                user_id=user.id, type="public_message", content=content
            )
            db.session.add(new_notification)
            db.session.flush()  

            socketio.emit(
                "new_notification",
                {
                    "id": new_notification.id,
                    "type": new_notification.type,
                    "content": new_notification.content,
                    "data": None,
                    "timestamp": new_notification.timestamp.strftime("%Y-%m-%d %H:%M"),
                },
                room=f"user_{user.id}",
            )
        db.session.commit()
    return redirect(url_for("chat"))

@app.route("/send_private/<int:recipient_id>", methods=["POST"])
@login_required
def send_private(recipient_id):
    message_text = request.form["message"]
    if message_text.strip():
        new_message = PrivateMessage(
            sender_id=session["user_id"],
            recipient_id=recipient_id,
            message_text=message_text,
        )
        db.session.add(new_message)
        db.session.commit()
        sender = User.query.get(session["user_id"])
        for uid in [session["user_id"], recipient_id]:
            socketio.emit(
                "new_private_message",
                {
                    "sender_id": sender.id,
                    "sender_username": sender.username,
                    "recipient_id": recipient_id,
                    "text": message_text,
                    "timestamp": new_message.timestamp.strftime("%Y-%m-%d %H:%M"),
                },
                room=f"user_{uid}",
            )
        content = f"New private message from {sender.username}"
        data = json.dumps({"sender_id": sender.id, "sender_username": sender.username})
        new_notification = Notification(
            user_id=recipient_id, type="private_message", content=content, data=data
        )
        db.session.add(new_notification)
        db.session.commit()
        socketio.emit(
            "new_notification",
            {
                "id": new_notification.id,
                "type": new_notification.type,
                "content": new_notification.content,
                "data": json.loads(data),
                "timestamp": new_notification.timestamp.strftime("%Y-%m-%d %H:%M"),
            },
            room=f"user_{recipient_id}",
        )
    return redirect(url_for("private_chat", user_id=recipient_id))

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            error = "Username already exists"
        else:
            password_hash = generate_password_hash(password)
            new_user = User(username=username, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            pattern_image = generate_random_pattern_image()
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{new_user.id}.png")
            pattern_image.save(image_path)
            session["user_id"] = new_user.id
            return redirect(url_for("chat"))
    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            return redirect(url_for("chat"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/admin")
@login_required
def admin_dashboard():
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        abort(402)
    users = User.query.all()
    public_messages = (
        db.session.query(
            Message.id.label("id"),
            User.username.label("sender"),
            Message.message_text.label("text"),
            Message.timestamp.label("timestamp"),
        )
        .join(User, Message.sender_id == User.id)
        .order_by(Message.timestamp.desc())
        .all()
    )
    sender_alias = aliased(User)
    recipient_alias = aliased(User)
    private_messages = (
        db.session.query(
            PrivateMessage.id.label("id"),
            sender_alias.username.label("sender"),
            recipient_alias.username.label("recipient"),
            PrivateMessage.message_text.label("text"),
            PrivateMessage.timestamp.label("timestamp"),
        )
        .join(sender_alias, PrivateMessage.sender_id == sender_alias.id)
        .join(recipient_alias, PrivateMessage.recipient_id == recipient_alias.id)
        .order_by(PrivateMessage.timestamp.desc())
        .all()
    )
    suggestions = (
        db.session.query(
            Suggestion.id.label("id"),
            User.username.label("sender"),
            Suggestion.suggestion_text.label("text"),
            Suggestion.timestamp.label("timestamp"),
            Suggestion.completed.label("completed"),
        )
        .join(User, Suggestion.sender_id == User.id)
        .order_by(Suggestion.timestamp.desc())
        .all()
    )
    user_images = get_user_images()
    return render_template(
        "admin_dashboard.html",
        users=users,
        public_messages=public_messages,
        private_messages=private_messages,
        suggestions=suggestions,
        user=user,
        user_images=user_images
    )

@app.route("/delete_public_message/<int:message_id>", methods=["POST"])
@login_required
def delete_public_message(message_id):
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        abort(402)
    message = Message.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_private_message/<int:message_id>", methods=["POST"])
@login_required
def delete_private_message(message_id):
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        abort(402)
    message = PrivateMessage.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_suggestion/<int:suggestion_id>", methods=["POST"])
@login_required
def delete_suggestion(suggestion_id):
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        abort(402)
    suggestion = Suggestion.query.get_or_404(suggestion_id)
    db.session.delete(suggestion)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/suggestions")
@login_required
def suggestions():
    current_user = User.query.get(session["user_id"])
    suggestions = Suggestion.query.order_by(Suggestion.timestamp.desc()).all()
    user_images = get_user_images()
    return render_template("suggestions.html", user=current_user, suggestions=suggestions, user_images=user_images)

@app.route("/get_suggestions")
@login_required
def get_suggestions():
    suggestions = Suggestion.query.order_by(Suggestion.timestamp).all()
    data = [
        {
            "id": s.id,
            "username": s.sender.username,
            "text": s.suggestion_text,
            "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M"),
            "completed": s.completed,
        }
        for s in suggestions
    ]
    return jsonify(data)

@app.route("/send_suggestion", methods=["POST"])
@login_required
def send_suggestion():
    suggestion_text = request.form["suggestion"]
    if suggestion_text.strip():
        new_suggestion = Suggestion(
            sender_id=session["user_id"], suggestion_text=suggestion_text
        )
        db.session.add(new_suggestion)
        db.session.commit()
    return redirect(url_for("suggestions"))

@app.route("/complete_suggestion/<int:id>", methods=["POST"])
@login_required
def complete_suggestion(id):
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        abort(402)
    suggestion = Suggestion.query.get_or_404(id)
    suggestion.completed = True
    db.session.commit()
    return ("", 204)

@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    profile_user = User.query.get(user_id)
    current_user = User.query.get(session["user_id"])
    user_images = get_user_images()
    return render_template("profile.html", user=profile_user, current_user=current_user, user_images=user_images)

@app.route("/upload_profile_picture", methods=["POST"])
@login_required
def upload_profile_picture():
    if "profile_picture" not in request.files:
        return redirect(url_for("profile", user_id=session["user_id"]))
    
    file = request.files["profile_picture"]
    if file.filename == "":
        return redirect(url_for("profile", user_id=session["user_id"]))
    
    if file:
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in ['.png', '.jpg', '.jpeg']:
            return redirect(url_for("profile", user_id=session["user_id"]))
        
        user_id = session["user_id"]
        new_filename = f"{user_id}.png"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        
        file.save(file_path)
        
    return redirect(url_for("profile", user_id=session["user_id"]))

@app.route("/get_notifications")
@login_required
def get_notifications():
    notifications = (
        Notification.query.filter_by(user_id=session["user_id"])
        .order_by(Notification.timestamp.desc())
        .all()
    )
    data = [
        {
            "id": n.id,
            "type": n.type,
            "content": n.content,
            "data": json.loads(n.data) if n.data else None,
            "timestamp": n.timestamp.strftime("%Y-%m-%d %H:%M"),
            "read": n.read,
        }
        for n in notifications
    ]
    return jsonify(data)

@app.route("/clear_notifications", methods=["POST"])
@login_required
def clear_notifications():
    Notification.query.filter_by(user_id=session["user_id"]).delete()
    db.session.commit()
    return ("", 204)


@app.route("/get_users")
@login_required
def get_users():
    now = datetime.now(pytz.utc).astimezone(timezone)
    users = User.query.filter(User.id != session["user_id"]).order_by(
        desc(User.id.in_(online_users)),  
        desc(User.last_seen) 
    ).all()
    data = [{
        "id": user.id, 
        "username": user.username,
        "online": user.id in online_users,
        "last_seen": user.last_seen.strftime("%Y-%m-%d %H:%M:%S") if user.last_seen else None,
        "relative_last_seen": (
            humanize.naturaltime(
                now - timezone.localize(user.last_seen)  
            ) if user.last_seen else "Never"
        )
    } for user in users]
    print("Users sorted:", [(user.username, user.last_seen, data[i]["relative_last_seen"]) for i, user in enumerate(users)]) 
    return jsonify(data)

@app.route("/mark_notifications_read", methods=["POST"])
@login_required
def mark_notifications_read():
    notifications = Notification.query.filter_by(
        user_id=session["user_id"], read=False
    ).all()
    for n in notifications:
        n.read = True
    db.session.commit()
    return ("", 204)

@socketio.on("join")
def handle_join(data):
    user_id = data["user_id"]
    join_room(f"user_{user_id}")

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.last_seen = datetime.now(pytz.utc).astimezone(timezone)
            db.session.commit()
            print(f"Connect: {user.username} last_seen set to {user.last_seen}")
            online_users.add(session['user_id'])
            socketio.emit('user_status_change', {
                'user_id': session['user_id'],
                'status': 'online'
            }, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.last_seen = datetime.now(pytz.utc).astimezone(timezone)
            db.session.commit()
            print(f"Disconnect: {user.username} last_seen set to {user.last_seen}")  
        online_users.discard(session['user_id'])
        socketio.emit('user_status_change', {
            'user_id': session['user_id'],
            'status': 'offline'
        }, broadcast=True)





if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER", "") == ""
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
