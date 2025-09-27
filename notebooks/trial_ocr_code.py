import streamlit as st
import json
from google.oauth2 import service_account
from google.cloud import vision
import io

# Load the credentials from Streamlit Secrets
creds_dict = json.loads(st.secrets["google"]["credentials"])
credentials = service_account.Credentials.from_service_account_info(creds_dict)

# Create the Vision API client with credentials
client = vision.ImageAnnotatorClient(credentials=credentials)


def extract_text_from_image(image_path: str) -> str:
    """
    Extract text from a single image using Google Vision OCR.
    Returns the extracted text as a string.
    """
    with io.open(image_path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f"Google Vision API error: {response.error.message}")

    if texts:
        return texts[0].description.strip()
    else:
        return ""
