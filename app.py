import streamlit as st
import os
import time
import tempfile
import shutil
import json
import re

# --- Processor Imports & Dummy Functions ---
# This structure correctly handles cases where modules might be missing.
try:
    from cbse.six_to_ten_studies.english_main import process_english_pdf
    from cbse.six_to_ten_studies.science_main import process_science_pdf
    from cbse.six_to_ten_studies.social_science_main import process_social_science_pdf
    from cbse.six_to_ten_studies.maths_main import process_maths_pdf
    from cbse.six_to_ten_studies.tamil_main import process_tamil_pdf
    from cbse.six_to_ten_studies.hindi_main import process_hindi_pdf
    from cbse.higher_studies.biotechnology_main import process_biotechnology_docx
    from cbse.higher_studies.business_studies_main import process_business_studies_docx
    from cbse.higher_studies.chemistry_main import process_chemistry_docx
    from cbse.higher_studies.physics_main import process_physics_docx
except ImportError:
    st.error("One or more processor files were not found. Please ensure all processor scripts are in the correct directory. Using dummy functions for demonstration.")

    def create_dummy_output_filebased(subject):
        output_folder = f"output_{subject.lower()}"
        os.makedirs(output_folder, exist_ok=True)
        json_filename = f"{subject.lower()}_questions.json"
        with open(os.path.join(output_folder, json_filename), "w", encoding="utf-8") as f:
            json.dump([{"message": f"This is a dummy JSON for {subject}."}], f)
        with open(os.path.join(output_folder, "duplicate_output.txt"), "w", encoding="utf-8") as f:
            f.write(f"This is a dummy duplicate report for {subject}.\nNo duplicates were found.")
        time.sleep(1)

    def create_dummy_output_returnbased(subject):
        dummy_json_data = [{"message": f"This is a dummy JSON for {subject} (returned directly)."}]
        dummy_report_data = f"This is a dummy duplicate report for {subject} (returned directly).\nNo duplicates were found."
        time.sleep(1)
        return dummy_json_data, dummy_report_data

    # Assign dummy functions
    process_english_pdf = lambda path: create_dummy_output_filebased("english")
    process_science_pdf = lambda path: create_dummy_output_filebased("science")
    process_social_science_pdf = lambda path: create_dummy_output_filebased("social_science")
    process_maths_pdf = lambda path: create_dummy_output_filebased("maths")
    process_hindi_pdf = lambda path: create_dummy_output_filebased("hindi")
    process_biotechnology_docx = lambda path: create_dummy_output_filebased("biotechnology")
    process_business_studies_docx = lambda path: create_dummy_output_filebased("business_studies")
    process_chemistry_docx = lambda path: create_dummy_output_filebased("chemistry")
    process_physics_docx = lambda path: create_dummy_output_filebased("physics")
    process_tamil_pdf = lambda path: create_dummy_output_returnbased("Tamil")


# --- Subject Configuration ---
# Central map to define how each subject should be processed.
subject_processors = {
    # Grades 6-10
    "English": {"func": process_english_pdf, "type": "file", "folder": "english", "file_ext": "pdf"},
    "Science": {"func": process_science_pdf, "type": "file", "folder": "science", "file_ext": "pdf"},
    "Social_Science": {"func": process_social_science_pdf, "type": "file", "folder": "social_science", "file_ext": "pdf"},
    "Maths": {"func": process_maths_pdf, "type": "file", "folder": "maths", "file_ext": "pdf"},
    "Tamil": {"func": process_tamil_pdf, "type": "return", "folder": None, "file_ext": "docx"},
    "Hindi": {"func": process_hindi_pdf, "type": "file", "folder": "hindi", "file_ext": "docx"},
    
    # Aliases for Social Science point to the same processor
    "History": {"func": process_social_science_pdf, "type": "file", "folder": "social_science", "file_ext": "pdf"},
    "Political Science": {"func": process_social_science_pdf, "type": "file", "folder": "social_science", "file_ext": "pdf"},
    "Geography": {"func": process_social_science_pdf, "type": "file", "folder": "social_science", "file_ext": "pdf"},

    # Grades 11-12
    "Biotechnology": {"func": process_biotechnology_docx, "type": "file", "folder": "biotechnology", "file_ext": "docx"},
    "Commerce": {"func": process_business_studies_docx, "type": "file", "folder": "business_studies", "file_ext": "docx"},
    "Chemistry": {"func": process_chemistry_docx, "type": "file", "folder": "chemistry", "file_ext": "docx"},
    "Physics": {"func": process_physics_docx, "type": "file", "folder": "physics", "file_ext": "docx"},
}


