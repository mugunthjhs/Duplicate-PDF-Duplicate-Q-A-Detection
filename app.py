import streamlit as st
import os
import time
import tempfile
import shutil
import json

# === DEBUG: Show available files in the current directory ===
st.write("📂 Files in current directory:", os.listdir())

# === Helper to attempt imports individually ===
def safe_import(module_name, func_name):
    try:
        mod = __import__(module_name)
        func = getattr(mod, func_name)
        st.success(f"✅ Found {module_name}.py → {func_name}")
        return func
    except ModuleNotFoundError:
        st.error(f"❌ Missing file: {module_name}.py — using dummy for now.")
    except AttributeError:
        st.error(f"❌ {module_name}.py found but missing function `{func_name}` — using dummy for now.")

    # Dummy fallback
    def create_dummy_output_returnbased(subject):
        dummy_json_data = [{"message": f"This is a dummy JSON for {subject} (returned directly)."}]
        dummy_report_data = f"This is a dummy duplicate report for {subject} (returned directly).\nNo duplicates were found."
        time.sleep(1)
        return dummy_json_data, dummy_report_data

    return lambda path=None, s=module_name: create_dummy_output_returnbased(s)

# === Import each processor individually ===
process_english_pdf = safe_import("english_main", "process_english_pdf")
process_science_pdf = safe_import("science_main", "process_science_pdf")
process_social_science_pdf = safe_import("social_science_main", "process_social_science_pdf")
process_maths_pdf = safe_import("maths_main", "process_maths_pdf")
process_tamil_pdf = safe_import("tamil_main", "process_tamil_pdf")

# --- Subject-specific processor map ---
subject_processors = {
    "English": process_english_pdf,
    "Science": process_science_pdf,
    "Social_Science": process_social_science_pdf,
    "Maths": process_maths_pdf,
    "Tamil": process_tamil_pdf,
}

# --- Page Setup ---
st.set_page_config(page_title="Duplicate Q/A Finder", layout="wide")
st.markdown("<h1 style='text-align: center; color: #2E86C1;'>📚 Duplicate Q/A Finder</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🔄 Refresh"):
        st.session_state.uploader_key += 1
        st.session_state.board = "Select"
        st.rerun()

    board = st.selectbox(
        "Select the educational board",
        ["Select", "CBSE", "TNSCERT", "NIOS"],
        key="board"
    )

    grade_range = None
    if board == "CBSE":
        grade_range = st.selectbox(
            "Select Grade",
            ["Select", "6", "7", "8", "9", "10", "11", "12"]
        )

# --- Main Logic ---
if board == "Select":
    st.info("📌 Please select the educational board from the sidebar.")

elif board in ["TNSCERT", "NIOS"]:
    st.info(f"⚙️ Processing for **{board}** will be available soon.")

elif board == "CBSE":
    if grade_range == "Select":
        st.info("📌 Please select the grade from the sidebar.")
    elif grade_range in ["11", "12"]:
        st.info(f"⚙️ Processing for CBSE Grade {grade_range} will be available soon.")
    elif grade_range in ["6", "7", "8", "9", "10"]:
        # Determine available subjects based on grade
        if grade_range in ["6", "7"]:
            available_subjects = ["Select", "English", "Tamil", "Maths", "Science", "Social_Science"]
        elif grade_range in ["8", "9", "10"]:
            available_subjects = ["Select", "English", "Tamil", "Maths", "Science", "History", "Political Science", "Geography"]

        subject = st.selectbox("Select Subject", available_subjects)

        if subject == "Select":
            st.info("📌 Please select the subject.")
        elif subject not in subject_processors:
            st.info(f"⚙️ Support for **{subject}** is coming soon.")
        else:
            if subject == "Tamil":
                uploader_label = "Upload DOCX File"
                accepted_types = ["docx"]
                temp_file_suffix = ".docx"
            else:
                uploader_label = "Upload PDF File"
                accepted_types = ["pdf"]
                temp_file_suffix = ".pdf"
            
            uploaded_file = st.file_uploader(
                uploader_label,
                type=accepted_types,
                key=st.session_state.uploader_key
            )

            if uploaded_file:
                base_filename, _ = os.path.splitext(uploaded_file.name)
                download_txt_filename = f"{base_filename}_duplicate_report.txt"
                download_json_filename = f"{base_filename}_extracted_json.json"

                temp_file_path = None
                json_content = None
                duplicate_content = None

                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=temp_file_suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        temp_file_path = tmp_file.name

                    with st.spinner(f"⏳ Processing your {subject} file..."):
                        if subject == "Tamil":
                            processor_result = subject_processors[subject](temp_file_path)
                            if isinstance(processor_result, (list, tuple)) and len(processor_result) == 2:
                                json_content, duplicate_content = processor_result
                            else:
                                st.warning(f"Processor for '{subject}' did not return the expected data.")
                                json_content, duplicate_content = None, None
                        else:
                            subject_processors[subject](temp_file_path)
                            output_folder = f"output_{subject.lower()}"
                            json_path = os.path.join(output_folder, f"{subject.lower()}_questions.json")
                            duplicate_txt_path = os.path.join(output_folder, "duplicate_output.txt")

                            if os.path.exists(json_path):
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    json_content = json.load(f)
                            if os.path.exists(duplicate_txt_path):
                                with open(duplicate_txt_path, 'r', encoding='utf-8') as f:
                                    duplicate_content = f.read()

                    if json_content and duplicate_content is not None:
                        st.success("✅ Processing complete!")
                        st.markdown("<h4 style='text-align: center;'>📥 Download Results</h4>", unsafe_allow_html=True)
                        dl1, dl2 = st.columns(2)

                        with dl1:
                            st.download_button(
                                "Download Duplicate Report (.txt)",
                                data=duplicate_content,
                                file_name=download_txt_filename,
                                mime="text/plain"
                            )
                        with dl2:
                            json_string = json.dumps(json_content, indent=4, ensure_ascii=False)
                            st.download_button(
                                "Download JSON File",
                                data=json_string,
                                file_name=download_json_filename,
                                mime="application/json"
                            )

                        st.markdown(f"<h4 style='text-align: center;'>🔍 Duplicate Questions in {subject}</h4>", unsafe_allow_html=True)
                        if "No duplicates were found" not in duplicate_content and duplicate_content.strip():
                            st.text_area("", duplicate_content, height=300, label_visibility="collapsed")
                        else:
                            st.info("✅ No duplicates were found in the document.")
                    else:
                        st.error("❌ Failed to extract content. Please check the file format and processor logic.")

                except Exception as e:
                    st.error("⚠️ Error during processing:")
                    st.exception(e)

                finally:
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                    for s in subject_processors:
                        output_folder = f"output_{s.lower()}"
                        if os.path.exists(output_folder):
                            shutil.rmtree(output_folder)
