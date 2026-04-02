import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
from google_auth_oauthlib.flow import Flow

flow = Flow.from_client_secrets_file(
    "client_secret.json",
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_uri="http://127.0.0.1:5000/callback"
)