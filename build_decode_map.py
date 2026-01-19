from docx import Document
import json
import re

def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    return s.strip()

doc = Document("rashifrovka.docx")

decode = {}
current_key = None
buf = []

for p in doc.paragraphs:
    t = clean(p.text)
    if not t:
        continue

    # эвристика: "признак" обычно короткая строка, без точки в конце
    looks_like_key = (
        len(t) <= 220
        and not t.endswith(".")
        and not t.lower().startswith("возможные")
        and not t.lower().startswith("признак")
        and not t.lower().startswith("расшифровка")
    )

    if looks_like_key:
        if current_key and buf:
            decode[current_key] = "\n".join(buf).strip()
        current_key = t
        buf = []
    else:
        if current_key:
            buf.append(t)

if current_key and buf:
    decode[current_key] = "\n".join(buf).strip()

with open("decode_map.json", "w", encoding="utf-8") as f:
    json.dump(decode, f, ensure_ascii=False, indent=2)

print("OK. Keys:", len(decode))