def run_file_processor(subject):
    """
    Handles the Streamlit UI and logic for uploading a file, processing it,
    and displaying the results for a given subject.
    """
    config = subject_processors.get(subject)
    
    if not config:
        st.info(f"⚙️ Processing for {subject} will be available soon.")
        return

    file_extension = config['file_ext']
    uploader_label = f"Upload {file_extension.upper()} File"
    
    uploaded_file = st.file_uploader(
        uploader_label,
        type=[file_extension],
        key=st.session_state.uploader_key
    )

    if not uploaded_file:
        return

    base_filename, _ = os.path.splitext(uploaded_file.name)
    download_txt_filename = f"{base_filename}_duplicate_report.txt"
    download_json_filename = f"{base_filename}_questions.json"

    temp_file_path = None
    output_folder_to_clean = f"output_{config['folder']}" if config['type'] == 'file' else None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_file_path = tmp_file.name

        json_content, duplicate_content = None, None
        
        with st.spinner(f"⏳ Processing your {subject} file... This may take a moment."):
            processor_function = config['func']
            
            if config['type'] == 'return':
                processor_result = processor_function(temp_file_path)
                if isinstance(processor_result, (list, tuple)) and len(processor_result) == 2:
                    json_content, duplicate_content = processor_result
                else:
                    st.warning(f"Processor for '{subject}' did not return the expected data.")
            
            elif config['type'] == 'file':
                processor_function(temp_file_path)
                json_path = os.path.join(output_folder_to_clean, f"{config['folder']}_questions.json")
                duplicate_txt_path = os.path.join(output_folder_to_clean, "duplicate_output.txt")
                
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_content = json.load(f)
                if os.path.exists(duplicate_txt_path):
                    with open(duplicate_txt_path, 'r', encoding='utf-8') as f:
                        duplicate_content = f.read()

        if json_content is not None and duplicate_content is not None:
            st.success("✅ Processing complete!")

            st.markdown("<h4 style='text-align: center;'>📥 Download Results</h4>", unsafe_allow_html=True)
            dl1, dl2 = st.columns(2)

            with dl1:
                st.download_button("Download Duplicate Report (.txt)", data=duplicate_content, file_name=download_txt_filename, mime="text/plain")
            with dl2:
                json_string = json.dumps(json_content, indent=4, ensure_ascii=False)
                st.download_button("Download JSON File", data=json_string, file_name=download_json_filename, mime="application/json")

            st.markdown(f"<h4 style='text-align: center;'>🔍 Duplicate Questions Preview</h4>", unsafe_allow_html=True)
            
            if not re.search(r"no duplicates found", duplicate_content, re.IGNORECASE) and duplicate_content.strip():
                st.text_area("Duplicate Report", duplicate_content, height=300, label_visibility="collapsed")
            else:
                st.info("✅ No duplicates were found in the document.")
        else:
            st.error("❌ Failed to extract content. Please check the file format and review the console logs for processing errors.")

    except Exception as e:
        st.error("⚠️ An unexpected error occurred in the application:")
        st.exception(e)

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if output_folder_to_clean and os.path.exists(output_folder_to_clean):
            shutil.rmtree(output_folder_to_clean)


# --- Page Setup & Main UI ---
st.set_page_config(page_title="Duplicate Q/A Finder", layout="wide")
st.markdown("<h1 style='text-align: center; color: #2E86C1;'>📚 Duplicate Q/A Finder</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🔄 Clear & Refresh"):
        keys_to_reset = ['board', 'grade_range', 'subject']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.uploader_key += 1
        st.rerun()

    board = st.selectbox("Select Board", ["Select", "CBSE", "TNSCERT", "NIOS"], key="board")
    grade_range = "Select"
    if board == "CBSE":
        grade_range = st.selectbox("Select Grade", ["Select", "6", "7", "8", "9", "10", "11", "12"], key="grade_range")

# --- Main Application Flow ---
if board == "Select":
    st.info("📌 Please select an educational board from the sidebar to begin.")
elif board in ["TNSCERT", "NIOS"]:
    st.info(f"⚙️ Processing for {board} will be available soon.")
elif board == "CBSE":
    if grade_range == "Select":
        st.info("📌 Please select a grade from the sidebar.")
    else:
        available_subjects = ["Select"]
        if grade_range in ["6", "7"]:
            available_subjects.extend(["English", "Tamil", "Maths", "Science", "Social_Science", "Hindi"])
        elif grade_range in ["8", "9", "10"]:
            available_subjects.extend(["English", "Tamil", "Maths", "Science", "History", "Political Science", "Geography", "Hindi"])
        elif grade_range == "11":
            available_subjects.extend(["Biotechnology", "Economics", "Political Science", "Physics", "Chemistry", "Maths", "English", "Commerce", "Hindi"])
        elif grade_range == "12":
            available_subjects.extend(["Biotechnology", "English", "Physics", "Chemistry", "Maths", "Accountancy", "Commerce", "Hindi"])
        
        subject = st.selectbox("Select Subject", available_subjects, key="subject")
        
        if subject != "Select":
            # The entire processing logic is now handled by this single, clean function call.
            run_file_processor(subject)