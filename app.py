import streamlit as st
import os
import time
import tempfile
import shutil

try:
    from english_main import process_english_pdf
    from science_main import process_science_pdf
    from social_science_main import process_social_science_pdf
    from maths_main import process_maths_pdf
except ImportError:
    st.error("Could not find processor files (e.g., english_main.py). Using dummy functions for demonstration.")
    def create_dummy_output(subject):
        output_folder = f"output_{subject.lower().replace('_', '')}"
        os.makedirs(output_folder, exist_ok=True)
        with open(os.path.join(output_folder, f"{subject.lower().replace('_', '')}_questions.json"), "w") as f:
            f.write('{"message": "This is a dummy JSON file."}')
        with open(os.path.join(output_folder, "duplicate_output.txt"), "w") as f:
            f.write("This is a dummy duplicate report.\nNo duplicates were found.")
        time.sleep(2)

    def process_english_pdf(path): create_dummy_output("English")
    def process_science_pdf(path): create_dummy_output("Science")
    def process_social_science_pdf(path): create_dummy_output("Social_Science")
    def process_maths_pdf(path): create_dummy_output("Maths")


# --- Subject-specific processor map ---
subject_processors = {
    "English": process_english_pdf,
    "Science": process_science_pdf,
    "Social_Science": process_social_science_pdf,
    "Maths": process_maths_pdf,
}

# --- Page Setup ---
st.set_page_config(page_title="Duplicate Q/A Finder", layout="centered")
st.markdown("<h1 style='text-align: center;'>📚 Duplicate Q/A Finder</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

if st.button("🔄 Start Over / Refresh Page"):
    st.session_state.uploader_key += 1
    st.rerun()


# --- Subject & File Upload Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    subject = st.selectbox("Select Subject", list(subject_processors.keys()) + ["Tamil", "Hindi"])

with col2:
    # Use the changing key from session state
    uploaded_file = st.file_uploader(
        "Upload PDF File",
        type=["pdf"],
        key=st.session_state.uploader_key
    )


# --- Subject Availability ---
if subject not in subject_processors:
    st.info(f"⚙️ Support for **{subject}** is coming soon. Please check back later.")


# --- Process File if Supported & Uploaded ---
if subject in subject_processors and uploaded_file:
    base_filename, _ = os.path.splitext(uploaded_file.name)
    download_txt_filename = f"{base_filename}_duplicate_report.txt"
    download_json_filename = f"{base_filename}_extracted_json.json"

    # Use a clean folder name
    output_folder = f"output_{subject.lower().replace('_', '')}"
    temp_pdf_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_pdf_path = tmp_file.name

        with st.spinner(f"⏳ Processing your {subject} PDF..."):
            subject_processors[subject](temp_pdf_path)

        json_path = os.path.join(output_folder, f"{subject.lower().replace('_', '')}_questions.json")
        duplicate_txt_path = os.path.join(output_folder, "duplicate_output.txt")

        if os.path.exists(json_path) and os.path.exists(duplicate_txt_path):
            st.success("✅ Processing complete!")

            st.markdown("<h4 style='text-align: center;'>📥 Download Results</h4>", unsafe_allow_html=True)
            dl1, dl2 = st.columns(2)

            with dl1:
                with open(duplicate_txt_path, "rb") as f:
                    st.download_button(
                        "Download Duplicate Report (.txt)", f,
                        file_name=download_txt_filename, mime="text/plain"
                    )
            with dl2:
                with open(json_path, "rb") as f:
                    st.download_button(
                        "Download JSON File", f,
                        file_name=download_json_filename, mime="application/json"
                    )
            
            st.markdown(f"<h4 style='text-align: center;'>🔍 Duplicate Questions in {subject}</h4>", unsafe_allow_html=True)
            with open(duplicate_txt_path, "r", encoding="utf-8") as f:
                duplicate_content = f.read()

            if duplicate_content.strip():
                st.text_area("", duplicate_content, height=300, label_visibility="collapsed")
            else:
                st.info("✅ No duplicates were found in the document.")

        else:
            st.error("❌ Failed to extract content. Please check the PDF format and processor logic.")

    except Exception as e:
        st.error("⚠️ Error during processing:")
        st.exception(e)

    finally:
        # Cleanup temporary files and folders
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        if os.path.exists(output_folder):
            shutil.rmtree(output_folder)
