import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
import pandas as pd

from flask_migrate import Migrate

from utils.file_handler import save_uploaded_file, allowed_file
from utils.data_analyzer import analyze_dataframe
from utils.chart_generator import generate_plotly_divs, generate_single_plot_div

from datetime import timedelta
from config import Config
from models.db import db
from models.history import History

from utils.data_cleaning import analyze_cleanliness
from utils.dax_generator import generate_dax

# ✅ CREATE APP (ONLY ONCE)
app = Flask(__name__, template_folder="templates", static_folder="static")

# ✅ CONFIG
app.config.from_object(Config)

# ✅ DB INIT
db.init_app(app)
migrate=Migrate(app,db)


# --- Upload folder ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

# ✅ REGISTER BLUEPRINT
from auth.routes import auth_bp
app.register_blueprint(auth_bp)

# --- Helper ---
def read_dataset(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError

    if filename.endswith(".csv"):
        return pd.read_csv(filepath)

    return pd.read_excel(filepath)

# --- ROUTES ---

@app.route("/")
def root():
    return redirect(url_for("auth.home"))   # ✅ FIXED

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("No file selected", "warning")
        return redirect(url_for("auth.home"))   # ✅ FIXED

    if not allowed_file(file.filename):
        flash("Invalid file type", "danger")
        return redirect(url_for("auth.home"))   # ✅ FIXED

    filename = secure_filename(file.filename)
    save_uploaded_file(file, app.config["UPLOAD_FOLDER"], filename)

    return redirect(url_for("cleaning_page", filename=filename))

@app.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")

@app.route("/analysis/<path:filename>")
def analysis(filename):
    try:
        df = read_dataset(filename)
    except:
        return redirect(url_for("auth.home"))   # ✅ FIXED

    profile = analyze_dataframe(df)

    numeric = df.select_dtypes(include=["number"])
    numeric_summary = numeric.describe().round(4).to_dict() if not numeric.empty else None
    
    cleaning_report = analyze_cleanliness(df)
    dax_recommendations = generate_dax(df)
    
    existing = None  # ✅ ALWAYS DEFINE FIRST
# ✅ FOR LOGGED USER
    if "user_id" in session:
        existing = History.query.filter_by(
            user_id=session["user_id"],
            filename=filename
        ).first()

# ✅ FOR GUEST USER
    elif "guest_id" in session:
        existing = History.query.filter_by(
            guest_id=session["guest_id"],
            filename=filename
        ).first()

# ✅ SAVE ONLY IF NOT EXISTS
    if not existing:
        new = History(
            user_id=session.get("user_id"),
            guest_id=session.get("guest_id"),
            filename=filename,
            chart_type="auto"
        )
        db.session.add(new)
        db.session.commit()

    return render_template(
        "analysis.html",
        filename=filename,
        profile=profile,
        numeric_summary=numeric_summary,
        cleaning=cleaning_report,
        dax=dax_recommendations,
        is_guest=("guest_id" in session)
    )


@app.route("/charts/<path:filename>", methods=["GET", "POST"])
def charts(filename):
    df = read_dataset(filename)
    profile = analyze_dataframe(df)

    previews = generate_plotly_divs(df, profile, max_charts=4)

    if request.method == "POST":
        return redirect(url_for(
            "view_chart",
            filename=filename,
            chart_type=request.form.get("chart_type"),
            xcol=request.form.get("xcol"),
            ycol=request.form.get("ycol")
        ))

    return render_template(
        "charts.html",
        filename=filename,
        profile=profile,
        previews=previews,
        columns=[c["name"] for c in profile["columns"]],
        numeric_columns=profile.get("numeric_columns", [])
    )


@app.route("/view_chart/<path:filename>")
def view_chart(filename):
    df = read_dataset(filename)

    chart_type = request.args.get("chart_type")
    xcol = request.args.get("xcol")
    ycol = request.args.get("ycol")

    div, title = generate_single_plot_div(df, chart_type, xcol, ycol)

    # ✅ FIXED HISTORY SAVE
    if "user_id" in session:
        history = History(
            user_id=session["user_id"],
            filename=filename,
            chart_type=chart_type
        )
        db.session.add(history)
        db.session.commit()

    return render_template("view_chart.html", chart_div=div, title=title, filename=filename)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


@app.route("/dashboard/<path:filename>")
def dashboard_redirect(filename):
    return redirect(url_for("analysis", filename=filename))


app.permanent_session_lifetime = timedelta(days=7)

@app.route("/cleaning/<path:filename>")
def cleaning_page(filename):
    df = read_dataset(filename)

    cleaning_report = analyze_cleanliness(df)
    dax_recommendations = generate_dax(df)

    return render_template(
        "cleaning.html",
        filename=filename,
        cleaning=cleaning_report,
        dax=dax_recommendations
    )


if __name__ == "__main__":
    app.run(debug=True)