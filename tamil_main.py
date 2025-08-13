import re
import json
import os
import shutil
from docx import Document

# =================================================================
# ===== SINGLE, DEPLOYABLE PROCESSING FUNCTION ====================
# =================================================================

def process_tamil_pdf(input_docx_path): # MODIFICATION: Removed 'output_folder' as it's not needed for Streamlit
    """
    Main orchestrator function to process a single DOCX document for Streamlit.

    This function is designed to be called by a web app. It performs the
    entire workflow in memory and returns the results.
    1.  Parses the DOCX file to extract questions.
    2.  Reorders keys for consistent formatting.
    3.  Analyzes for duplicates.
    4.  Returns the structured data and the duplicate report.

    Args:
        input_docx_path (str): The full path to the temporary input .docx file.

    Returns:
        tuple: A tuple containing (ordered_questions, duplicate_report_content).
               Returns (None, None) if processing fails.
    """
    print(f"--- Starting Full Process for: {os.path.basename(input_docx_path)} ---")

    # --- Initial File Check ---
    if not os.path.exists(input_docx_path):
        # FIXED: Added the input_docx_path to the error message for better debugging.
        print(f"❌ Error: Input file not found at '{input_docx_path}'. Aborting process.")
        return None, None # MODIFICATION: Return a tuple indicating failure

    # --- Configuration Constants ---
    SPECIAL_SENTENCES = [
        "சரியானவிடையைத்தேர்ந்தெடுத்துஎழுதுக",
        "சிறுவினா",
        "பெருவினா"
    ]
    QUESTION_TYPE_MAPPING = {
        "சரியானவிடையைத்தேர்ந்தெடுத்துஎழுதுக": "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக",
        "சிறுவினா": "சிறுவினா",
        "பெருவினா": "பெருவினா"
    }
    MARKS_MAPPING = {
        "சரியானவிடையைத்தேர்ந்தெடுத்துஎழுதுக": 1,
        "சிறுவினா": 2,
        "பெருவினா": 5
    }

    # =================================================================
    # ===== HELPER FUNCTIONS (Nested for Encapsulation) ===============
    # =================================================================

    def parse_mcq(qa_text, q_num, subchapter):
        """Parses a text block for a Multiple Choice Question."""
        try:
            parts = re.split(r'\bAnswer\s*:\s*', qa_text, maxsplit=1, flags=re.IGNORECASE)
            q_and_options_text = parts[0]
            answer_text = parts[1].splitlines()[0].strip() if len(parts) > 1 and parts[1] else ""
            options = re.findall(r"^\s*[A-D]\)\s*(.*)", q_and_options_text, re.MULTILINE)
            option_list = [opt.strip() for opt in options]
            first_option_match = re.search(r"^\s*[A-D]\)", q_and_options_text, re.MULTILINE)
            question_text = q_and_options_text[:first_option_match.start()].strip() if first_option_match else q_and_options_text.strip()
            question_text = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", question_text, 1)
            correct_answer_clean = re.sub(r'^[A-D]\)\s*', '', answer_text).strip()
            
            correct_option_index = -1
            try:
                correct_option_index = option_list.index(correct_answer_clean)
            except ValueError:
                # FIXED: Added variables to the warning for better debugging.
                print(f"Warning: Could not find answer '{correct_answer_clean}' in options for Q#{q_num}. Index set to -1.")
            
            q_type_key = "சரியானவிடையைத்தேர்ந்தெடுத்துஎழுதுக"
            # FIXED: Added the actual question number.
            return {"questionNUM": f"pdf_{q_num}", "question": question_text, "questionType": QUESTION_TYPE_MAPPING[q_type_key], "image": None, "options": option_list, "correctOptionIndex": correct_option_index, "correctAnswer": correct_answer_clean, "mark": MARKS_MAPPING[q_type_key], "subchapter": subchapter}
        except Exception as e:
            # FIXED: Added variables to the error for better debugging.
            print(f"Error parsing MCQ Q#{q_num}: {e}\nContent:\n{qa_text}\n")
            return None

    def parse_descriptive(qa_text, q_num, subchapter, q_type_key):
        """Parses a text block for a Short or Long Answer Question."""
        try:
            parts = re.split(r'\bKeywords\s*:\s*', qa_text, maxsplit=1, flags=re.IGNORECASE)
            main_part = parts[0]
            keywords_part = parts[1].strip() if len(parts) > 1 else ""
            q_a_parts = re.split(r'\bAnswer\s*:\s*', main_part, maxsplit=1, flags=re.IGNORECASE)
            question_part = q_a_parts[0]
            answer_part = q_a_parts[1].strip() if len(q_a_parts) > 1 else ""
            question_text = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", question_part.strip(), 1)
            keywords_list = [k.strip() for k in keywords_part.split(',') if k.strip()]
            
            # FIXED: Added the actual question number.
            return {"questionNUM": f"pdf_{q_num}", "question": question_text, "questionType": QUESTION_TYPE_MAPPING[q_type_key], "image": None, "correctAnswer": answer_part, "answerKeyword": keywords_list, "mark": MARKS_MAPPING[q_type_key], "subchapter": subchapter}
        except Exception as e:
            # FIXED: Added variables to the error for better debugging.
            print(f"Error parsing Descriptive Q#{q_num}: {e}\nContent:\n{qa_text}\n")
            return None

    def parse_questions_from_docx(file_path):
        """Reads DOCX and processes it into a list of question data, without saving."""
        print("Starting question parsing process...")
        all_questions_data = []
        try:
            doc = Document(file_path)
            lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            current_subchapter, current_q_type_key, current_qa_lines = "Unknown Subchapter", None, []
            chapter_pattern = re.compile(r"^(Chapter\.?\s*\d+(\.\d+)*)", re.IGNORECASE)
            question_start_pattern = re.compile(r"^\s*\d+\s*[\.\)]")

            def process_collected_block():
                nonlocal all_questions_data, current_qa_lines
                if not current_qa_lines or not current_q_type_key:
                    return
                qa_text = "\n".join(current_qa_lines)
                q_num_match = re.match(r"^\s*(\d+)", qa_text)
                if not q_num_match: return
                q_num = q_num_match.group(1)
                
                parsed_data = None
                if current_q_type_key == "சரியானவிடையைத்தேர்ந்தெடுத்துஎழுதுக":
                    parsed_data = parse_mcq(qa_text, q_num, current_subchapter)
                elif current_q_type_key in ["சிறுவினா", "பெருவினா"]:
                    parsed_data = parse_descriptive(qa_text, q_num, current_subchapter, current_q_type_key)
                if parsed_data:
                    all_questions_data.append(parsed_data)

            for line in lines:
                no_space_line = line.replace(" ", "")
                is_q_type_heading = next((s for s in SPECIAL_SENTENCES if no_space_line.startswith(s)), None)
                if chapter_pattern.search(line) or is_q_type_heading:
                    process_collected_block()
                    current_qa_lines = []
                    if chapter_pattern.search(line):
                        current_subchapter = line
                    if is_q_type_heading:
                        current_q_type_key = is_q_type_heading
                    continue
                
                if question_start_pattern.match(line):
                    process_collected_block()
                    current_qa_lines = [line]
                elif current_qa_lines:
                    current_qa_lines.append(line)
            
            process_collected_block()
            
            print(f"Successfully parsed {len(all_questions_data)} questions from the document.")
            return all_questions_data

        except Exception as e:
            print(f"An unexpected error occurred during parsing: {e}")
            return []

    # MODIFICATION: This function now returns a string instead of writing to a file.
    def find_and_report_duplicates(question_data):
        """Analyzes question data for duplicates and returns a report string."""
        print("\nStarting duplicate detection process...")

        def normalize_question_text(text):
            return re.sub(r'\s+', '', text.lower()) if isinstance(text, str) else ""

        def count_option_mismatches(opts1, opts2):
            set1 = set(map(str, opts1)) if isinstance(opts1, list) else set()
            set2 = set(map(str, opts2)) if isinstance(opts2, list) else set()
            return len(set1.symmetric_difference(set2))

        seen, reports, dup_count = {}, [], 0
        for i, item in enumerate(question_data):
            # Assign a unique temporary ID for matching
            item['temp_id'] = i
            norm_question = normalize_question_text(item.get("question", ""))
            if not norm_question: continue

            if norm_question in seen:
                dup_count += 1
                orig = seen[norm_question]
                mismatch_details = []

                if item.get("subchapter") != orig.get("subchapter"): mismatch_details.append(f"Subchapter (Orig: '{orig.get('subchapter')}', Dup: '{item.get('subchapter')}')")
                if item.get("questionType") != orig.get("questionType"): mismatch_details.append(f"Question Type (Orig: '{orig.get('questionType')}', Dup: '{item.get('questionType')}')")
                if str(item.get("correctAnswer")) != str(orig.get("correctAnswer")): mismatch_details.append("Correct Answer")
                if item.get("questionType") == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                    option_diff = count_option_mismatches(item.get('options'), orig.get('options'))
                    if option_diff > 0: mismatch_details.append(f"Options ({option_diff} different)")
                
                # FIXED: Corrected the f-string for summary
                report_entry = (f"DUPLICATE #{dup_count}\n"
                                f" - Original Item (ID {orig['temp_id']}): {orig['questionNUM']} (from Subchapter: \"{orig.get('subchapter')}\")\n"
                                f" - Duplicate Item (ID {item['temp_id']}): {item['questionNUM']} (from Subchapter: \"{item.get('subchapter')}\")\n"
                                f" - Mismatches: {', '.join(mismatch_details) or 'None (Exact Match)'}\n"
                                f"{'='*80}\n"
                                f"--- Original Item (ID {orig['temp_id']}) ---\n{json.dumps(orig, indent=2, ensure_ascii=False)}\n\n"
                                f"--- Duplicate Item (ID {item['temp_id']}) ---\n{json.dumps(item, indent=2, ensure_ascii=False)}\n"
                                f"{'='*80}\n")
                reports.append(report_entry)
            else:
                seen[norm_question] = item
        
        # Clean up temporary IDs before returning
        for item in question_data:
            del item['temp_id']

        if reports:
            # FIXED: Added dup_count to the print statement
            print(f"Found {dup_count} duplicates.")
            final_report = f"Found {dup_count} duplicate question(s).\n\n{'='*80}\n"
            final_report += "\n".join(reports)
            return final_report
        else:
            print("No duplicates found.")
            return "No duplicate questions were found in the document."

    # =================================================================
    # ===== EXECUTION FLOW ============================================
    # =================================================================
    
    # --- Step 1: Parse the DOCX to extract question data ---
    parsed_questions = parse_questions_from_docx(input_docx_path)
    
    if not parsed_questions:
        print("\nNo questions were parsed from the document. Halting process.")
        return None, "No questions could be parsed from the document. Please check the file format." # MODIFICATION: Return a helpful message

    # --- Step 2: Reorder keys for consistent format ---
    print("\nReordering JSON keys for consistent output format...")
    ordered_questions = []
    for q in parsed_questions:
        q_type = q.get("questionType")
        
        if q_type == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
            ordered_q = {
                "questionNUM": q.get("questionNUM"), "question": q.get("question"),
                "questionType": q_type, "image": q.get("image"), "options": q.get("options"),
                "correctOptionIndex": q.get("correctOptionIndex"), "correctAnswer": q.get("correctAnswer"),
                "mark": q.get("mark"), "subchapter": q.get("subchapter")
            }
        elif q_type in ["சிறுவினா", "பெருவினா"]:
            ordered_q = {
                "questionNUM": q.get("questionNUM"), "question": q.get("question"),
                "questionType": q_type, "image": q.get("image"), "correctAnswer": q.get("correctAnswer"),
                "answerKeyword": q.get("answerKeyword"), "mark": q.get("mark"), "subchapter": q.get("subchapter")
            }
        else:
            ordered_q = q
        ordered_questions.append(ordered_q)

    # --- Step 3: Run duplicate detection on the generated data ---
    duplicate_report_content = find_and_report_duplicates(ordered_questions)
    
    # FIXED: Added the filename to the final print statement
    print(f"\n--- Process complete for {os.path.basename(input_docx_path)}. Returning results. ---")
    
    # --- Step 4: Return the results for Streamlit ---
    return ordered_questions, duplicate_report_content


# =================================================================
# ===== MAIN EXECUTION BLOCK (For standalone testing) =============
# =================================================================
if __name__ == "__main__":
    # This block allows you to test the script independently of Streamlit.
    # It will create an output folder and save the files there.
    
    input_file_path = r"cbse_g8_tamil_chapter_1_with_keywords.docx"
    output_directory = "tamil_output"
    
    if os.path.exists(input_file_path):
        # Call the function and get the returned data
        json_data, report_data = process_tamil_pdf(input_file_path)

        if json_data and report_data:
            # Create output directory for testing
            if os.path.exists(output_directory):
                shutil.rmtree(output_directory)
            os.makedirs(output_directory, exist_ok=True)
            
            # Save the returned data to files
            json_path = os.path.join(output_directory, "tamil_questions.json")
            report_path = os.path.join(output_directory, "duplicate_report.txt")
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_data)

            # FIXED: Included the output directory name in the print message.
            print(f"\n--- Standalone test complete. Check the '{output_directory}' folder. ---")
        else:
            print("\n--- Standalone test failed. No data was returned. ---")
    else:
        # FIXED: Included the file path in the error message.
        print(f"Error: Input file not found at '{input_file_path}'. Please check the path and try again.")
    
    print("\n--- Script finished. ---")
