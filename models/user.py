from models.db import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(200), unique=True)
    email = db.Column(db.String(200))
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    work = db.Column(db.String(50))
    avatar = db.Column(db.String(100))