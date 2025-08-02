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
        r"^CBSE GRADE\s*\d+",
        r"^ENGLISH$",
        r"^CHAPTER\s*[-–]\s*\d+.*",
        r"^\d{1,3}$",
        r"^\s*$",
        r"^---\s*Page\s*\d+\s*---$",
    ]
    compiled_remove_patterns = [re.compile(pat, re.IGNORECASE) for pat in remove_patterns]
    section_triggers = [
        "multiple choice questions:",
        "answer the following shortly:",
        "answer the following briefly:"
    ]
    trigger_regex = re.compile("|".join(map(re.escape, section_triggers)), re.IGNORECASE)
    main_question_pattern = re.compile(r"^(\d{1,3})[).]", re.IGNORECASE)
    option_pattern = re.compile(r"^[A-D][).]\s*(.*)")

    def should_remove_line(line):
        return any(pat.match(line.strip()) for pat in compiled_remove_patterns)

    def is_trigger_line(line):
        return any(line.lower().strip().startswith(trigger) for trigger in section_triggers)

    def insert_spacing_before_questions(lines):
        final_lines = []
        last_question_number = 0
        for i, line in enumerate(lines):
            match = main_question_pattern.match(line)
            if match:
                current_q = int(match.group(1))
                if current_q == last_question_number + 1:
                    if final_lines and final_lines[-1] != "":
                        final_lines.append("")
                    last_question_number = current_q
            final_lines.append(line)
        return final_lines

    def process_answer_line(line, current_question_options):
        stripped = line.strip()
        output_lines = []
        if "answer:" in stripped.lower() and ":" in stripped:
            output_lines.append("-----------------------------")
            formatted_answer = stripped
            answer_letter_match = re.search(r'\b([A-D])\b', stripped.upper())
            if answer_letter_match:
                answer_letter = answer_letter_match.group(1)
                if answer_letter in current_question_options:
                    full_answer_text = current_question_options[answer_letter]
                    formatted_answer = f"Answer: {full_answer_text}"
            output_lines.append(formatted_answer)
        else:
            output_lines.append(line)
        return output_lines

    all_lines = []
    trigger_found = False
    current_question_options = {}

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        raw_text = page.get_text()
        lines = raw_text.split("\n")
        cleaned_on_page = []
        for line in lines:
            line_stripped = line.strip()
            if should_remove_line(line_stripped):
                continue
            opt_match = option_pattern.match(line_stripped)
            if opt_match:
                option_letter = line_stripped[0]
                option_text = opt_match.group(1).strip()
                current_question_options[option_letter] = option_text
                cleaned_on_page.append(line_stripped)
                continue
            processed_lines = process_answer_line(line_stripped, current_question_options)
            cleaned_on_page.extend(processed_lines)

        cleaned_compact = []
        for line in cleaned_on_page:
            if line != "":
                cleaned_compact.append(line)
            elif not cleaned_compact or cleaned_compact[-1] != "":
                cleaned_compact.append("")

        if not trigger_found:
            full_text_on_page = "\n".join(cleaned_compact)
            match = trigger_regex.search(full_text_on_page)
            if match:
                trigger_found = True
                full_text_from_trigger = full_text_on_page[match.start():]
                cleaned_compact = full_text_from_trigger.split("\n")
            else:
                continue
        all_lines.extend(cleaned_compact)

    doc.close()

    padded_lines = []
    for line in all_lines:
        if is_trigger_line(line):
            padded_lines.append("")
            padded_lines.append(line.strip())
            padded_lines.append("")
        else:
            padded_lines.append(line)

    final_output_lines = insert_spacing_before_questions(padded_lines)

    processed_final_lines = []
    for i, line in enumerate(final_output_lines):
        if line.strip() == "":
            if (i > 0 and final_output_lines[i-1].strip() != "") or \
               (i < len(final_output_lines) - 1 and final_output_lines[i+1].strip() != ""):
                processed_final_lines.append(line)
        else:
            processed_final_lines.append(line)

    lines_for_json = [line for line in processed_final_lines if line.strip()]

    # Section parsing
    def find_section_index(marker, line_list):
        for idx, line in enumerate(line_list):
            if marker in line.lower():
                return idx
        return -1

    def parse_section(lines_in_section, qtype, question_counter_start):
        questions = []
        i = 0
        question_counter = question_counter_start
        numbered_q_pattern = re.compile(r"^(\d+)[.)]\s*(.*)")
        keyword_pattern = re.compile(r"^Keywords\s*[:：]", re.IGNORECASE)
        separator_pattern = re.compile(r"^[-]{3,}$")
        mcq_option_pattern = re.compile(r"^[A-Z][.)]\s+(.*)")
        MCQ_MARKER = "multiple choice questions:"
        SHORT_MARKER = "answer the following shortly:"
        LONG_MARKER = "answer the following briefly:"

        while i < len(lines_in_section):
            match = numbered_q_pattern.match(lines_in_section[i])
            if not match:
                i += 1
                continue

            current_q_num = int(match.group(1))
            q_lines, options, answer_lines_raw, keyword_lines = [], [], [], []
            while i < len(lines_in_section) and not separator_pattern.match(lines_in_section[i]):
                line = lines_in_section[i].strip()
                if qtype == "MCQ":
                    option_match = mcq_option_pattern.match(line)
                    if option_match:
                        options.append(option_match.group(1).strip())
                    else:
                        q_lines.append(line)
                else:
                    q_lines.append(line)
                i += 1
            if i < len(lines_in_section) and separator_pattern.match(lines_in_section[i]):
                i += 1
            while i < len(lines_in_section):
                line = lines_in_section[i].strip()
                if numbered_q_pattern.match(line) or line.lower() in [MCQ_MARKER, SHORT_MARKER, LONG_MARKER]:
                    break
                if keyword_pattern.match(line):
                    keyword_content = line[line.find(":") + 1:].strip()
                    keyword_lines.append(keyword_content)
                    i += 1
                    while i < len(lines_in_section):
                        next_line = lines_in_section[i].strip()
                        if numbered_q_pattern.match(next_line) or next_line.lower() in [MCQ_MARKER, SHORT_MARKER, LONG_MARKER]:
                            break
                        keyword_lines.append(next_line)
                        i += 1
                    break
                else:
                    answer_lines_raw.append(line)
                    i += 1
            question_text = re.sub(r"^\d+[.)]\s*", "", " ".join(q_lines), count=1).strip()
            cleaned_answer_text = re.sub(r"^Answer:\s*", "", "\n".join(answer_lines_raw).strip(), flags=re.IGNORECASE)
            question_obj = {
                "questionNUM": f"pdf_{question_counter}",
                "questionType": qtype,
                "question": question_text
            }
            if qtype == "MCQ":
                question_obj["options"] = options
                letter_match = re.match(r"([A-D])\)?", cleaned_answer_text)
                if letter_match:
                    idx = ord(letter_match.group(1)) - ord("A")
                    question_obj["correctAnswer"] = options[idx] if 0 <= idx < len(options) else ""
                else:
                    match_opt = next((opt for opt in options if cleaned_answer_text.lower() in opt.lower()), "")
                    question_obj["correctAnswer"] = match_opt if match_opt else cleaned_answer_text
            else:
                question_obj["correctAnswer"] = cleaned_answer_text
                keywords = ", ".join(keyword_lines)
                question_obj["answerKeyword"] = [k.strip() for k in keywords.split(",") if k.strip()]
            questions.append(question_obj)
            question_counter += 1
        return questions, question_counter

    MCQ_MARKER = "multiple choice questions:"
    SHORT_MARKER = "answer the following shortly:"
    LONG_MARKER = "answer the following briefly:"

    mcq_start_idx = find_section_index(MCQ_MARKER, lines_for_json)
    short_start_idx = find_section_index(SHORT_MARKER, lines_for_json)
    long_start_idx = find_section_index(LONG_MARKER, lines_for_json)

    end_mcq_idx = min(filter(lambda x: x != -1, [short_start_idx, long_start_idx, len(lines_for_json)]))
    end_short_idx = long_start_idx if long_start_idx != -1 else len(lines_for_json)

    mcq_section = lines_for_json[mcq_start_idx + 1 : end_mcq_idx] if mcq_start_idx != -1 else []
    short_section = lines_for_json[short_start_idx + 1 : end_short_idx] if short_start_idx != -1 else []
    long_section = lines_for_json[long_start_idx + 1 :] if long_start_idx != -1 else []

    question_counter = 1
    all_questions = []

    if mcq_section:
        parsed, question_counter = parse_section(mcq_section, "MCQ", question_counter)
        all_questions.extend(parsed)
    if short_section:
        parsed, question_counter = parse_section(short_section, "Short Answer", question_counter)
        all_questions.extend(parsed)
    if long_section:
        parsed, question_counter = parse_section(long_section, "Long Answer", question_counter)
        all_questions.extend(parsed)

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, indent=4, ensure_ascii=False)

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
    for item in all_questions:
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
            summary = f"DUPLICATE #{dup_count}: {item['questionNUM']} duplicates {orig['questionNUM']} - {', '.join(mismatch) or 'all fields match'}"
            reports.append(f"{summary}\n\nOriginal:\n{json.dumps(orig, indent=4)}\n\nDuplicate:\n{json.dumps(item, indent=4)}\n{'='*70}\n")
        else:
            seen[norm] = item

    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        if reports:
            f.write(f"Found {dup_count} duplicate entries.\n{'='*70}\n\n" + "\n".join(reports))
        else:
            f.write("No duplicates found.\n")

    print(f"✅ Extracted to {json_output_path}")
    print(f"✅ Duplicate report saved to {duplicate_output_path}")


# --- Run ---
if __name__ == "__main__":
    process_english_pdf("english/english.pdf")
