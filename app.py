import streamlit as st
import os
import time
import tempfile
import shutil

# Import your processors (add others in future)
from english_main import process_english_pdf
from science_main import process_science_pdf
from social_science_main import process_social_science_pdf
from maths_main import process_maths_pdf


# --- Subject-specific processor map ---
subject_processors = {
    "English": process_english_pdf,
    "Science": process_science_pdf,
    "Social_Science": process_social_science_pdf,
    "Maths": process_maths_pdf,
    # Add more here
}

# --- Page Setup ---
st.set_page_config(page_title="Duplicate Q/A Finder", layout="centered")
st.markdown("<h1 style='text-align: center;'>📚 Duplicate Q/A Finder</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- Subject & File Upload Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    subject = st.selectbox("Select Subject", list(subject_processors.keys()) + ["Tamil", "Hindi"])

with col2:
    uploaded_file = st.file_uploader("Upload PDF File", type=["pdf"])

# --- Subject Availability ---
if subject not in subject_processors:
    st.info(f"⚙️ Support for **{subject}** is coming soon. Please check back later.")

# --- Process File if Supported & Uploaded ---
if subject in subject_processors and uploaded_file:
    output_folder = f"output_{subject.lower()}"
    temp_pdf_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.read())
            temp_pdf_path = tmp_file.name

        with st.spinner(f"⏳ Processing your {subject} PDF..."):
            subject_processors[subject](temp_pdf_path)
            time.sleep(1)

        json_path = os.path.join(output_folder, f"{subject.lower()}_questions.json")
        duplicate_txt_path = os.path.join(output_folder, "duplicate_output.txt")

        if os.path.exists(json_path) and os.path.exists(duplicate_txt_path):
            st.success("✅ Processing complete!")

            st.markdown("<h4 style='text-align: center;'>📥 Download Results</h4>", unsafe_allow_html=True)
            dl1, dl2 = st.columns(2)

            with dl1:
                with open(duplicate_txt_path, "rb") as f:
                    st.download_button(
                        "Download Duplicate Report (.txt)", f, file_name="duplicate_report.txt", mime="text/plain"
                    )

            with dl2:
                with open(json_path, "rb") as f:
                    st.download_button(
                        "Download Extracted Questions (.json)", f, file_name="extracted_questions.json", mime="application/json"
                    )
            st.markdown(f"<h4 style='text-align: center;'>🔍 Duplicate Questions in {subject}</h4>", unsafe_allow_html=True)
            with open(duplicate_txt_path, "r", encoding="utf-8") as f:
                duplicate_content = f.read()

            st.text_area("", duplicate_content, height=300, label_visibility="collapsed")

            
        else:
            st.error("❌ Failed to extract content. Please check the PDF format.")

    except Exception as e:
        st.error("⚠️ Error during processing:")
        st.exception(e)

    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        if os.path.exists(output_folder):
            shutil.rmtree(output_folder)
