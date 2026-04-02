from flask import Blueprint, render_template, redirect, session, request
from models.user import User
from models.guest import Guest
from models.db import db
import uuid

# Google auth imports
from auth.google_auth import flow
from googleapiclient.discovery import build

auth_bp = Blueprint("auth", __name__)


# ---------------------- LOGIN PAGE ----------------------
@auth_bp.route("/login")
def login_page():
    return render_template("login.html")


# ---------------------- GUEST LOGIN ----------------------
@auth_bp.route("/login/guest")
def guest_login():
    session_id = str(uuid.uuid4())

    guest = Guest(session_id=session_id)
    db.session.add(guest)
    db.session.commit()

    session["guest_id"] = session_id

    return redirect("/home")


# ---------------------- GOOGLE LOGIN ----------------------
@auth_bp.route("/login/google")
def login_google():
    remember = request.args.get("remember")

    if remember == "true":
        session.permanent = True
    else:
        session.permanent = False

    auth_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(auth_url)
    


# ---------------------- GOOGLE CALLBACK ----------------------
@auth_bp.route("/callback")
def callback():
    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        print("OAuth Error:", e)
        return redirect("/login")   # fallback safely

    credentials = flow.credentials

    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()

    google_id = user_info["id"]
    email = user_info["email"]

    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        session["google_id"] = google_id
        session["email"] = email
        return redirect("/complete-profile")

    session["user_id"] = user.id
    return redirect("/home")

# ---------------------- COMPLETE PROFILE ----------------------
@auth_bp.route("/complete-profile", methods=["GET", "POST"])
def complete_profile():
    if request.method == "POST":
        user = User(
            google_id=session["google_id"],
            email=session["email"],
            name=request.form["name"],
            age=request.form["age"],
            work=request.form["work"],
            avatar=request.form["avatar"]
        )

        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id

        return redirect("/home")

    return render_template("user_form.html")

@auth_bp.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    from models.history import History
    data = History.query.filter_by(user_id=session["user_id"]).all()

    return render_template("history.html", data=data)

@auth_bp.route("/profile")
def profile():
    user = User.query.get(session["user_id"])

    from models.history import History
    history = History.query.filter_by(user_id=user.id).all()

    return render_template("profile.html", user=user, history=history)

@auth_bp.route("/edit-avatar")
def edit_avatar():
    return render_template("edit_avatar.html")

@auth_bp.route("/set-avatar/<name>")
def set_avatar(name):
    user = User.query.get(session["user_id"])
    user.avatar = name
    db.session.commit()
    return redirect("/profile")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@auth_bp.route("/home", methods=["GET", "POST"])
def home():
    if "user_id" not in session and "guest_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        file = request.files["file"]

        if file:
            filename = file.filename
            filepath = "uploads/" + filename
            file.save(filepath)

            return redirect(f"/analysis/{filename}")

    return render_template("index.html")