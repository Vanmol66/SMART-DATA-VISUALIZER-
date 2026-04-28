import os

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, upload_folder):
    filename = file.filename

    # ensure folder exists
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, filename)

    # 🔥 remove old file if exists (prevents duplicates)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass

    file.save(filepath)

    return filepath