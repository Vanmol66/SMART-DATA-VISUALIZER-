from models.db import db

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(200))