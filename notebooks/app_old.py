import streamlit as st
import os

# Import OCR and Transform modules
from trial_ocr_code import extract_text_from_image
from Transform_data import pipeline_from_raw_text, save_df_to_output

# Paths
OUTPUT_FOLDER = "Resultant CSVs"
OUTPUT_FILENAME = "output_TestCase6.csv"
OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, OUTPUT_FILENAME)

# App title
st.set_page_config(page_title="Tip Tracking OCR", page_icon="💵")
st.title("💵 Tip Tracking OCR System")

# Step 1: Upload image
uploaded_file = st.file_uploader("Upload an envelope image", type=["jpg", "jpeg", "png"])

# --- Clear session state if uploaded_file is removed ---
if uploaded_file is None:
    if "ocr_text" in st.session_state:
        del st.session_state["ocr_text"]

# Step 2: Show image if uploaded
if uploaded_file:
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    # Save temp copy
    temp_path = os.path.join("temp", uploaded_file.name)
    os.makedirs("temp", exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Step 3: Run OCR button
    if st.button("Run OCR"):
        with st.spinner("Extracting text..."):
            raw_text = extract_text_from_image(temp_path)
        st.session_state["ocr_text"] = raw_text

# Step 4: Show extracted text and Transform button only if OCR has been run
if uploaded_file and "ocr_text" in st.session_state:
    st.subheader("📄 Extracted Text")
    st.text(st.session_state["ocr_text"])

    if st.button("Transform & Save"):
        with st.spinner("Transforming data..."):
            df = pipeline_from_raw_text(st.session_state["ocr_text"])
            save_df_to_output(df, OUTPUT_FOLDER, OUTPUT_FILENAME)
        st.success(f"✅ Data appended to {OUTPUT_PATH}")
        st.dataframe(df)
