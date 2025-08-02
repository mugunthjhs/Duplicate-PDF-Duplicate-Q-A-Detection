import streamlit as st
import os
import time
import tempfile
from english_main import process_english_pdf

st.set_page_config(page_title="Duplicate Q/A Finder", layout="centered")
st.title("📚 Duplicate Q/A Finder")

# Subject selection
subject = st.selectbox("Select Subject", ["English", "Science", "Maths", "Tamil", "Hindi", "Social Science"])

if subject != "English":
    st.warning("🚧 Work in Progress for this subject.")
else:
    uploaded_file = st.file_uploader("Upload PDF file", type=["pdf"])

    if uploaded_file is not None:
        temp_pdf_path = None
        try:
            # Use a temporary file that we can manually delete
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                temp_pdf_path = tmp_file.name

            with st.spinner("Processing PDF..."):
                # Call the function which runs, creates files, but returns None
                process_english_pdf(temp_pdf_path)
                time.sleep(1)

            st.success("✅ Processing Complete!")

            # Since main.py doesn't return the paths, we must define them here,
            # matching the hardcoded paths in main.py.
            output_folder = "english/output_english"
            json_path = os.path.join(output_folder, "english_questions.json")
            duplicate_txt_path = os.path.join(output_folder, "duplicate_output.txt")


            # Check if the output file was actually created before trying to read it
            if os.path.exists(duplicate_txt_path):
                st.subheader("🔍 Duplicate Questions Found:")
                with open(duplicate_txt_path, "r", encoding="utf-8") as f:
                    duplicate_content = f.read()
                st.text_area("Duplicate Q/A Output", duplicate_content, height=300)

                # Add download button for the duplicate file
                with open(duplicate_txt_path, "rb") as f:
                    st.download_button("📥 Download Duplicate.txt", f, file_name="duplicate.txt", mime="text/plain")
            else:
                st.warning("Could not find duplicate report file. Processing might have failed.")


            # Check if the JSON file exists before creating a download button
            if os.path.exists(json_path):
                 with open(json_path, "rb") as f:
                    st.download_button("📥 Download JSON File", f, file_name="questions.json", mime="application/json")
            else:
                st.warning("Could not find JSON output file. Processing might have failed.")


        except Exception as e:
            st.error(f"An error occurred during processing: {e}")
        finally:
            # Clean up the temporary PDF file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
