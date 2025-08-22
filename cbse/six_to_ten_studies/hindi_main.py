import docx
import re
import json
import os
import shutil

def process_hindi_pdf(doc_path):
    output_folder = "output_hindi"
    json_output_path = os.path.join(output_folder, "hindi_questions.json")
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")

    # --- Step 1: Clean/Create Output Directory ---
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # --- Step 2: Extract and Structure Questions ---
    try:
        doc = docx.Document(doc_path)
    except Exception as e:
        print(f"❌ Error opening Word document: {e}")
        return

    remove_patterns = [
        r"(?i)^CBSE\s*[-–]?\s*GRADE\s*[-–]?\s*\d+\s*$",      # CBSE - GRADE – 6
        r"(?i)^GRADE\s*[-–]?\s*\d+\s*$",                      # GRADE – 6 or GRADE 6
        r"(?i)^CBSE\s*$",                                    # CBSE
        r"(?i)^हिंदी\s*$",                                    # हिंदी (Hindi)
        r"(?i)^इकाई\s*[-–]?\s*\d+.*$",                        # इकाई – 4 (Unit – 4)
        r"(?i)^अध्याय\s*[-–]?\s*\d+.*$",                      # अध्याय – 3 (Chapter – 3)
        r"^\d{1,3}\s*$",                                     # Just a number like 1, 23, 100
        r"^\s*$",                                            # Blank lines
        r"^---\s*Page\s*\d+\s*---$",                          # --- Page 5 ---
        r"^(?=.*\bCBSE\b)(?=.*\bGRADE\b)[A-Z\s\-–0-9]*$",      # Line has both CBSE and GRADE in uppercase
        r"(?i)^(?=(?:.*\b(उत्तर|निम्नलिखित|प्रश्नों|संक्षेप में|संक्षिप्त)\b.*?){3,}).*$"  # Hindi equivalent of answer-related terms
    ]
    compiled_remove_patterns = [re.compile(pat, re.IGNORECASE) for pat in remove_patterns]

    main_question_pattern = re.compile(r"^(\d{1,3})[).]", re.IGNORECASE)
    
    def should_remove_line(line):
        return any(pat.match(line.strip()) for pat in compiled_remove_patterns)

    def process_answer_line(line):
        stripped = line.strip()
        output_lines = []
        if "उत्तर:" in stripped.lower() and ":" in stripped:
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

    for para in doc.paragraphs:
        lines = para.text.split("\n")
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
        separator_pattern = re.compile(r"^[-]{3,}$")
        
        while i < len(all_lines):
            line = all_lines[i].strip()
            match = numbered_q_pattern.match(line)
            if not match:
                i += 1
                continue

            current_q_num = int(match.group(1))
            qtype = ""
            if 1 <= current_q_num <= 150:
                qtype = "बहुविकल्पीय प्रश्न"  # MCQ
            elif 151 <= current_q_num <= 185:
                qtype = "निम्नलिखित प्रश्नों के उत्तर लिखिए"  # Short Answer
            elif 186 <= current_q_num <= 200:
                qtype = "निम्नलिखित प्रश्नों के उत्तर लिखिए"  # Long Answer
            else:
                i += 1
                continue
            
            q_lines, answer_lines_raw = [], []
            
            # --- Gather all lines for the question block ---
            start_of_question_index = i
            while i < len(all_lines) and not separator_pattern.match(all_lines[i]):
                current_line = all_lines[i].strip()
                if i > start_of_question_index and numbered_q_pattern.match(current_line):
                    break
                q_lines.append(current_line)
                i += 1
            
            # --- Skip separator ---
            if i < len(all_lines) and separator_pattern.match(all_lines[i]):
                i += 1

            # --- Gather all lines for the answer block ---
            while i < len(all_lines):
                current_line = all_lines[i].strip()
                if numbered_q_pattern.match(current_line):
                    break
                answer_lines_raw.append(current_line)
                i += 1

            question_text_raw = " ".join(q_lines)
            question_text_raw = re.sub(r"^\d+[.)]\s*", "", question_text_raw, count=1).strip()
            
            question_obj = {
                "questionNUM": f"doc_{current_q_num}",
                "questionType": qtype,
                "image": None,
            }

            if qtype == "बहुविकल्पीय प्रश्न":
                option_split_pattern = re.compile(r'\s+([क-घA-D][.)])\s*')
                parts = option_split_pattern.split(question_text_raw)
                
                question_text = parts[0].strip()
                options = [p.strip() for p in parts[2::2] if p.strip()]

                question_obj["question"] = question_text
                question_obj["options"] = options
                question_obj["mark"] = 1
                
                full_answer_block = "\n".join(answer_lines_raw)

                # This version of the answer still has the option marker, e.g., "(C) राणा के आदेशों का पालन"
                # It is useful for finding the correct option index via the letter if text matching fails.
                answer_with_marker = re.sub(r"^(?:उत्तर:|Answer:)\s*", "", full_answer_block, flags=re.IGNORECASE).strip()
                
                # This version removes the marker, e.g., "राणा के आदेशों का पालन".
                # This is the desired format for the "correctAnswer" field.
                answer_without_marker = re.sub(r"^\s*\(?[क-घA-D]\)?\s*[.)]?\s*", "", answer_with_marker, flags=re.IGNORECASE).strip()
                
                # Assign the clean text (without the marker) to the correctAnswer field
                question_obj["correctAnswer"] = answer_without_marker

                correct_option_index = None
                # First, try to find the index by matching the clean answer text exactly with one of the options.
                if answer_without_marker and options:
                    try:
                        correct_option_index = options.index(answer_without_marker)
                    except ValueError:
                        # Fallback to a normalized comparison (case-insensitive, no whitespace)
                        normalized_options = [re.sub(r'\s+', '', opt, flags=re.UNICODE).lower() for opt in options]
                        normalized_text_to_find = re.sub(r'\s+', '', answer_without_marker, flags=re.UNICODE).lower()
                        try:
                            correct_option_index = normalized_options.index(normalized_text_to_find)
                        except ValueError:
                            correct_option_index = None

                # If text matching fails, fall back to finding the option letter (e.g., 'ग' or 'C')
                # in the answer text that still has the marker.
                if correct_option_index is None:
                    letter_match = re.search(r'\b([क-घ])\b', answer_with_marker) or re.search(r'\b([A-D])\b', answer_with_marker, re.IGNORECASE)
                    if letter_match and options:
                        letter = letter_match.group(1)
                        hindi_map = {'क': 0, 'ख': 1, 'ग': 2, 'घ': 3}
                        eng_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                        idx = hindi_map.get(letter) or eng_map.get(letter.upper())
                        if idx is not None and 0 <= idx < len(options):
                            correct_option_index = idx
                
                question_obj["correctOptionIndex"] = correct_option_index
                
            else: # "निम्नलिखित प्रश्नों के उत्तर लिखिए"
                question_obj["question"] = question_text_raw
                
                if 151 <= current_q_num <= 185:
                    question_obj["mark"] = 2
                elif 186 <= current_q_num <= 200:
                    question_obj["mark"] = 5

                full_answer_text = "\n".join(answer_lines_raw)
                full_answer_text = re.sub(r"^(?:उत्तर:|Answer:)\s*", "", full_answer_text.strip(), flags=re.IGNORECASE)
                
                keyword_marker_pattern = re.compile(r'(मुख्य\s*शब्द|मुख्य\s*वाक्\s*।?)\s*[:：]', re.IGNORECASE)
                parts = keyword_marker_pattern.split(full_answer_text, 1)

                final_answer = ""
                keywords = []
                if len(parts) > 2:  # Split successful
                    final_answer = parts[0].strip()
                    keys_string = parts[2].strip()
                    keywords = [k.strip() for k in keys_string.split(',') if k.strip()]
                else:  # No keyword marker found
                    final_answer = full_answer_text.strip()
                    keywords = []
                
                question_obj["correctAnswer"] = final_answer
                question_obj["answerKeyword"] = keywords
            
            questions.append(question_obj)

        return questions

    all_questions = parse_questions_by_number(lines_for_json)
    
    # --- Reorder dictionary keys for consistent JSON output ---
    ordered_questions = []
    for q in all_questions:
        q_type = q.get("questionType")
        
        if q_type == "बहुविकल्पीय प्रश्न":
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
        elif q_type == "निम्नलिखित प्रश्नों के उत्तर लिखिए":
            ordered_q = {
                "questionNUM": q.get("questionNUM"),
                "question": q.get("question"),
                "questionType": q_type,
                "image": q.get("image"),
                "correctAnswer": q.get("correctAnswer"),
                "answerKeyword": q.get("answerKeyword"),
                "mark": q.get("mark")
            }
        else:
            ordered_q = q

        ordered_questions.append(ordered_q)

    # --- Save JSON output ---
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(ordered_questions, f, indent=4, ensure_ascii=False)

    # --- Step 3: Duplicate Detection ---
    def normalize_question_text(text):
        return re.sub(r'\s+', '', text.lower()) if isinstance(text, str) else ""

    def count_option_mismatches(opt1, opt2):
        s1 = set(map(str, opt1)) if isinstance(opt1, list) else set()
        s2 = set(map(str, opt2)) if isinstance(opt2, list) else set()
        return len(s1.symmetric_difference(s2))

    seen = {}
    reports = []
    dup_count = 0
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
            if item.get("questionType", "") == "बहुविकल्पीय प्रश्न":
                mismatch.append(f"{count_option_mismatches(item.get('options'), orig.get('options'))} options mismatched")
            summary = f"DUPLICATE : {item['questionNUM']} duplicates {orig['questionNUM']} - {', '.join(mismatch) or 'all fields match'}"
            reports.append(f"{summary}\n\nOriginal:\n{json.dumps(orig, indent=4, ensure_ascii=False)}\n\nDuplicate:\n{json.dumps(item, indent=4, ensure_ascii=False)}\n{'='*70}\n")
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
    doc_file_path = r"hindi_input\GRADE 6 HINDI CHAPTER 7 WITH KEY WORDS.docx"
    if os.path.exists(doc_file_path):
        process_hindi_pdf(doc_file_path)
    else:
        print(f"❌ Error: Word document not found at '{doc_file_path}'")