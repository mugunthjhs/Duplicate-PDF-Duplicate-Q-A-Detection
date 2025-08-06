import fitz  # PyMuPDF
import re
import json
import os
import shutil

def process_english_pdf(pdf_path):
    output_folder = "output_english"
    json_output_path = os.path.join(output_folder, "english_questions.json")
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")

    # --- Step 1: Clean/Create Output Directory ---
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # --- Step 2: Extract and Structure Questions ---
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"❌ Error opening PDF: {e}")
        return

    remove_patterns = [
        r"(?i)^CBSE\s*[-–]?\s*GRADE\s*[-–]?\s*\d+\s*$",      # CBSE - GRADE – 6
        r"(?i)^GRADE\s*[-–]?\s*\d+\s*$",                      # GRADE – 6 or GRADE 6
        r"(?i)^CBSE\s*$",                                    # CBSE
        r"(?i)^ENGLISH\s*$",                                 # ENGLISH
        r"(?i)^UNIT\s*[-–]?\s*\d+.*$",                        # UNIT – 4 SPORTS AND WELLNESS
        r"(?i)^CHAPTER\s*[-–]?\s*\d+.*$",                     # CHAPTER – 3 or CHAPTER - 4 Text
        r"^\d{1,3}\s*$",                                     # Just a number like 1, 23, 100
        r"^\s*$",                                            # Blank lines
        r"^---\s*Page\s*\d+\s*---$",                          # --- Page 5 ---
        r"^(?=.*\bCBSE\b)(?=.*\bGRADE\b)[A-Z\s\-–0-9]*$",      # Line has both CBSE and GRADE in uppercase
        r"(?i)^(?=(?:.*\b(answer|following|questions|briefly|shortly)\b.*?){3,}).*$"
    ]
    compiled_remove_patterns = [re.compile(pat, re.IGNORECASE) for pat in remove_patterns]

    main_question_pattern = re.compile(r"^(\d{1,3})[).]", re.IGNORECASE)
    option_pattern = re.compile(r"^[A-D][).]\s*(.*)")

    def should_remove_line(line):
        return any(pat.match(line.strip()) for pat in compiled_remove_patterns)

    def process_answer_line(line):
        stripped = line.strip()
        output_lines = []
        if "answer:" in stripped.lower() and ":" in stripped:
            output_lines.append("-----------------------------")
        output_lines.append(line)
        return output_lines

    def insert_spacing_before_questions(lines):
        final_lines = []
        for i, line in enumerate(lines):
            match = main_question_pattern.match(line)
            if match:
                if final_lines and final_lines[-1] != "":
                    final_lines.append("")
            final_lines.append(line)
        return final_lines

    all_lines = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        raw_text = page.get_text()
        lines = raw_text.split("\n")
        cleaned_on_page = []
        for line in lines:
            line_stripped = line.strip()
            if should_remove_line(line_stripped):
                continue
            
            processed_lines = process_answer_line(line_stripped)
            cleaned_on_page.extend(processed_lines)

        cleaned_compact = []
        for line in cleaned_on_page:
            if line != "":
                cleaned_compact.append(line)
            elif not cleaned_compact or cleaned_compact[-1] != "":
                cleaned_compact.append("")

        all_lines.extend(cleaned_compact)

    doc.close()

    final_output_lines = insert_spacing_before_questions(all_lines)

    processed_final_lines = []
    for i, line in enumerate(final_output_lines):
        if line.strip() == "":
            if (i > 0 and final_output_lines[i-1].strip() != "") and \
               (i < len(final_output_lines) - 1 and final_output_lines[i+1].strip() != ""):
                processed_final_lines.append(line)
        else:
            processed_final_lines.append(line)

    lines_for_json = [line for line in processed_final_lines if line.strip()]

    def parse_questions_by_number(all_lines):
        questions = []
        i = 0
        numbered_q_pattern = re.compile(r"^(\d+)[.)]\s*(.*)")
        keyword_pattern = re.compile(r"^Keywords\s*[:：]", re.IGNORECASE)
        separator_pattern = re.compile(r"^[-]{3,}$")
        mcq_option_pattern = re.compile(r"^[A-Z][.)]\s+(.*)")

        while i < len(all_lines):
            line = all_lines[i].strip()
            match = numbered_q_pattern.match(line)
            if not match:
                i += 1
                continue

            current_q_num = int(match.group(1))
            qtype = ""
            if 1 <= current_q_num <= 150:
                qtype = "MCQ"
            elif 151 <= current_q_num <= 185:
                qtype = "Short Answer"
            elif 186 <= current_q_num <= 200:
                qtype = "Long Answer"
            else:
                i += 1
                continue
            
            q_lines, options, answer_lines_raw, keyword_lines = [], [], [], []
            
            start_of_question_index = i
            while i < len(all_lines) and not separator_pattern.match(all_lines[i]):
                current_line = all_lines[i].strip()
                if i > start_of_question_index and numbered_q_pattern.match(current_line):
                    break
                if qtype == "MCQ":
                    option_match = mcq_option_pattern.match(current_line)
                    if option_match:
                        options.append(option_match.group(1).strip())
                    else:
                        q_lines.append(current_line)
                else:
                    q_lines.append(current_line)
                i += 1
            
            if i < len(all_lines) and separator_pattern.match(all_lines[i]):
                i += 1

            while i < len(all_lines):
                current_line = all_lines[i].strip()
                if numbered_q_pattern.match(current_line):
                    break
                if keyword_pattern.match(current_line):
                    keyword_content = current_line[current_line.find(":") + 1:].strip()
                    keyword_lines.append(keyword_content)
                    i += 1
                    while i < len(all_lines):
                        next_line = all_lines[i].strip()
                        if numbered_q_pattern.match(next_line):
                            break
                        keyword_lines.append(next_line)
                        i += 1
                    break
                else:
                    answer_lines_raw.append(current_line)
                    i += 1

            question_text = re.sub(r"^\d+[.)]\s*", "", " ".join(q_lines), count=1).strip()
            
            question_obj = {
                "questionNUM": f"pdf_{current_q_num}",
                "questionType": qtype,
                "question": question_text,
                "image": None,
            }

            if qtype == "MCQ":
                question_obj["options"] = options
                question_obj["mark"] = 1
                
                full_answer_block = "\n".join(answer_lines_raw)
                answer_letter_match = re.search(r'\b([A-D])\b', full_answer_block, re.IGNORECASE)
                correct_answer_text = ""
                
                if answer_letter_match and options:
                    answer_letter = answer_letter_match.group(1).upper()
                    idx = ord(answer_letter) - ord('A')
                    if 0 <= idx < len(options):
                        correct_answer_text = options[idx]
                
                if not correct_answer_text:
                    cleaned_answer_text = re.sub(r"^Answer:\s*", "", full_answer_block, flags=re.IGNORECASE).strip()
                    correct_answer_text = cleaned_answer_text

                question_obj["correctAnswer"] = correct_answer_text

                correct_option_index = None
                if correct_answer_text and options:
                    try:
                        correct_option_index = options.index(correct_answer_text) + 1
                    except ValueError:
                        correct_option_index = None
                question_obj["correctOptionIndex"] = correct_option_index
                
            else:
                if qtype == "Short Answer":
                    question_obj["mark"] = 3
                elif qtype == "Long Answer":
                    question_obj["mark"] = 5

                cleaned_answer_text = re.sub(r"^Answer:\s*", "", "\n".join(answer_lines_raw).strip(), flags=re.IGNORECASE)
                question_obj["correctAnswer"] = cleaned_answer_text
                keywords_str = " ".join(keyword_lines)
                question_obj["answerKeyword"] = [k.strip() for k in keywords_str.split(',') if k.strip()]
            
            questions.append(question_obj)

        return questions

    all_questions = parse_questions_by_number(lines_for_json)
    
    # --- MODIFICATION START: Reorder dictionary keys for consistent JSON output ---
    # This new section creates a new list of dictionaries with keys in the desired order.
    ordered_questions = []
    for q in all_questions:
        q_type = q.get("questionType")
        
        if q_type == "MCQ":
            # Build the dictionary with the exact key order for MCQs
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
        elif q_type in ["Short Answer", "Long Answer"]:
            # Build the dictionary with the exact key order for other types
            ordered_q = {
                "questionNUM": q.get("questionNUM"),
                "question": q.get("question"),
                "questionType": q_type,
                "image": q.get("image"),
                "correctAnswer": q.get("correctAnswer"),
                "answerKeyword": q.get("answerKeyword"),
                "mark": q.get("mark")
            }
        else: # Fallback for any unexpected types, just use the original dict
            ordered_q = q

        ordered_questions.append(ordered_q)
    # --- MODIFICATION END ---


    # Use the newly ordered list for JSON output
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(ordered_questions, f, indent=4, ensure_ascii=False)

    # --- Step 3: Duplicate Detection (Now uses the ordered list for consistent report formatting) ---
    def normalize_question_text(text):
        return re.sub(r'\s+', '', text.lower()) if isinstance(text, str) else ""

    def count_option_mismatches(opt1, opt2):
        s1 = set(map(str, opt1)) if isinstance(opt1, list) else set()
        s2 = set(map(str, opt2)) if isinstance(opt2, list) else set()
        return len(s1.symmetric_difference(s2))

    seen = {}
    reports = []
    dup_count = 0
    # Use the ordered_questions list here
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
            if item.get("questionType", "").lower() == "mcq":
                mismatch.append(f"{count_option_mismatches(item.get('options'), orig.get('options'))} options mismatched")
            summary = f"DUPLICATE : {item['questionNUM']} duplicates {orig['questionNUM']} - {', '.join(mismatch) or 'all fields match'}"
            reports.append(f"{summary}\n\nOriginal:\n{json.dumps(orig, indent=4)}\n\nDuplicate:\n{json.dumps(item, indent=4)}\n{'='*70}\n")
        else:
            seen[norm] = item

    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        if reports:
            f.write(f"Found {dup_count} duplicate entries.\n{'='*70}\n\n" + "\n".join(reports))
        else:
            f.write("No duplicates found.\n")

    print(f"✅ Extracted {len(ordered_questions)} questions to {json_output_path}")
    print(f"✅ Duplicate report saved to {duplicate_output_path}")


# --- Run ---
if __name__ == "__main__":
    pdf_file_path = r"E:\SUBJECTS_PDF\pdf\cbsc_g6_english_unit4_with_keywords.pdf"
    if os.path.exists(pdf_file_path):
        process_english_pdf(pdf_file_path)
    else:
        print(f"❌ Error: PDF file not found at '{pdf_file_path}'")

