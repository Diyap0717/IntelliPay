# trial_ocr_code.py
import os
from google.cloud import vision
import io

# Initialize Google Vision client
credential_path = r"C:\Users\dpate331\Downloads\PersonalProjects\OCR_Project\Google_Vision\ocrpro-safe-key.json"
client = vision.ImageAnnotatorClient.from_service_account_file(credential_path)


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
