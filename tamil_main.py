import fitz  # PyMuPDF
import re
import os
import shutil
import json
from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
import difflib
import PyPDF2

def process_tamil_pdf(pdf_path):
    """
    Processes a Tamil PDF to extract questions, and generates a duplicate report.
    This function is designed to be called from a web app like Streamlit.

    Args:
        pdf_path (str): The file path to the input PDF.

    Returns:
        tuple: A tuple containing:
            - list: The extracted questions as a list of dictionaries (JSON data).
            - str: The content of the duplicate report as a string.
            On error, it returns a tuple with an empty list and an error message string.
    """
    # Note: The file-writing part is for local testing.
    # The main output is the returned tuple at the end of the function.
    output_folder = "output_tamil"
    
    # --- Step 1: Clean/Create Output Directory (for local testing) ---
    # This part is optional for streamlit, but good for standalone runs.
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")
    filename = os.path.basename(pdf_path)
    chapter_match = re.search(r"chapter_(\d+)", filename, re.IGNORECASE)
    chapter_num = chapter_match.group(1) if chapter_match else "Unknown"
    json_output_path = os.path.join(output_folder, f"chapter_{chapter_num}_questions.json")


    # --- Step 2: Extract and Structure Questions ---
    
    # --- Sub-Step 2.1: Detect Sub-Chapters ---
    unique_sub_chapters = []
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text + "\n"
            
            subchapter_pattern = r"(?:^\s*|\s)(Chapter\s*-?\s*\d+\.\d+)(?=\s*-|\b)"
            matches = re.findall(subchapter_pattern, text)
            unique_sub_chapters = sorted(list(dict.fromkeys(matches)))
    except Exception as e:
        # We can continue without subchapters, but we should log it.
        print(f"Warning: Could not detect sub-chapters with PyPDF2. Error: {e}")
        
    # --- Sub-Step 2.2: Extract Text using PyMuPDF ---
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        error_message = f"❌ Error opening PDF with PyMuPDF: {e}. The file might be corrupted or not a valid PDF."
        print(error_message)
        # <-- CRITICAL FIX: Return a valid tuple on error -->
        return [], error_message

    # Patterns, normalizers, and helper functions
    remove_patterns = [
        r"(?i)^CBSE\s*[-–]?\s*GRADE\s*[-–]?\s*\d+\s*$", r"(?i)^GRADE\s*[-–]?\s*\d+\s*$",
        r"(?i)^CBSE\s*$", r"(?i)^தமிழ்\s*$", r"(?i)^பிரிவு\s*[-–]?\s*\d+.*$",
        r"(?i)^அத்தியாயம்\s*[-–]?\s*\d+.*$", r"^[௦-௯\d]{1,3}\s*$", r"^\s*$",
        r"^---\s*Page\s*\d+\s*---$", r"^(?=.*\bCBSE\b)(?=.*\bGRADE\b)[A-Z\s\-–0-9]*$",
        r"(?i)^(?=(?:.*\b(பதில்|கேள்விகள்|குறுகிய|விரிவான)\b.*?){2,}).*$"
    ]
    compiled_remove_patterns = [re.compile(pat, re.IGNORECASE | re.UNICODE) for pat in remove_patterns]
    main_question_pattern = re.compile(r"^([\d௦-௯]{1,3})[).]", re.UNICODE)
    tamil_normalizer = IndicNormalizerFactory().get_normalizer("ta")

    def normalize_tamil_text(text):
        return tamil_normalizer.normalize(text).strip()
    def should_remove_line(line):
        return any(pat.match(line.strip()) for pat in compiled_remove_patterns)
    def process_answer_line(line):
        stripped = line.strip()
        output_lines = []
        if re.match(r"^(பதில்|Answer)\s*[:]", stripped, re.IGNORECASE | re.UNICODE):
            output_lines.append("-----------------------------")
        output_lines.append(line)
        return output_lines
    def insert_spacing_before_questions(lines_with_subchapters):
        final_lines = []
        for line, subchapter in lines_with_subchapters:
            if main_question_pattern.match(line):
                if final_lines and final_lines[-1][0] != "":
                    final_lines.append(("", subchapter))
            final_lines.append((line, subchapter))
        return final_lines

    all_lines_with_subchapters = []
    current_subchapter = "Chapter Unknown"

    for page in doc:
        lines = page.get_text().split("\n")
        for line in lines:
            normalized_line = normalize_tamil_text(line)
            for sub_chap_header in unique_sub_chapters:
                if sub_chap_header in normalized_line:
                    current_subchapter = sub_chap_header
                    break
            if should_remove_line(normalized_line):
                continue
            for pl in process_answer_line(normalized_line):
                all_lines_with_subchapters.append((pl, current_subchapter))
    doc.close()

    spaced_lines = insert_spacing_before_questions(all_lines_with_subchapters)
    processed_final_lines = []
    for i, (line, subchapter) in enumerate(spaced_lines):
        if line.strip() == "" and i > 0 and spaced_lines[i-1][0].strip() != "" and i < len(spaced_lines) - 1 and spaced_lines[i+1][0].strip() != "":
             processed_final_lines.append((line, subchapter))
        elif line.strip() != "":
            processed_final_lines.append((line, subchapter))

    # --- Parser Logic (as a nested function) ---
    def parse_questions_by_number(lines_with_subchapters):
        questions = []
        i = 0
        numbered_q_pattern = re.compile(r"^([\d௦-௯]{1,3})[.)]\s*(.*)", re.UNICODE)
        keyword_pattern = re.compile(r"^(?:முக்கிய வார்த்தைகள்|Keywords)\s*[:]\s*(.*)", re.IGNORECASE | re.UNICODE)
        separator_pattern = re.compile(r"^[-]{3,}$", re.UNICODE)
        mcq_option_pattern = re.compile(r"^[அ-ஈ][).]\s*(.*)", re.UNICODE)
        embedded_option_pattern = re.compile(r"[அ-ஈA-D]\)\s*(.*?)(?=\s*[அ-ஈA-D]\)|$)", re.UNICODE)
        tamil_to_int = {'௦': 0, '௧': 1, '௨': 2, '௩': 3, '௪': 4, '௫': 5, '௬': 6, '௭': 7, '௮': 8, '௯': 9}

        while i < len(lines_with_subchapters):
            line, current_subchapter = lines_with_subchapters[i]
            match = numbered_q_pattern.match(line.strip())
            if not match:
                i += 1
                continue
            q_num_str = match.group(1)
            try:
                num_val_str = ''.join(str(tamil_to_int.get(c, c)) for c in q_num_str)
                current_q_num_int = int(num_val_str)
            except ValueError:
                i += 1
                continue
            
            qtype = ""
            if 1 <= current_q_num_int <= 25: qtype = "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக"
            elif 26 <= current_q_num_int <= 32: qtype = "சிறுவினா"
            elif 33 <= current_q_num_int <= 35: qtype = "பெருவினா"
            else: i += 1; continue
            
            q_lines, options, answer_lines_raw, keyword_lines = [], [], [], []
            
            start_of_question_index = i
            while i < len(lines_with_subchapters) and not separator_pattern.match(lines_with_subchapters[i][0]):
                current_line, _ = lines_with_subchapters[i]
                if i > start_of_question_index and numbered_q_pattern.match(current_line.strip()): break
                if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக" and mcq_option_pattern.match(current_line.strip()):
                    options.append(mcq_option_pattern.match(current_line.strip()).group(1).strip())
                else:
                    q_lines.append(current_line.strip())
                i += 1
            if i < len(lines_with_subchapters) and separator_pattern.match(lines_with_subchapters[i][0]): i += 1
            while i < len(lines_with_subchapters):
                current_line, _ = lines_with_subchapters[i]
                if numbered_q_pattern.match(current_line.strip()): break
                keyword_match = keyword_pattern.match(current_line.strip())
                if keyword_match:
                    keyword_lines.append(keyword_match.group(1).strip())
                    i += 1
                    while i < len(lines_with_subchapters):
                        next_line, _ = lines_with_subchapters[i]
                        if numbered_q_pattern.match(next_line.strip()) or keyword_pattern.match(next_line.strip()): break
                        keyword_lines.append(next_line.strip())
                        i += 1
                    break 
                else:
                    answer_lines_raw.append(current_line.strip())
                    i += 1

            question_text_raw = " ".join(q_lines)
            question_text = re.sub(r"^[\d௦-௯]+[.)]\s*", "", question_text_raw, count=1).strip()
            if not question_text: continue
            
            final_options = options
            if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                embedded_options = embedded_option_pattern.findall(question_text)
                if embedded_options:
                    final_options = [opt.strip() for opt in embedded_options]
                    first_option_match = embedded_option_pattern.search(question_text)
                    if first_option_match:
                        question_text = question_text[:first_option_match.start()].strip()
            
            question_obj = {"questionNUM": f"pdf_{current_q_num_int}", "questionType": qtype, "question": question_text, "image": None, "subchapter": current_subchapter}
            
            if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                question_obj["options"] = final_options
                question_obj["mark"] = 1
                raw_answer = re.sub(r"^(?:பதில்|Answer)\s*[:]\s*", "", "\n".join(answer_lines_raw), flags=re.I|re.U).strip()
                cleaned_answer = re.sub(r"^[அ-ஈA-D]\)\s*", "", raw_answer).strip()
                question_obj["correctAnswer"] = cleaned_answer
                correct_option_index = None
                if cleaned_answer and final_options:
                    try:
                        correct_option_index = [normalize_tamil_text(opt) for opt in final_options].index(normalize_tamil_text(cleaned_answer)) + 1
                    except ValueError: pass
                question_obj["correctOptionIndex"] = correct_option_index
            else:
                question_obj["mark"] = 2 if qtype == "சிறுவினா" else 5
                question_obj["correctAnswer"] = re.sub(r"^(?:பதில்|Answer)\s*[:]\s*", "", "\n".join(answer_lines_raw), flags=re.I|re.U).strip()
                question_obj["answerKeyword"] = [k.strip() for k in " ".join(keyword_lines).split(',') if k.strip()]
            questions.append(question_obj)
        return questions

    all_questions = parse_questions_by_number(processed_final_lines)
    
    # --- Reorder keys for consistent JSON output and prepare for duplicate check ---
    ordered_questions = []
    subchapter_grouped_questions = {sub: {"சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக": [], "சிறுவினா": [], "பெருவினா": []} for sub in unique_sub_chapters + ["Chapter Unknown"]}

    for q in all_questions:
        q_type = q.get("questionType")
        if q_type == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
            ordered_q = {"questionNUM": q.get("questionNUM"), "question": q.get("question"), "questionType": q_type, "image": q.get("image"), "options": q.get("options"), "correctOptionIndex": q.get("correctOptionIndex"), "correctAnswer": q.get("correctAnswer"), "mark": q.get("mark"), "subchapter": q.get("subchapter")}
        else:
            ordered_q = {"questionNUM": q.get("questionNUM"), "question": q.get("question"), "questionType": q_type, "image": q.get("image"), "correctAnswer": q.get("correctAnswer"), "answerKeyword": q.get("answerKeyword"), "mark": q.get("mark"), "subchapter": q.get("subchapter")}
        ordered_questions.append(ordered_q)
        sub = q.get("subchapter", "Chapter Unknown")
        if sub in subchapter_grouped_questions and q_type in subchapter_grouped_questions[sub]:
            subchapter_grouped_questions[sub][q_type].append(ordered_q)

    # --- Step 3: Duplicate Detection ---
    reports = []
    total_dup_count = 0
    
    def normalize_question_text_for_dup_check(text):
        if not isinstance(text, str) or len(text.strip()) < 5 or not re.search(r'[\u0B80-\u0BFF]', text):
            return ""
        return normalize_tamil_text(text)

    for subchapter in subchapter_grouped_questions:
        for qtype in subchapter_grouped_questions[subchapter]:
            questions_in_group = subchapter_grouped_questions[subchapter][qtype]
            seen = {}
            group_dup_count = 0
            for item in questions_in_group:
                norm = normalize_question_text_for_dup_check(item.get("question", ""))
                if not norm: continue
                is_duplicate = False
                for orig_norm, orig in seen.items():
                    if difflib.SequenceMatcher(None, norm, orig_norm).ratio() > 0.95:
                        is_duplicate = True; group_dup_count += 1
                        mismatch_str = "correctAnswer mismatch" if str(item.get("correctAnswer")) != str(orig.get("correctAnswer")) else "all fields match"
                        reports.append(f"DUPLICATE : {item['questionNUM']} duplicates {orig['questionNUM']} - {mismatch_str}\n\n{'='*70}\n")
                        break
                if not is_duplicate: seen[norm] = item
            if group_dup_count > 0:
                header = f"\nSUBCHAPTER: {subchapter} - Found {group_dup_count} duplicates \nQUESTION TYPE: {qtype}\n"
                reports.insert(len(reports) - group_dup_count, header)
                total_dup_count += group_dup_count

    duplicate_report_string = ""
    if reports:
        duplicate_report_string = f"Found {total_dup_count} total duplicate entries.\n{'='*70}\n" + "".join(reports)
    else:
        duplicate_report_string = "No duplicates found.\n"

    # Write files for local testing
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(ordered_questions, f, ensure_ascii=False, indent=4)
    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        f.write(duplicate_report_string)
        
    print(f"✅ Local testing files created for Chapter {chapter_num}.")

    # <-- CRITICAL FIX: Always return the tuple for Streamlit -->
    return ordered_questions, duplicate_report_string

# --- Standalone Run Block ---
if __name__ == "__main__":
    # Replace with a valid path to your test PDF
    pdf_file_path = r"path/to/your/tamil_chapter_file.pdf" 
    
    if os.path.exists(pdf_file_path):
        # Capture the returned values, just like Streamlit does
        json_data, report_text = process_tamil_pdf(pdf_file_path)

        print("\n--- Function Execution Summary ---")
        print(f"Extracted {len(json_data)} questions.")
        print(f"Duplicate report generated ({len(report_text)} characters).")
        print("--- End of Summary ---\n")
        
        # Optionally, print the first few lines of the report
        print("--- Duplicate Report Snippet ---")
        print(report_text[:500] + "...")
        print("--- End of Snippet ---")
    else:
        print(f"❌ Error: Test PDF file not found at '{pdf_file_path}'. Please update the path in the script.")