import os
from werkzeug.datastructures import FileStorage

ALLOWED_EXTENSIONS = {"csv", "xlsx"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file_obj: FileStorage, upload_folder: str, filename: str) -> str:
    save_path = os.path.join(upload_folder, filename)
    file_obj.save(save_path)
    return save_path
