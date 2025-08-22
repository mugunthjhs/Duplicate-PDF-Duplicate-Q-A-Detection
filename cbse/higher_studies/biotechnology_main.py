import re
import json
import os
import shutil
from docx import Document


def process_biotechnology_docx(docx_path):
    output_folder = "output_biotechnology"
    json_output_path = os.path.join(output_folder, "biotechnology_questions.json")
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")

    # --- Step 1: Clean/Create Output Directory ---
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # ---------- helpers ----------
    def norm_alnum(s: str) -> str:
        """Lowercase, remove all non [a-z0-9] for robust comparisons."""
        return re.sub(r'[^a-z0-9]+', '', s.lower())

    def process_block_for_explanation(block_lines, q_pattern):
        if not block_lines:
            return []

        m = q_pattern.match(block_lines[0])
        if not m:
            return block_lines

        q_num = int(m.group(1))

        if 1 <= q_num <= 81:
            EXPL_INLINE_RE = re.compile(r'(?i)\bexplan\w*\s*[:\-–—]?\s*')
            DASH_ANY_RE = re.compile(r'[-–—]{3,}')

            for i, line in enumerate(block_lines):
                m_ex = EXPL_INLINE_RE.search(line)
                if not m_ex:
                    continue

                final_lines = block_lines[:i]
                prefix = line[:m_ex.start()].rstrip()
                remainder = line[m_ex.end():]
                m_dash_same_line = DASH_ANY_RE.search(remainder)

                if prefix:
                    final_lines.append(prefix)

                if m_dash_same_line:
                    final_lines.append(m_dash_same_line.group(0))
                    if final_lines:
                        final_lines[-1] = final_lines[-1].rstrip()
                    return final_lines

                for j in range(i + 1, len(block_lines)):
                    if DASH_ANY_RE.search(block_lines[j]):
                        final_lines.append(block_lines[j].strip())
                        if final_lines:
                            final_lines[-1] = final_lines[-1].rstrip()
                        return final_lines

                if final_lines:
                    final_lines[-1] = final_lines[-1].rstrip()
                return final_lines

        return block_lines

    # ---------- Step 1: Cleaning Unwanted Content ----------
    def clean_text_lines(lines):
        cleaned = []
        normalized_targets = {
            "multiplechoicequestions",
            "answerthefollowingquestionsintwoorthreesentences",
            "answerthefollowing",
            "casestudyanswerindetail",
            "answerthefollowingquestionsbriefly",
        }
        has_mcq_marker = any(norm_alnum(l.strip()) == "multiplechoicequestions" for l in lines)
        skip_until_mcq = has_mcq_marker

        for raw in lines:
            line = raw.strip()
            if not line or line == "\x0c":
                continue

            nline = norm_alnum(line)

            if skip_until_mcq:
                if nline == "multiplechoicequestions":
                    skip_until_mcq = False
                continue

            if nline in normalized_targets:
                continue

            if all(w in nline for w in ("answer", "following", "questions")):
                continue

            if re.match(r'^\s*CHAPTER\s*[-–—]?\s*\d+\b.*$', line, re.IGNORECASE):
                continue

            u = line.upper()
            if "CBSE" in u and "GRADE" in u:
                continue
            if line.upper() == "PHYSICS":
                continue

            if re.fullmatch(r'\d+', line):
                continue
            if re.fullmatch(r'[A-Z]+', line):
                continue

            cleaned.append(line)
        return cleaned

    # ---------- Step 2: Formatting into Clean Blocks ----------
    def format_into_clean_blocks(lines):
        dense_lines = [line for line in lines if line.strip()]
        if not dense_lines:
            return ""

        q_pattern = re.compile(r'^\s*(\d{1,3})[.)]\s*')
        all_blocks = []
        current_block_lines = []

        for line in dense_lines:
            is_start = bool(q_pattern.match(line))

            if is_start and current_block_lines:
                processed = process_block_for_explanation(current_block_lines, q_pattern)
                if processed:
                    all_blocks.append("\n".join(processed))
                current_block_lines = []

            current_block_lines.append(line)

        if current_block_lines:
            processed = process_block_for_explanation(current_block_lines, q_pattern)
            if processed:
                all_blocks.append("\n".join(processed))

        separator = "\n" + "-" * 25 + "\n"
        return separator.join(all_blocks)

    # ---------- DOCX → TXT ----------
    def docx_to_clean_text(docx_path):
        doc = Document(docx_path)
        lines = [para.text for para in doc.paragraphs]
        content_lines = clean_text_lines(lines)
        final_text = format_into_clean_blocks(content_lines)
        return final_text

    # ---------- Parsing Utilities ----------
    def normalize_text(s: str) -> str:
        return re.sub(r"\s+", " ", s or "").strip().lower()

    def get_type_and_mark(qnum: int):
        if 1 <= qnum <= 80:
            return "MCQ", 1
        elif 81 <= qnum <= 110:
            return "Very Short Answer", 2
        elif 111 <= qnum <= 140:
            return "Short Answer", 3
        elif 141 <= qnum <= 170:
            return "Answer in Detail", 4
        elif 171 <= qnum <= 200:
            return "Long Answer", 5
        else:
            return "General", 0

    def clean_explanation_and_dashes(text: str) -> str:
        text = re.sub(r"Explanation\s*:.*?(?:-+\n)", "", text, flags=re.S | re.I)
        text = re.sub(r"-{3,}", "", text)
        return text.strip()

    def parse_questions_from_text(content: str):
        content = re.sub(r"(VERY\s*SHORT\s*ANSWER.*?APPLICATIONS|SHORT\s*ANSWER.*?\d+\s*MARKS|LONG\s*ANSWER.*?\d+\s*MARKS)", "", content, flags=re.I | re.S)
        content = clean_explanation_and_dashes(content)

        question_blocks = re.split(r"(?m)^(?=\s*\(?\d{1,3}\s*[\.\)])", content)
        questions_json = []

        for block in question_blocks:
            block = block.strip()
            if not block:
                continue

            m = re.match(r"^\s*\(?(\d{1,3})\s*[\.\)]\s*(.*)", block, re.S)
            if not m:
                continue
            qnum = int(m.group(1))
            qtype, mark = get_type_and_mark(qnum)

            if qtype == "MCQ":
                question_head = re.split(r"\n\s*[A-Da-d][\)\.]", block)[0]
                question_text = re.sub(r"^\s*\(?\d{1,3}\s*[\.\)]\s*", "", question_head).strip()
                question_text = re.sub(r"\s*\n\s*", " ", question_text)

                options = []
                options_block = re.findall(r"^[A-Da-d][\)\.]?\s*.*", block, re.M)
                for opt in options_block:
                    if re.match(r"(?i)^(ans|answer|correct answer|nswer)", opt.strip()):
                        continue
                    opt_clean = re.sub(r"^[A-Da-d][\)\.]?\s*", "", opt).strip()
                    if opt_clean:
                        options.append(opt_clean)

                ans_match = re.search(r"(Answer|Ans|Correct Answer)\s*[:\-]\s*((?:.|\n)*?)(?:\n\s*\n|$)", block, re.I)
                correct_answer_text = ans_match.group(2).strip() if ans_match else ""
                clean_answer = re.sub(r"^[A-Da-d][\)\.]?\s*", "", correct_answer_text).strip() if correct_answer_text else ""

                idx = None
                if options and clean_answer:
                    norm_ans = normalize_text(clean_answer)
                    for i, opt in enumerate(options):
                        if normalize_text(opt) == norm_ans:
                            idx = i
                            break

                data = {
                    "questionNUM": f"docx_{qnum}",
                    "question": question_text,
                    "questionType": qtype,
                    "image": None,
                }
                if options:
                    data["options"] = options
                if idx is not None:
                    data["correctOptionIndex"] = idx
                if clean_answer:
                    data["correctAnswer"] = clean_answer
                data["mark"] = mark

            else:
                question_lines = []
                lines = block.splitlines()
                for line in lines:
                    if re.match(r"(Answer|Ans|Keywords)\s*[:\-]", line, re.I):
                        break
                    clean_line = re.sub(r"^\s*\(?\d{1,3}\s*[\.\)]\s*", "", line).strip()
                    if clean_line:
                        question_lines.append(clean_line)
                question_text = " ".join(question_lines)

                ans_match = re.search(r"(Answer|Ans)\s*[:\-]\s*((?:.|\n)*?)(?:Keywords|$)", block, re.I)
                correct_answer_text = ans_match.group(2).strip() if ans_match else ""

                kw_match = re.search(r"Keywords\s*[:\-]\s*((?:.|\n)*?)$", block, re.I)
                answer_keywords = []
                if kw_match:
                    kw_blob = kw_match.group(1).strip()
                    raw = re.split(r"[,\n]+", kw_blob)
                    answer_keywords = [t.strip() for t in raw if t.strip()]

                data = {
                    "questionNUM": f"docx_{qnum}",
                    "question": question_text,
                    "questionType": qtype,
                    "image": None,
                }
                if correct_answer_text:
                    data["correctAnswer"] = correct_answer_text
                if answer_keywords:
                    data["answerKeyword"] = answer_keywords
                data["mark"] = mark

            questions_json.append(data)

        return questions_json

    # --- Step 2: Extract and Structure Questions ---
    clean_text = docx_to_clean_text(docx_path)
    ordered_questions = parse_questions_from_text(clean_text)

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
            if item.get("questionType", "").lower() == "mcq":
                mismatches_count = count_option_mismatches(item.get('options'), orig.get('options'))
                if mismatches_count > 0:
                    mismatch.append(f"{mismatches_count} options mismatched")
            summary = f"DUPLICATE : {item['questionNUM']} is a duplicate of {orig['questionNUM']} - {', '.join(mismatch) or 'all fields match'}"
            reports.append(f"{summary}\n\nOriginal:\n{json.dumps(orig, indent=2)}\n\nDuplicate:\n{json.dumps(item, indent=2)}\n{'='*70}\n")
        else:
            seen[norm] = item

    with open(duplicate_output_path, "w", encoding="utf-8") as f:
        if reports:
            f.write(f"Found {dup_count} duplicate entries.\n{'='*70}\n\n" + "\n".join(reports))
        else:
            f.write("No duplicates found.\n")

    print(f"✅ Extracted questions to {json_output_path}")
    print(f"✅ Duplicate report saved to {duplicate_output_path}")


# --- Run ---
if __name__ == "__main__":
    docx_file_path = r"input_biotech\G11 NCERT BIOTECHNOLOGY CHP- 6 WITHKEY.docx"
    if os.path.exists(docx_file_path):
        process_biotechnology_docx(docx_file_path)
    else:
        print(f"❌ Error: DOCX file not found at '{docx_file_path}'")
