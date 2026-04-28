import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
import pandas as pd

import markdown

from flask_migrate import Migrate

from ai_extension.llm.insight_engine import generate_insights
from ai_extension.chat.pandas_agent import ask_question
from ai_extension.report.pdf_generator import generate_pdf

from utils.file_handler import save_uploaded_file, allowed_file
from utils.data_analyzer import analyze_dataframe
from utils.chart_generator import generate_plotly_divs, generate_single_plot_div

from datetime import timedelta
from config import Config
from models.db import db
from models.history import History

from utils.data_cleaning import analyze_cleanliness
from utils.dax_generator import generate_dax

current_df = None
current_insights = None
current_summary = None
current_charts = []

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
    upload_folder = app.config["UPLOAD_FOLDER"]

    filepath = os.path.join(upload_folder, filename)

    if not os.path.exists(filepath):
        # try matching real filename
        for f in os.listdir(upload_folder):
            if f.endswith(filename):
                filepath = os.path.join(upload_folder, f)
                break

    if not os.path.exists(filepath):
        return None  # ⚠️ DO NOT CRASH

    session["current_dataset"] = os.path.basename(filepath)

    if filepath.endswith(".csv"):
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
        return redirect(url_for("auth.home"))

    if not allowed_file(file.filename):
        flash("❌ Only CSV or Excel files allowed", "danger")
        return redirect(url_for("auth.home"))

    filename = secure_filename(file.filename)

    # ❌ REMOVE THIS LINE
    # filepath = save_uploaded_file(file, ..., filename)

    # ✅ KEEP ONLY THIS
    filepath = save_uploaded_file(file, app.config["UPLOAD_FOLDER"])

    if not filepath:
        flash("❌ File is open/locked. Close Excel and try again.", "danger")
        return redirect(url_for("auth.home"))

    # ✅ SAVE CURRENT DATASET (ABSOLUTE PATH)
    with open("current_dataset.txt", "w") as f:
        f.write(filepath)

    # ✅ TRY READING FILE (VALIDATION)
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        # ❌ EMPTY FILE CHECK
        if df.empty:
            flash("❌ Uploaded file is empty", "danger")
            os.remove(filepath)
            return redirect(url_for("auth.home"))

        # ❌ INVALID STRUCTURE
        if df.shape[1] == 0:
            flash("❌ File has no usable columns", "danger")
            os.remove(filepath)
            return redirect(url_for("auth.home"))

    except Exception as e:
        os.remove(filepath)
        flash(f"❌ Invalid dataset format: {str(e)}", "danger")
        return redirect(url_for("auth.home"))

    # ✅ SESSION SET (CRITICAL)
    session["current_file"] = filename
    session["current_dataset"] = filename

    return redirect(url_for("cleaning_page", filename=filename))

@app.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")

@app.route("/analysis/<path:filename>")
def analysis(filename):
    global current_df, current_insights, current_summary

    # -------------------------------
    # 1. LOAD DATASET (SAFE)
    # -------------------------------
    try:
        df = read_dataset(filename)

        # ✅ CRITICAL FIX (ADD THIS LINE)
        session["current_file"] = filename
        session["current_dataset"] = filename
    except Exception as e:
        print("DATA LOAD ERROR:", e)
        return f"<h3>Error loading dataset: {e}</h3>"

    # -------------------------------
    # 2. AI INITIALIZATION (SAFE + NON-BREAKING)
    # -------------------------------
    try:
        current_df = df.head(500)

        current_summary = {
            "rows": len(df),
            "columns": list(df.columns)
        }

        current_insights = generate_insights(current_df)

    except Exception as ai_error:
        print("AI ERROR:", ai_error)
        current_insights = "AI insights unavailable"

    # -------------------------------
    # 3. EXISTING LOGIC (UNCHANGED)
    # -------------------------------
    profile = analyze_dataframe(df)

    numeric = df.select_dtypes(include=["number"])
    numeric_summary = (
        numeric.describe().round(4).to_dict()
        if not numeric.empty else None
    )

    cleaning_report = analyze_cleanliness(df)
    dax_recommendations = generate_dax(df)

    existing = None

    if "user_id" in session:
        existing = History.query.filter_by(
            user_id=session["user_id"],
            filename=filename
        ).first()

    elif "guest_id" in session:
        existing = History.query.filter_by(
            guest_id=session["guest_id"],
            filename=filename
        ).first()

    if not existing:
        new = History(
            user_id=session.get("user_id"),
            guest_id=session.get("guest_id"),
            filename=filename,
            chart_type="auto"
        )
        db.session.add(new)
        db.session.commit()

    # -------------------------------
    # 4. FINAL RENDER (UNCHANGED UI)
    # -------------------------------
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

    # ✅ ADD THIS LINE
    session["current_file"] = filename
    session["current_dataset"] = filename

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
    date_cols = df.select_dtypes(include=["datetime"]).columns
    if len(date_cols):
        flash("ℹ️ Date columns detected. Some statistical measures skipped.", "info")
    return render_template(
        "cleaning.html",
        filename=filename,
        cleaning=cleaning_report,
        dax=dax_recommendations
    )



