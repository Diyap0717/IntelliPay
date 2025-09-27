import streamlit as st
import os

# Import OCR and Transform modules
from trial_ocr_code import extract_text_from_image
from Transform_data import pipeline_from_raw_text, save_df_to_output

# Paths
OUTPUT_FOLDER = "Resultant CSVs"
OUTPUT_FILENAME = "output_TestCase6.csv"
OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, OUTPUT_FILENAME)

# ----------------------- Page Config -----------------------
st.set_page_config(
    page_title="Tip Tracking OCR",
    page_icon="💵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------- Sidebar -----------------------
st.sidebar.title("ℹ️ Instructions")
st.sidebar.markdown("""
1. Upload an envelope image (.jpg, .jpeg, .png).  
2. Click **Run OCR** to extract text.  
3. Review extracted text.  
4. Click **Transform & Save** to generate CSV.  
5. Download CSV if needed.  
""")

# Optional: Background color styling
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f9f9f9;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------- Main Title -----------------------
st.title("💵 Tip Tracking OCR System")

# ----------------------- Upload Section -----------------------
col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader(
        "Upload an envelope image",
        type=["jpg", "jpeg", "png"],
        key="uploader"
    )

# ----------------------- Clear session state if image removed -----------------------
if uploaded_file is None:
    if "ocr_text" in st.session_state:
        del st.session_state["ocr_text"]

# ----------------------- Display Uploaded Image -----------------------
with col2:
    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

        # Save temp copy
        temp_path = os.path.join("temp", uploaded_file.name)
        os.makedirs("temp", exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

# ----------------------- OCR Section -----------------------
if uploaded_file:
    if st.button("Run OCR", key="run_ocr"):
        with st.spinner("🔍 Extracting text..."):
            raw_text = extract_text_from_image(temp_path)
            st.session_state["ocr_text"] = raw_text
        st.success("✅ OCR Extraction Complete")

# ----------------------- Show Extracted Text & Transform -----------------------
if uploaded_file and "ocr_text" in st.session_state:

    # Use expander for clean layout
    with st.expander("📄 Extracted Text"):
        st.text_area("OCR Output", st.session_state["ocr_text"], height=200)

    if st.button("Transform & Save", key="transform_save"):
        with st.spinner("⚙️ Transforming data..."):
            df = pipeline_from_raw_text(st.session_state["ocr_text"])
            save_df_to_output(df, OUTPUT_FOLDER, OUTPUT_FILENAME)
        st.success(f"✅ Data saved to {OUTPUT_PATH}")

        # Display transformed data in expander
        with st.expander("📊 Transformed Data"):
            st.dataframe(df.style.format({"Tips": "${:.2f}"}).background_gradient(subset=["Tips"], cmap="Greens"))

        # Download button
        st.download_button(
            label="⬇️ Download CSV",
            data=open(OUTPUT_PATH, "rb").read(),
            file_name=OUTPUT_FILENAME,
            mime="text/csv"
        )
