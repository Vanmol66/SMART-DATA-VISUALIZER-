import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory,session
from werkzeug.utils import secure_filename
import pandas as pd
import auth.routes

from utils.file_handler import save_uploaded_file, allowed_file
from utils.data_analyzer import analyze_dataframe
from utils.chart_generator import generate_plotly_divs, generate_single_plot_div

from datetime import timedelta

from models.history import History

from config import Config
from models.db import db

# ✅ CREATE APP FIRST (ONLY ONCE)
app = Flask(__name__, template_folder="templates", static_folder="static")

# ✅ CONFIG
app.config.from_object(Config)

# ✅ DB INIT
db.init_app(app)

# ✅ CREATE TABLES
with app.app_context():
    db.create_all()



# --- Configuration ---
app = Flask(__name__, template_folder="templates", static_folder="static")

app.config.from_object(Config)
db.init_app(app)   # ✅ MUST be here BEFORE using db anywhere

# ADD THESE HERE
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key-change-this")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

# ✅ REGISTER BLUEPRINT HERE
from auth.routes import auth_bp
app.register_blueprint(auth_bp)

# Inject 'app' into templates for small uses (like showing upload limit)
@app.context_processor
def inject_app():
    return dict(app=app)

# --- Helper to read file into DataFrame ---
def read_dataset(filename: str) -> pd.DataFrame:
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError("Uploaded file not found.")
    if filename.lower().endswith(".csv"):
        return pd.read_csv(filepath)
    return pd.read_excel(filepath)

# --- Routes ---
@app.route("/")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("home"))
    if not allowed_file(file.filename):
        flash("Unsupported file type. Use .csv or .xlsx", "danger")
        return redirect(url_for("home"))
    filename = secure_filename(file.filename)
    save_uploaded_file(file, app.config["UPLOAD_FOLDER"], filename)
    flash(f"Uploaded {filename}", "success")
    return redirect(url_for("analysis", filename=filename))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/analysis/<path:filename>")
def analysis(filename):
    try:
        df = read_dataset(filename)
    except FileNotFoundError:
        flash("File not found.", "danger")
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for("home"))

    profile = analyze_dataframe(df)
    numeric = df.select_dtypes(include=["number"])
    numeric_summary = None
    if not numeric.empty:
        numeric_summary = numeric.describe().round(4).to_dict()

    correlation = profile.get("correlation", {})

    return render_template(
        "analysis.html",
        filename=filename,
        profile=profile,
        numeric_summary=numeric_summary,
        correlation=correlation
    )



@app.route("/charts/<path:filename>", methods=["GET", "POST"])
def charts(filename):
    try:
        df = read_dataset(filename)
    except FileNotFoundError:
        flash("File not found.", "danger")
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for("home"))

    profile = analyze_dataframe(df)

    # <-- show only the top 4 suggestions (highest suitability scores) as previews
    chart_previews = generate_plotly_divs(df, profile, max_charts=4)

    if request.method == "POST":
        chart_type = request.form.get("chart_type")
        xcol = request.form.get("xcol") or None
        ycol = request.form.get("ycol") or None
        return redirect(url_for("view_chart", filename=filename, chart_type=chart_type, xcol=xcol, ycol=ycol))

    columns = [c["name"] for c in profile["columns"]]
    numeric_columns = profile.get("numeric_columns", [])

    return render_template(
        "charts.html",
        filename=filename,
        profile=profile,
        previews=chart_previews,
        columns=columns,
        numeric_columns=numeric_columns
    )


@app.route("/view_chart/<path:filename>")
def view_chart(filename):
    try:
        df = read_dataset(filename)
    except FileNotFoundError:
        flash("File not found.", "danger")
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for("home"))

    chart_type = request.args.get("chart_type")
    xcol = request.args.get("xcol")
    ycol = request.args.get("ycol")

    try:
        div, title = generate_single_plot_div(df, chart_type=chart_type, xcol=xcol, ycol=ycol)
    except Exception as e:
        flash(f"Could not generate chart: {e}", "danger")
        return redirect(url_for("charts", filename=filename))
    from models.history import History

    if "user_id" in session:
        history = History(
        user_id=session["user_id"],
        filename=filename,
        chart_type=request.args.get("chart_type")
    )
    db.session.add(history)
    db.session.commit()

    return render_template("view_chart.html", chart_div=div, title=title, filename=filename)

# backward-compatible redirect
@app.route("/dashboard/<path:filename>")
def dashboard_redirect(filename):
    return redirect(url_for("analysis", filename=filename))

app.permanent_session_lifetime = timedelta(days=7)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

