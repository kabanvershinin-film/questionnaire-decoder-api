import json, re, os
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

# [KD-001], [PD-012], [IM-003], [UG-007]
ID_RE = re.compile(r"\[(KD|PD|IM|UG)-\d{3}\]")

PLUS_MARKS = {"+", "＋"}  # обычный + и полноширинный

# Загружаем расшифровку по ID
DECODE_BY_ID = {}
if os.path.exists("decode_by_id.json"):
    with open("decode_by_id.json", "r", encoding="utf-8") as f:
        DECODE_BY_ID = json.load(f)

@app.get("/health")
def health():
    return {"status": "ok", "decode_keys": len(DECODE_BY_ID)}

@app.post("/decode")
async def decode(file: UploadFile = File(...)):
    data = await file.read()
    doc = Document(BytesIO(data))

    found_ids = []

    # 1) Основной случай: таблицы "Признак | +"
    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) < 2:
                continue
            left = (row.cells[0].text or "").strip()
            right = (row.cells[1].text or "").strip()

            if right in PLUS_MARKS:
                m = ID_RE.search(left)
                if m:
                    found_ids.append(m.group(0).strip("[]"))

    # убираем дубли сохраняя порядок
    found_ids = list(dict.fromkeys(found_ids))

    matched, missed, report_parts = [], [], []
    for qid in found_ids:
        text = DECODE_BY_ID.get(qid)
        if text:
            matched.append(qid)
            report_parts.append(f"### [{qid}]\n{text}")
        else:
            missed.append(qid)

    report = "\n\n".join(report_parts) if report_parts else "Отмеченных пунктов с кодами не найдено."

    return {
        "matched": matched,
        "missed": missed,
        "found_ids": found_ids,
        "report_markdown": report
    }
