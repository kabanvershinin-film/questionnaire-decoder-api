import json, re
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
from io import BytesIO

app = FastAPI()

# чтобы GitHub Pages мог дергать Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # позже можешь заменить на домен GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def norm(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\u200b\u00a0]", " ", s)
    s = re.sub(r"\([^)]*\)", "", s)  # убираем пояснения в скобках
    return s.strip().lower()

with open("decode_map.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

DECODE_MAP = {norm(k): v for k, v in raw.items()}
CHECK_MARKS = ("☑", "☒", "✔", "X", "x")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/decode")
async def decode(file: UploadFile = File(...)):
    data = await file.read()
    doc = Document(BytesIO(data))

    checked_lines = []
    for p in doc.paragraphs:
      t = (p.text or "").strip()
      if t and any(m in t for m in CHECK_MARKS):
        checked_lines.append(t)

    extracted = []
    for line in checked_lines:
      clean = line
      for m in CHECK_MARKS:
        clean = clean.replace(m, " ")
      clean = clean.strip(" -–—\t")
      extracted.append(clean)

    matched, missed, report_parts = [], [], []
    for symptom in extracted:
      key = norm(symptom)
      text = DECODE_MAP.get(key)
      if text:
        matched.append(symptom)
        report_parts.append(f"### {symptom}\n{text}")
      else:
        missed.append(symptom)

    report = "\n\n".join(report_parts) if report_parts else "Отмеченные пункты не найдены в базе расшифровок."
    return {"matched": matched, "missed": missed, "report_markdown": report}
