import fitz  # PyMuPDF
import re    # Regular expression module
import json  # JSON module for output
import os    # For path and directory operations
import shutil # For removing directory trees

def process_maths_pdf(pdf_path):
    """
    Processes a mathematics PDF to extract questions into a structured JSON file
    and generate a report on any duplicate questions found.

    The entire process is self-contained, creating an 'output_maths' folder
    for the final files.
    """
    # --- 1. Setup Output Directory ---
    output_folder = "output_maths"
    json_output_path = os.path.join(output_folder, "maths_questions.json")
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")

    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    # --- 2. Nested Helper Functions for PDF Parsing and Cleaning ---
    
    def remove_explanations_from_questions(lines):
        final_lines = []
        skip_mode = False
        next_question_pattern = None
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if skip_mode:
                if next_question_pattern and re.match(next_question_pattern, line_stripped):
                    skip_mode = False
                    final_lines.append(line)
                continue
            if line_stripped.startswith("Explanation:"):
                skip_mode = True
                for offset in range(i + 1, len(lines)):
                    match = re.match(r'^(\d{1,3})\s*\.', lines[offset].strip())
                    if match:
                        next_q_num = int(match.group(1))
                        next_question_pattern = rf'^{next_q_num}\s*\.'
                        break
                continue
            final_lines.append(line)
        return final_lines

    # This function is no longer called, as keywords are now parsed.
    # It is kept here to minimize structural changes to the original file.
    def remove_keywords_from_questions(lines):
        final_lines = []
        skip_mode = False
        next_question_pattern = None
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if skip_mode:
                if next_question_pattern and re.match(next_question_pattern, line_stripped):
                    skip_mode = False
                    final_lines.append(line)
                continue
            if line_stripped.startswith("Keywords:"):
                skip_mode = True
                for offset in range(i + 1, len(lines)):
                    match = re.match(r'^(\d{1,3})\s*\.', lines[offset].strip())
                    if match:
                        next_q_num = int(match.group(1))
                        next_question_pattern = rf'^{next_q_num}\s*\.'
                        break
                continue
            final_lines.append(line)
        return final_lines

    def get_question_type(q_num):
        if 1 <= q_num <= 150: return "MCQ"
        if 151 <= q_num <= 185: return "ShortAnswer"
        if 186 <= q_num <= 200: return "LongAnswer"
        return "Unknown"

    def parse_questions_to_json_structure(lines):
        all_questions_data = []
        full_text = "\n".join(lines)
        parsed_question_numbers = set()
        question_blocks = re.split(r'\n(?=\s*\d{1,3}\s*\.)', full_text)

        for block in question_blocks:
            block = block.strip()
            if not block: continue
            
            q_num_match = re.match(r'^\s*(\d{1,3})\s*\.\s*(.*)', block, re.DOTALL)
            if not q_num_match: continue
            
            q_num = int(q_num_match.group(1))
            if q_num in parsed_question_numbers:
                continue
            parsed_question_numbers.add(q_num)
            
            question_type = get_question_type(q_num)
            content_text = q_num_match.group(2).strip()
            question_data = {"questionNUM": f"pdf_{q_num}", "questionType": question_type, "image": None}

            if question_type == "MCQ":
                parts = re.split(r'\nAnswer:\s*', content_text, flags=re.IGNORECASE, maxsplit=1)
                if len(parts) < 2: continue
                
                question_and_options_part, answer_part = parts
                question_text_lines, options = [], []
                
                for line in question_and_options_part.split('\n'):
                    stripped_line = line.strip()
                    if re.match(r'^[A-D]\)\s*', stripped_line):
                        options.append(re.sub(r'^[A-D]\)\s*', '', stripped_line).strip())
                    else:
                        question_text_lines.append(line)
                
                if not options: continue
                
                question_data["question"] = "\n".join(question_text_lines).strip()
                question_data["options"] = options
                question_data["mark"] = 1

                answer_letter_match = re.search(r'^\s*([A-D])\b', answer_part.strip(), re.IGNORECASE)
                correct_answer_text = ""
                correct_option_index = None

                if answer_letter_match:
                    answer_letter = answer_letter_match.group(1).upper()
                    idx = ord(answer_letter) - ord('A')
                    if 0 <= idx < len(options):
                        correct_answer_text = options[idx]
                        correct_option_index = idx + 1
                
                if not correct_answer_text:
                    cleaned_answer = re.sub(r'^[A-D]\)\s*', '', answer_part.strip()).strip()
                    correct_answer_text = cleaned_answer
                    if cleaned_answer in options:
                        correct_option_index = options.index(cleaned_answer) + 1

                question_data["correctAnswer"] = correct_answer_text
                question_data["correctOptionIndex"] = correct_option_index

            elif question_type in ["ShortAnswer", "LongAnswer"]:
                keywords_split = re.split(r'\nKeywords:\s*', content_text, flags=re.IGNORECASE, maxsplit=1)
                main_content = keywords_split[0]
                keywords_text = keywords_split[1] if len(keywords_split) > 1 else ""

                answer_split = re.split(r'\nAnswer:\s*', main_content, flags=re.IGNORECASE, maxsplit=1)
                if len(answer_split) < 2: continue
                
                before_answer_part, answer_part = answer_split
                solution_split = re.split(r'\nSolution:\s*', before_answer_part, flags=re.IGNORECASE, maxsplit=1)
                
                question_data["question"] = solution_split[0].strip() if len(solution_split) > 1 else before_answer_part.strip()
                question_data["solution"] = solution_split[1].strip() if len(solution_split) > 1 else ""
                question_data["correctAnswer"] = answer_part.strip()
                question_data["answerKeyword"] = [k.strip() for k in keywords_text.split(',') if k.strip()]

                if question_type == "ShortAnswer":
                    question_data["mark"] = 3
                elif question_type == "LongAnswer":
                    question_data["mark"] = 5
            
            if "question" in question_data and question_data["question"]:
                all_questions_data.append(question_data)

        return all_questions_data

    # --- 3. Main PDF Processing Logic ---
    try:
        pdf_document = fitz.open(pdf_path)
    # === THIS IS THE CORRECTED LINE ===
    except FileNotFoundError:
        print(f"Error: The file '{pdf_path}' was not found.")
        return

    extracted_text = "".join(page.get_text() for page in pdf_document)
    pdf_document.close()

    cleaned_text = re.sub(r'Page\s*\d+', '', extracted_text)
    lines = cleaned_text.splitlines()

    filtered_lines = [
        line.strip() for line in lines if line.strip() and
        not (re.search(r'CBSE', line, re.IGNORECASE) and re.search(r'GRADE', line, re.IGNORECASE)) and
        not re.search(r'Chapter\s*\d{1,2}', line, re.IGNORECASE) and
        not re.search(r'Mathematics', line, re.IGNORECASE)
    ]

    without_explanations = remove_explanations_from_questions(filtered_lines)
    # The call to remove_keywords_from_questions is removed to allow keyword parsing.
    all_questions = parse_questions_to_json_structure(without_explanations)

    # --- New section to re-order keys for clean JSON output ---
    ordered_questions = []
    for q in all_questions:
        q_type = q.get("questionType")
        ordered_q = {}

        if q_type == "MCQ":
            ordered_q = {
                "questionNUM": q.get("questionNUM"),
                "question": q.get("question"),
                "questionType": q_type,
                "image": q.get("image"),
                "options": q.get("options"),
                "correctOptionIndex": q.get("correctOptionIndex"),
                "correctAnswer": q.get("correctAnswer"),
                "mark": q.get("mark")
            }
        elif q_type in ["ShortAnswer", "LongAnswer"]:
            ordered_q = {
                "questionNUM": q.get("questionNUM"),
                "question": q.get("question"),
                "questionType": q_type,
                "image": q.get("image"),
                "solution": q.get("solution"),
                "correctAnswer": q.get("correctAnswer"),
                "answerKeyword": q.get("answerKeyword"),
                "mark": q.get("mark")
            }
        else: # Fallback for any unexpected types
            ordered_q = q
        
        ordered_questions.append(ordered_q)

    with open(json_output_path, "w", encoding="utf-8") as json_file:
        json.dump(ordered_questions, json_file, indent=4, ensure_ascii=False)

    # --- 4. Duplicate Checking Logic (using the ordered list for consistency) ---
    def normalize_question_text(text):
        return re.sub(r'\s+', '', text.lower()) if isinstance(text, str) else ""

    def count_option_mismatches(opt1, opt2):
        s1 = set(map(str, opt1)) if isinstance(opt1, list) else set()
        s2 = set(map(str, opt2)) if isinstance(opt2, list) else set()
        return len(s1.symmetric_difference(s2))

    seen, reports, dup_count = {}, [], 0
    for item in ordered_questions:
        norm = normalize_question_text(item.get("question", ""))
        if not norm:
            continue
        if norm in seen:
            dup_count += 1
            orig = seen[norm]
            mismatch = []
            if item.get("questionType") != orig.get("questionType"):
                mismatch.append("questionType mismatch")
            if str(item.get("correctAnswer")) != str(orig.get("correctAnswer")):
                mismatch.append("correctAnswer mismatch")
            if str(item.get("solution")) != str(orig.get("solution")):
                mismatch.append("solution mismatch")
            if item.get("questionType", "").lower() == "mcq":
                mismatch.append(f"{count_option_mismatches(item.get('options'), orig.get('options'))} options mismatched")
            summary = f"DUPLICATE {dup_count}: {item['questionNUM']} duplicates {orig['questionNUM']} - {', '.join(mismatch) or 'all fields match'}"
            reports.append(f"{summary}\n\nOriginal:\n{json.dumps(orig, indent=4)}\n\nDuplicate:\n{json.dumps(item, indent=4)}\n{'='*70}\n")
        else:
            seen[norm] = item

    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        if reports:
            f.write(f"Found {dup_count} duplicate entries.\n{'='*70}\n\n" + "\n".join(reports))
        else:
            f.write("No duplicates found.\n")

    print(f"\n✅ Extracted questions to {json_output_path}")
    print(f"✅ Duplicate report saved to {duplicate_output_path}")

# --- Example Usage ---
if __name__ == "__main__":
    # IMPORTANT: Replace this with the actual path to your PDF file
    pdf_file_path = r"E:\SUBJECTS_PDF\AI\MATHS\CBSE GRADE 6 MATHS CHAPTER 1 (KEY).pdf"
    if os.path.exists(pdf_file_path):
        process_maths_pdf(pdf_file_path)
    else:
        print(f"Error: The specified PDF file does not exist at '{pdf_file_path}'")
        print("Please update the 'pdf_file_path' variable in the `if __name__ == '__main__':` block.")
