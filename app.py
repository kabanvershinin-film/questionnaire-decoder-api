import json, re, os
from difflib import get_close_matches
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PLUS_MARKS = {"+", "＋"}
FUZZY_CUTOFF = 0.58  # можно потом подкрутить

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00a0", " ").replace("\u200b", " ")
    s = re.sub(r"\([^)]*\)", "", s)  # убираем пояснения в скобках
    return s.strip().lower()

# 1) Грузим ID->расшифровка
DECODE_BY_ID = {}
if os.path.exists("decode_by_id.json"):
    with open("decode_by_id.json", "r", encoding="utf-8") as f:
        DECODE_BY_ID = json.load(f)

# 2) Грузим ID->вопрос (эталонный текст)
QUESTIONS_BY_ID = {}
if os.path.exists("questions_by_id.json"):
    with open("questions_by_id.json", "r", encoding="utf-8") as f:
        QUESTIONS_BY_ID = json.load(f)

# 3) Готовим обратный индекс: нормализованный вопрос -> ID
QUESTION_TEXT_TO_ID = {norm(v): k for k, v in QUESTIONS_BY_ID.items()}
QUESTION_KEYS = list(QUESTION_TEXT_TO_ID.keys())

@app.get("/health")
def health():
    return {
        "status": "ok",
        "decode_keys": len(DECODE_BY_ID),
        "question_keys": len(QUESTIONS_BY_ID)
    }

def find_id_by_text(symptom_text: str):
    """Находим ID по тексту пункта из опросника (без кодов)."""
    key = norm(symptom_text)
    if not key:
        return None, None, 0.0

    # 1) точное совпадение
    if key in QUESTION_TEXT_TO_ID:
        qid = QUESTION_TEXT_TO_ID[key]
        return qid, key, 1.0

    # 2) похожее совпадение
    if QUESTION_KEYS:
        cand = get_close_matches(key, QUESTION_KEYS, n=1, cutoff=FUZZY_CUTOFF)
        if cand:
            matched_key = cand[0]
            qid = QUESTION_TEXT_TO_ID[matched_key]
            return qid, matched_key, None

    return None, None, 0.0

@app.post("/decode")
async def decode(file: UploadFile = File(...)):
    data = await file.read()
    doc = Document(BytesIO(data))

    extracted = []

    # 1) таблицы "Признак | +"
    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) < 2:
                continue
            left = (row.cells[0].text or "").strip()
            right = (row.cells[1].text or "").strip()
            if right in PLUS_MARKS and left:
                extracted.append(left)

    # убираем дубли
    extracted = list(dict.fromkeys(extracted))

    matched, missed = [], []
    report_parts = []
    suggestions = {}  # пункт -> какой ID нашли (или подсказка)

    for symptom in extracted:
        qid, matched_key, score = find_id_by_text(symptom)

        if not qid:
            missed.append(symptom)
            continue

        text = DECODE_BY_ID.get(qid)
        suggestions[symptom] = qid

        if text:
            matched.append(symptom)
            # показываем заголовок по-человечески (без ID)
            report_parts.append(f"### {symptom}\n{text}")
        else:
            # ID нашли, но расшифровки нет
            missed.append(symptom)

    report = "\n\n".join(report_parts) if report_parts else "Отмеченные пункты не найдены в базе расшифровок."

    return {
        "matched": matched,
        "missed": missed,
        "extracted": extracted,
        "mapped_ids": suggestions,
        "report_markdown": report
    }
