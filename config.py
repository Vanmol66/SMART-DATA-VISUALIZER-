class Config:
    SECRET_KEY = "supersecretkey"

    SQLALCHEMY_DATABASE_URI = "sqlite:///users.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_CLIENT_SECRETS_FILE = "client_secret.json"