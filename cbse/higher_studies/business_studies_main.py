import re
import json
import os
import shutil

# --- python-docx imports (careful to avoid name collisions) ---
from docx import Document as LoadDocument      # to open .docx
from docx.document import Document as _Document  # internal docx type
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell


def process_business_studies_docx(docx_path):
    output_folder = "output_business_studies"
    json_output_path = os.path.join(output_folder, "business_studies_questions.json")
    duplicate_output_path = os.path.join(output_folder, "duplicate_output.txt")
    txt_output_path = os.path.join(output_folder, os.path.basename(docx_path).replace(".docx", "_cleaned.txt"))

    # --- Step 1: Clean/Create Output Directory ---
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # ---------- HELPERS: DOCX EXTRACTION & CLEANING ----------
    def _iter_block_items(parent):
        if isinstance(parent, _Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        elif isinstance(parent, Table):
            for row in parent.rows:
                for cell in row.cells:
                    for item in _iter_block_items(cell):
                        yield item
            return
        else:
            return

        for child in parent_elm.iterchildren():
            if child.tag.endswith('}p'):
                yield Paragraph(child, parent)
            elif child.tag.endswith('}tbl'):
                tbl = Table(child, parent)
                for item in _iter_block_items(tbl):
                    yield item

    def _get_num_info(p):
        try:
            pPr = p._p.pPr
            if pPr is None or pPr.numPr is None:
                return None
            numId_elm = pPr.numPr.numId
            ilvl_elm = pPr.numPr.ilvl
            numId = int(numId_elm.val) if numId_elm is not None and numId_elm.val is not None else None
            ilvl = int(ilvl_elm.val) if ilvl_elm is not None and ilvl_elm.val is not None else 0
            if numId is None:
                return None
            return (numId, ilvl)
        except Exception:
            return None

    def _extract_lines_with_numbering(doc_path):
        doc = LoadDocument(doc_path)
        counters = {}
        lines = []

        for item in _iter_block_items(doc):
            if not isinstance(item, Paragraph):
                continue
            text = (item.text or "").strip()
            num_info = _get_num_info(item)
            if num_info:
                numId, ilvl = num_info
                if numId not in counters:
                    counters[numId] = {}
                counters[numId][ilvl] = counters[numId].get(ilvl, 0) + 1
                if ilvl == 0:
                    if not re.match(r"^\d+\s*[\).]", text):
                        if text:
                            text = f"{counters[numId][ilvl]}) {text}"
                        else:
                            text = f"{counters[numId][ilvl]})"
            if text:
                lines.append(text)
            else:
                lines.append("")

        collapsed = []
        for ln in lines:
            if ln == "":
                if collapsed and collapsed[-1] != "":
                    collapsed.append("")
            else:
                collapsed.append(ln)
        return "\n".join(collapsed)

    def clean_extracted_text(text):
        lines = text.splitlines()
        cleaned_lines = []
        i = 0

        while i < len(lines):
            stripped_line = lines[i].strip()

            if re.search(r"CBSE\s*[-–]\s*GRADE\s*[-–]?\s*11", stripped_line, re.IGNORECASE) or \
               re.search(r"GRADE\s*[-–]\s*12", stripped_line, re.IGNORECASE) or \
               re.search(r"CHEMISTRY", stripped_line, re.IGNORECASE) or \
               re.search(r"STRUCTURE\s+OF\s+ATOM", stripped_line, re.IGNORECASE) or \
               re.match(r"^CHAPTER\s*[-–]?\s*\d+", stripped_line, re.IGNORECASE) or \
               re.match(r"^\s*Answer\s+the\s+following", stripped_line, re.IGNORECASE) or \
               re.search(r"Multiple\s+choice\s+questions", stripped_line, re.IGNORECASE) or \
               re.match(r"^\d+$", stripped_line) or \
               re.search(r"5\s*MARKS.*LONG\s*ANSWER", stripped_line, re.IGNORECASE) or \
               re.search(r"4\s*MARKS.*QUESTIONS", stripped_line, re.IGNORECASE) or \
               re.search(r"SHORT\s*ANSWER.*3\s*MARKS", stripped_line, re.IGNORECASE) or \
               re.search(r"VERY\s*SHORT\s*ANSWER.*2\s*MARKS.*REAL\s*TIME\s*APPLICATIONS", stripped_line, re.IGNORECASE):
                i += 1
                continue

            if re.search(r"BUSINESS\s+STUDIES", stripped_line, re.IGNORECASE):
                skip_count = 1
                if i + 1 < len(lines) and re.search(r"PART|CHAPTER", lines[i + 1], re.IGNORECASE):
                    skip_count += 1
                if i + 2 < len(lines) and re.search(r"CHAPTER", lines[i + 2], re.IGNORECASE):
                    skip_count += 1
                i += skip_count
                continue

            cleaned_lines.append(stripped_line)
            i += 1

        first_q_index = next((idx for idx, line in enumerate(cleaned_lines) if re.match(r"^(Q?\s*1[\).])", line, re.IGNORECASE)), None)
        if first_q_index is not None:
            cleaned_lines = cleaned_lines[first_q_index:]

        def split_inline_options(s: str):
            if re.search(r"\bA\)", s):
                parts = re.split(r"(?=(?:[A-H]\)))", s)
                return parts[0].strip(), [p.strip() for p in parts[1:] if p.strip()]
            return s, []

        final_lines = []
        expected_qnum = 1
        i = 0
        while i < len(cleaned_lines) and expected_qnum <= 200:
            line = cleaned_lines[i].strip()
            if re.match(r"^\d+[\).]", line, re.IGNORECASE):
                qtext = re.sub(r"^\d+[\).]", "", line).strip()
                j = i + 1
                block = []
                while j < len(cleaned_lines) and not re.match(r"^\d+[\).]", cleaned_lines[j].strip()):
                    block.append(cleaned_lines[j].strip())
                    j += 1
                if not qtext and block:
                    qtext = block.pop(0).strip()
                qtext, inline_opts = split_inline_options(qtext)
                if inline_opts:
                    block = inline_opts + block
                processed_block = []
                skip_explanation = False
                for bline in block:
                    if re.search(r"^Explanation", bline, re.IGNORECASE):
                        skip_explanation = True
                        continue
                    if skip_explanation and bline.strip() == "":
                        skip_explanation = False
                    if skip_explanation:
                        continue
                    if re.search(r"\bA\)", bline) and not bline.startswith("Answer:"):
                        head, opts = split_inline_options(bline)
                        if head: processed_block.append(head)
                        processed_block.extend(opts)
                    else:
                        processed_block.append(bline)
                final_lines.append(f"{expected_qnum}) {qtext}")
                final_lines.extend(processed_block)
                final_lines.append("-----------------")
                expected_qnum += 1
                i = j
            else:
                i += 1
        
        # Collapse multiple blank lines into one
        cleaned_final_lines = []
        for line in final_lines:
            if line.strip() != "":
                cleaned_final_lines.append(line)
            elif cleaned_final_lines and cleaned_final_lines[-1] != "":
                cleaned_final_lines.append("")
        return "\n".join(cleaned_final_lines)

    # ---------- HELPERS: PARSING & STRUCTURING ----------
    def normalize_text_for_match(s: str) -> str:
        return re.sub(r"\s+", " ", s or "").strip().lower()

    def get_type_and_mark(qnum: int):
        if 1 <= qnum <= 80: return "MCQ", 1
        elif 81 <= qnum <= 110: return "Very Short Answer", 2
        elif 111 <= qnum <= 140: return "Short Answer", 3
        elif 141 <= qnum <= 170: return "Answer in Detail", 4
        elif 171 <= qnum <= 200: return "Long Answer", 5
        return None, None

    def clean_explanation_and_dashes(text: str) -> str:
        text = re.sub(r"Explanation:.*?(?:-+\n)", "", text, flags=re.S | re.I)
        text = re.sub(r"-{5,}", "", text)
        return text.strip()
    
    def parse_questions_from_text(content: str):
        content = clean_explanation_and_dashes(content)
        question_blocks = re.split(r"(?m)^(?=\d{1,3}\s*[\.\)]\s+)", content)
        questions_json = []

        for block in filter(None, (b.strip() for b in question_blocks)):
            m = re.match(r"^(\d{1,3})\s*[\.\)]\s*(.*)", block, re.S)
            if not m: continue
            
            qnum = int(m.group(1))
            qtype, mark = get_type_and_mark(qnum)
            if not qtype: continue

            if qtype == "MCQ":
                question_head = re.split(r"\n[A-D]\)", block)[0]
                question_text = re.sub(r"^\d{1,3}\s*[\.\)]\s*|\s*\n\s*", " ", question_head).strip()
                options = [re.sub(r"^[A-D]\)\s*", "", opt).strip() for opt in re.findall(r"^[A-D]\)\s*.*", block, re.M)]
                ans_match = re.search(r"Answer:\s*((?:.|\n)*?)(?:\n\s*\n|$)", block, re.I)
                clean_answer = ""
                if ans_match:
                    clean_answer = re.sub(r"^[A-D]\)\s*", "", ans_match.group(1).strip()).strip()
                
                idx = None
                if options and clean_answer:
                    norm_ans = normalize_text_for_match(clean_answer)
                    idx = next((i for i, opt in enumerate(options) if normalize_text_for_match(opt) == norm_ans), None)

                data = {"questionNUM": f"docx_{qnum}", "question": question_text, "questionType": qtype, "image": None}
                if options: data["options"] = options
                if idx is not None: data["correctOptionIndex"] = idx
                if clean_answer: data["correctAnswer"] = clean_answer
                data["mark"] = mark
            else:
                lines = block.splitlines()
                q_lines = [re.sub(r"^\d{1,3}\s*[\.\)]\s*", "", line).strip() for line in lines if not line.strip().startswith(("Answer:", "Keywords:"))]
                question_text = " ".join(filter(None, q_lines))
                
                ans_match = re.search(r"Answer:\s*((?:.|\n)*?)(?:Keywords:|\n\s*\n|$)", block, re.I)
                correct_answer_text = ans_match.group(1).strip() if ans_match else ""
                
                kw_match = re.search(r"Keywords:\s*((?:.|\n)*?)(?:\n\s*\n|$)", block, re.I)
                answer_keywords = []
                if kw_match:
                    answer_keywords = [t.strip() for t in re.split(r"[,\n]+", kw_match.group(1).strip()) if t.strip()]

                data = {"questionNUM": f"docx_{qnum}", "question": question_text, "questionType": qtype, "image": None}
                if correct_answer_text: data["correctAnswer"] = correct_answer_text
                if answer_keywords: data["answerKeyword"] = answer_keywords
                data["mark"] = mark

            questions_json.append(data)
        return questions_json

    # --- Step 2: Extract and Clean Text from DOCX ---
    try:
        raw_text = _extract_lines_with_numbering(docx_path)
        cleaned_text = clean_extracted_text(raw_text)
        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)
    except Exception as e:
        print(f"❌ Failed to extract content from DOCX: {e}")
        print("❌ Please check the file format and review the console logs for processing errors.")
        return

    # --- Step 3: Parse Questions from Text ---
    ordered_questions = parse_questions_from_text(cleaned_text)
    
    # --- Step 4: Write JSON Output ---
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(ordered_questions, f, ensure_ascii=False, indent=4)
    print(f"✅ Extracted and converted {len(ordered_questions)} questions -> {json_output_path}")

    # --- Step 5: Duplicate Detection ---
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
        if not norm: continue
        
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

    print(f"✅ Duplicate report saved to {duplicate_output_path} ({dup_count} duplicates found)")


# --- Run ---
if __name__ == "__main__":
    docx_file_path = r"business_studies\G12_CBSE_PART A_Ch 1_200 Q&A_With Key_Nature and Sig of mgmt.docx"
    if os.path.exists(docx_file_path):
        process_business_studies_docx(docx_file_path)
        print("✅ All processing complete.")
    else:
        print(f"❌ Error: DOCX file not found at '{docx_file_path}'")