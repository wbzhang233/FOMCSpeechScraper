import os
from PyPDF2 import PdfReader
import requests


def read_pdf_file(pdf_filename: str):
    if os.path.exists(pdf_filename):
        reader = PdfReader(pdf_filename)
        print("----" * 20)
        print("{} has been read.".format(pdf_filename))
        return "\n\n".join([page.extract_text() for page in reader.pages]).strip("\n ")
    else:
        return ""


def is_download_existed(filepath: str):
    if os.path.exists(filepath):
        return True
    else:
        return False


def download_pdf(pdf_url: str, file_name: str, save_path: str):
    if is_download_existed(f"{save_path}/{file_name}"):
        print("PDF {} has been downloaded.".format(file_name))
        return
    response = requests.get(pdf_url)

    if response.status_code == 200:
        with open(f"{save_path}/{file_name}", "wb") as f:
            f.write(response.content)
        print("PDF {} downloaded successfully.".format(file_name))
    else:
        print("Failed to download PDF. Status code:", response.status_code)


def is_download_complete(download_dir):
    for file in os.listdir(download_dir):
        if file.endswith(".crdownload"):
            return False
    return True
