from models.db import db

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    filename = db.Column(db.String(200))
    chart_type = db.Column(db.String(100))