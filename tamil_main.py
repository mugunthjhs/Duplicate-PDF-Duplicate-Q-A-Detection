import fitz  
import re
import os
import shutil
import json
from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
import difflib
import PyPDF2

def process_tamil_pdf(pdf_path):
    output_folder = "output_tamil"
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")
    
    # Extract chapter number from filename
    filename = os.path.basename(pdf_path)
    chapter_match = re.search(r"chapter_(\d+)", filename, re.IGNORECASE)
    chapter_num = chapter_match.group(1) if chapter_match else "Unknown"
    json_output_path = os.path.join(output_folder, f"chapter_{chapter_num}_questions.json")

    # Clean/Create Output Directory
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # === PART 1: Sub-Chapter Detection ===
    subchapter_pattern = r"(?:^\s*|\s)(Chapter\s*-?\s*\d+\.\d+)(?=\s*-|\b)"
    subchapter_questions = {}

    # Extract sub-chapters first
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                text += extracted_text + "\n"

    matches = re.findall(subchapter_pattern, text)
    unique_sub_chapters = sorted(set(matches), key=matches.index)
    print(f"\n=== Sub-Chapter Detection ===")
    print(f"Total sub-chapters found: {len(unique_sub_chapters)}")
    for sub in unique_sub_chapters:
        print(sub)
        subchapter_questions[sub] = {"சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக": [], "சிறுவினா": [], "பெருவினா": []}

    # === PART 2: Tamil Question Processing ===
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"❌ Error opening PDF: {e}")
        return

    # Patterns for Tamil only
    remove_patterns = [
        r"(?i)^CBSE\s*[-–]?\s*GRADE\s*[-–]?\s*\d+\s*$",
        r"(?i)^GRADE\s*[-–]?\s*\d+\s*$",
        r"(?i)^CBSE\s*$",
        r"(?i)^தமிழ்\s*$",
        r"(?i)^பிரிவு\s*[-–]?\s*\d+.*$",
        r"(?i)^அத்தியாயம்\s*[-–]?\s*\d+.*$",
        r"^[௦-௯]{1,3}\s*$",
        r"^\s*$",
        r"^---\s*Page\s*\d+\s*---$",
        r"^(?=.*\bCBSE\b)(?=.*\bGRADE\b)[A-Z\s\-–0-9]*$",
        r"(?i)^(?=(?:.*\b(பதில்|கேள்விகள்|குறுகிய|விரிவான)\b.*?){2,}).*$"
    ]
    compiled_remove_patterns = [re.compile(pat, re.IGNORECASE | re.UNICODE) for pat in remove_patterns]

    main_question_pattern = re.compile(r"^([\d௦-௯]{1,3})[).]\s*(.*)", re.UNICODE)
    option_pattern = re.compile(r"^[அ-ஈ][).]\s*(.*)", re.UNICODE)
    answer_pattern = re.compile(r"^(?:பதில்|Answer)\s*[:]\s*(.*)", re.IGNORECASE | re.UNICODE)
    keyword_pattern = re.compile(r"^(?:முக்கிய வார்த்தைகள்|Keywords)\s*[:]\s*(.*)", re.IGNORECASE | re.UNICODE)
    separator_pattern = re.compile(r"^[-]{3,}$", re.UNICODE)

    tamil_normalizer = IndicNormalizerFactory().get_normalizer("ta")
    def normalize_text(text):
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
        for i, (line, subchapter) in enumerate(lines_with_subchapters):
            match = main_question_pattern.match(line)
            if match:
                if final_lines and final_lines[-1][0] != "":
                    final_lines.append(("", subchapter))
            final_lines.append((line, subchapter))
        return final_lines

    all_lines = []
    current_subchapter = None
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        raw_text = page.get_text()
        lines = raw_text.split("\n")
        cleaned_on_page = []
        for line in lines:
            line_stripped = normalize_text(line.strip())
            # Check if line matches subchapter pattern
            for subchapter in unique_sub_chapters:
                if subchapter in line_stripped:
                    current_subchapter = subchapter
                    break
            if should_remove_line(line_stripped):
                continue
            processed_lines = process_answer_line(line_stripped)
            cleaned_on_page.extend((line, current_subchapter) for line in processed_lines)

        cleaned_compact = []
        for line, subchapter in cleaned_on_page:
            if line != "":
                cleaned_compact.append((line, subchapter))
            elif not cleaned_compact or cleaned_compact[-1][0] != "":
                cleaned_compact.append(("", subchapter))
        all_lines.extend(cleaned_compact)
    doc.close()

    final_output_lines = insert_spacing_before_questions(all_lines)
    lines_for_processing = [(line, subchapter) for line, subchapter in final_output_lines if line.strip() or True] # Keep empty lines for spacing
    print(f"DEBUG: Extracted {len(lines_for_processing)} lines for processing")

    def parse_questions_by_number(all_lines_with_subchapters):
        questions = []
        i = 0
        while i < len(all_lines_with_subchapters):
            line, current_subchapter = all_lines_with_subchapters[i]
            line = line.strip()
            match = main_question_pattern.match(line)
            if not match:
                i += 1
                continue

            current_q_num = match.group(1)
            try:
                tamil_to_int = {'௦': 0, '௧': 1, '௨': 2, '௩': 3, '௪': 4, '௫': 5, '௬': 6, '௭': 7, '௮': 8, '௯': 9}
                if all(c in tamil_to_int for c in current_q_num):
                    num_str = ''.join(str(tamil_to_int[c]) for c in current_q_num)
                    current_q_num_int = int(num_str)
                else:
                    current_q_num_int = int(current_q_num)
            except ValueError:
                i += 1
                continue

            qtype = ""
            if 1 <= current_q_num_int <= 25:
                qtype = "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக"
            elif 26 <= current_q_num_int <= 32:
                qtype = "சிறுவினா"
            elif 33 <= current_q_num_int <= 35:
                qtype = "பெருவினா"
            else:
                i += 1
                continue
            
            q_lines, options, answer_lines_raw, keyword_lines = [], [], [], []
            start_of_question_index = i
            while i < len(all_lines_with_subchapters) and not separator_pattern.match(all_lines_with_subchapters[i][0]):
                current_line, _ = all_lines_with_subchapters[i]
                current_line = current_line.strip()
                if i > start_of_question_index and main_question_pattern.match(current_line):
                    break
                if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                    option_match = option_pattern.match(current_line)
                    if option_match:
                        options.append(option_match.group(1).strip())
                    else:
                        q_lines.append(current_line)
                else:
                    q_lines.append(current_line)
                i += 1
            if i < len(all_lines_with_subchapters) and separator_pattern.match(all_lines_with_subchapters[i][0]):
                i += 1

            while i < len(all_lines_with_subchapters):
                current_line, _ = all_lines_with_subchapters[i]
                current_line = current_line.strip()
                if main_question_pattern.match(current_line):
                    break
                keyword_match = keyword_pattern.match(current_line)
                if keyword_match:
                    keyword_content = keyword_match.group(1).strip()
                    keyword_lines.append(keyword_content)
                    i += 1
                    while i < len(all_lines_with_subchapters):
                        next_line, _ = all_lines_with_subchapters[i]
                        next_line = next_line.strip()
                        if main_question_pattern.match(next_line):
                            break
                        keyword_lines.append(next_line)
                        i += 1
                    break
                else:
                    answer_lines_raw.append(current_line)
                    i += 1

            # --- START: MODIFIED LOGIC FOR QUESTION PARSING ---
            
            raw_question_content = " ".join(q_lines)
            question_text = re.sub(r"^[\d௦-௯]+[.)]\s*", "", raw_question_content, count=1).strip()
            
            if not question_text:
                continue

            final_options = options # Default to options found on separate lines

            if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                # Pattern to find embedded options like A) text B) text... or அ) text ஆ) text...
                embedded_option_pattern = re.compile(r"[அ-ஈA-D]\)\s*(.*?)(?=\s*[அ-ஈA-D]\)|$)")
                
                embedded_options = embedded_option_pattern.findall(question_text)
                
                if embedded_options:
                    # If options are embedded in the question text, extract them
                    final_options = [opt.strip() for opt in embedded_options]
                    
                    # The actual question is the text before the first option starts
                    first_option_match = embedded_option_pattern.search(question_text)
                    if first_option_match:
                        question_text = question_text[:first_option_match.start()].strip()
            
            question_obj = {
                "questionNUM": f"pdf_{current_q_num_int}", # Correctly assign question number
                "questionType": qtype,
                "question": question_text,
                "image": None,
                "subchapter": current_subchapter
            }

            if qtype == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                question_obj["options"] = final_options
                question_obj["mark"] = 1
                
                full_answer_block = "\n".join(answer_lines_raw)
                
                # Get raw answer text by stripping "Answer:"/"பதில்:" prefix
                raw_answer_text = re.sub(r"^(?:பதில்|Answer)\s*[:]\s*", "", full_answer_block, flags=re.IGNORECASE | re.UNICODE).strip()

                # Clean the answer by removing the option marker like "A)" or "அ)"
                cleaned_answer_text = re.sub(r"^[அ-ஈA-D]\)\s*", "", raw_answer_text).strip()
                question_obj["correctAnswer"] = cleaned_answer_text
                
                correct_option_index = None
                if cleaned_answer_text and final_options:
                    try:
                        # Normalize both for a more reliable comparison
                        normalized_answer = normalize_text(cleaned_answer_text)
                        normalized_options = [normalize_text(opt) for opt in final_options]
                        correct_option_index = normalized_options.index(normalized_answer) + 1
                    except ValueError:
                        # Fallback for partial matches if direct match fails
                        for idx, opt in enumerate(final_options):
                            if cleaned_answer_text in opt or opt in cleaned_answer_text:
                                correct_option_index = idx + 1
                                break
                question_obj["correctOptionIndex"] = correct_option_index
            else:
                if qtype == "சிறுவினா":
                    question_obj["mark"] = 2
                elif qtype == "பெருவினா":
                    question_obj["mark"] = 5
                
                cleaned_answer_text = re.sub(r"^(?:பதில்|Answer)\s*[:]\s*", "", "\n".join(answer_lines_raw).strip(), flags=re.IGNORECASE | re.UNICODE)
                question_obj["correctAnswer"] = cleaned_answer_text
                keywords_str = " ".join(keyword_lines)
                question_obj["answerKeyword"] = [k.strip() for k in keywords_str.split(',') if k.strip()]

            # --- END: MODIFIED LOGIC ---

            if current_subchapter:
                if qtype in subchapter_questions[current_subchapter]:
                    subchapter_questions[current_subchapter][qtype].append(question_obj)
            questions.append(question_obj)
        return questions

    all_questions = parse_questions_by_number(lines_for_processing)
    print(f"DEBUG: Parsed {len(all_questions)} questions")

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=4)
    print(f"✅ Questions saved to {json_output_path}")

    # === PART 3: Duplicate Detection by Sub-Chapter and Question Type ===
    def normalize_question_text(question):
        text = question.get("question", "")
        if not text or not isinstance(text, str) or len(text.strip()) < 5:
            return None
        tamil_char_pattern = re.compile(r'[\u0B80-\u0BFF]', re.UNICODE)
        if not tamil_char_pattern.search(text):
            return None
        normalized_text = normalize_text(text)
        if not normalized_text.strip():
            return None
        return normalized_text

    def count_option_mismatches(opt1, opt2):
        s1 = set(map(str, opt1)) if isinstance(opt1, list) else set()
        s2 = set(map(str, opt2)) if isinstance(opt2, list) else set()
        return len(s1.symmetric_difference(s2))

    reports = []
    total_dups = 0

    for subchapter in unique_sub_chapters:
        for qtype in ["சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக", "சிறுவினா", "பெருவினா"]:
            questions = subchapter_questions[subchapter][qtype]
            seen, dups = {}, []
            dup_count = 0

            valid_questions = [q for q in questions if q.get("question") and isinstance(q.get("question"), str) and
                               len(q.get("question").strip()) >= 5 and re.search(r'[\u0B80-\u0BFF]', q.get("question"), re.UNICODE)]

            if not valid_questions:
                continue

            for i, item in enumerate(valid_questions):
                norm = normalize_question_text(item)
                if not norm:
                    continue
                is_duplicate = False
                for orig_norm, orig in seen.items():
                    similarity = difflib.SequenceMatcher(None, norm, orig_norm).ratio()
                    if similarity > 0.95:
                        is_duplicate = True
                        dup_count += 1
                        total_dups += 1
                        mismatch = []
                        if item.get("questionType") != orig.get("questionType"):
                            mismatch.append("questionType mismatch")
                        if str(item.get("correctAnswer")) != str(orig.get("correctAnswer")):
                            mismatch.append("correctAnswer mismatch")
                        if item.get("questionType") == "சரியான விடையைத் தேர்ந்தெடுத்து எழுதுக":
                            mismatched_options = count_option_mismatches(item.get('options'), orig.get('options'))
                            if mismatched_options > 0:
                                mismatch.append(f"{mismatched_options} options mismatched")
                        
                        summary = f"DUPLICATE : {item['questionNUM']} duplicates {orig['questionNUM']} - {', '.join(mismatch) or 'all fields are matching'}"
                        dups.append(f"\n{summary}\n{'='*70}")
                        dups.append(f"\n  Q1 ({orig['questionNUM']}): {orig['question']}")
                        dups.append(f"\n  Q2 ({item['questionNUM']}): {item['question']}\n\n")
                        break
                if not is_duplicate:
                    seen[norm] = item

            if dups:
                reports.append(f"\nSubchapter: {subchapter} - Question Type: {qtype}\nFound {dup_count} duplicates\n{'='*70}" + "".join(dups))

    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        if reports:
            f.write(f"Total duplicates found: {total_dups}\n{'='*70}\n\n" + "".join(reports))
        else:
            f.write("No duplicates found across all sub-chapters.\n")
    print(f"✅ Duplicate report saved to {duplicate_output_path}")

# --- Run ---
if __name__ == "__main__":
    pdf_file_path = r"cbse_g6_tamil_chapter_1_with_keywords.pdf"
    if os.path.exists(pdf_file_path):
        process_tamil_pdf(pdf_file_path)
    else:
        print(f"❌ Error: PDF file not found at '{pdf_file_path}'")