from flask import send_file

@app.route("/download_report")
def download_report():

    filename = session.get("current_file")

    if not filename:
        return "<h3>No dataset loaded.</h3>"

    df = read_dataset(filename)

    try:
        insights = generate_insights(df.head(500))
    except Exception as e:
        insights = f"Insights unavailable: {e}"

    summary = {
        "rows": len(df),
        "columns": list(df.columns)
    }

    generate_pdf(
        "report.pdf",
        summary=summary,
        insights=insights,
        charts=[]
    )

    return send_file("report.pdf", as_attachment=True)

@app.route("/ai")
def ai_home():
    return render_template("ai_mode/home.html")


from flask import session, redirect


import os

@app.route("/ai/dashboard")
def ai_dashboard():
    import subprocess
    import time
    import os

    filename = session.get("current_file")

    if not filename:
        return "<h3>❌ No dataset found. Please upload first.</h3>"

    # ✅ FIXED PATH
    dataset_path = os.path.abspath(os.path.join("uploads", filename))

    # Start Streamlit if not running
    try:
        import requests
        requests.get("http://localhost:8501")
    except:
        subprocess.Popen([
            "streamlit",
            "run",
            "streamlit_app.py",
            "--server.port=8501"
        ])
        time.sleep(2)

    return redirect(f"http://localhost:8501/?dataset={dataset_path}")
@app.route("/ai/insights")
def ai_insights():

    global current_insights

    filename = session.get("current_file")

    if not filename:
        return "<h3>No dataset loaded. Upload first.</h3>"

    df = read_dataset(filename)

    if not current_insights:
        current_insights = generate_insights(df.head(100))

    html_insights = markdown.markdown(current_insights)

    return render_template(
        "ai_mode/insights.html",
        html_insights=html_insights
    )

@app.route("/ai/chat", methods=["GET", "POST"])
def ai_chat():

    filename = session.get("current_file")

    if not filename:
        return "<h3>No dataset loaded. Please upload first.</h3>"

    df = read_dataset(filename)

    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        question = request.form["question"]

        try:
            raw_answer = ask_question(df.head(100), question)
            answer = markdown.markdown(raw_answer, extensions=["fenced_code", "tables"])
        except Exception as e:
            answer = f"Error: {e}"

        session["chat_history"].append({
            "question": question,
            "answer": answer
        })

        session.modified = True  # IMPORTANT

    return render_template(
        "ai_mode/chat.html",
        chat_history=session["chat_history"]
    )

@app.route("/ai/report")
def ai_report():
    return render_template("ai_mode/report.html")

@app.route("/history")
def history():
    files = []

    upload_folder = app.config["UPLOAD_FOLDER"]

    if os.path.exists(upload_folder):
        for f in os.listdir(upload_folder):
            full_path = os.path.join(upload_folder, f)

            if os.path.isfile(full_path):
                files.append(f)

    return render_template("history.html", files=files)



@app.route("/delete/<filename>")
def delete_file(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print("File delete error:", e)

    try:
        History.query.filter_by(filename=filename).delete()
        db.session.commit()
    except Exception as e:
        print("DB delete error:", e)

    session.pop("current_file", None)

    # 🔥 force reload
    return redirect(url_for("history") + "?refresh=1")

@app.route("/debug")
def debug():
    return str(session.get("current_file"))

if __name__ == "__main__":
    app.run(debug=True)