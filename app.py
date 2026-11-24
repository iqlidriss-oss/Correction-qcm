# -*- coding: utf-8 -*-
"""
app.py — «دفتر التصحيح» : مصحح آلي لورقة امتحان الإعلام الآلي (20 نقطة)
يرفع الأستاذ صورة نسخة الطالب، يقرأها بجانب نموذج الإجابة (تكبير/تدوير/تباين/OCR اختياري)،
يؤشر الإجابات، فيصحح التطبيق آليًا ويحفظ النتائج في سجل قابل للبحث والفرز والتصدير.

التشغيل:
    pip install streamlit pillow
    streamlit run app.py

اختياري (لاستخراج النص OCR من الصورة):
    pip install pytesseract
    + تثبيت tesseract-ocr مع حزمة اللغة الفرنسية (fra)
    بدون OCR يبقى كل شيء يعمل: القراءة من الصورة والإدخال اليدوي المصحح آليًا.
"""

import base64
import csv
import io
import json
import re
import shutil
import unicodedata
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

try:
    from PIL import Image, ImageEnhance, ImageOps
    PHOTO_OK = True
except Exception:
    PHOTO_OK = False

try:
    import pytesseract
    OCR_OK = bool(shutil.which("tesseract"))
except Exception:
    OCR_OK = False

# ============================================================
# 1) أدوات مساعدة
# ============================================================

def norm(txt):
    if not txt:
        return ""
    txt = unicodedata.normalize("NFD", txt.strip().lower())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = txt.replace("’", "'")
    txt = re.sub(r"^(l'|d'|le |la |les |un |une )", "", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip(" .;,:!?")


def parse_decimal(txt):
    s = re.sub(r"\s+", "", txt or "")
    s = re.sub(r"\((\d+)\)(?:10|₁₀)?", r"\1", s)
    s = s.replace("₁₀", "")
    if s and re.fullmatch(r"\d+", s):
        return int(s)
    return None


def parse_binary(txt):
    s = re.sub(r"\s+", "", txt or "")
    s = re.sub(r"\(([01]+)\)(?:2|₂)?", r"\1", s)
    s = s.replace("₂", "")
    if s and re.fullmatch(r"[01]+", s):
        return int(s, 2)
    return None


def mention(total):
    if total >= 16:
        return "ممتاز — Très bien"
    if total >= 14:
        return "جيد جدًا — Bien"
    if total >= 12:
        return "جيد — Assez bien"
    if total >= 10:
        return "مقبول — Passable"
    return "ضعيف — Insuffisant"


# ============================================================
# 2) محتوى الامتحان والتصحيح النموذجي
# ============================================================

EX1_QUESTIONS = [
    {"id": "q1",
     "prompt": "Le schéma de traitement de l'information est constitué de :",
     "options": {"d": "Traitement → Donnée → Résultat",
                 "e": "Résultat → Traitement → Donnée",
                 "f": "Donnée → Traitement → Résultat"},
     "correct": {"f"}},
    {"id": "q2",
     "prompt": "L'informatique se compose des mots suivants :",
     "options": {"g": "Information + automotive",
                 "h": "Information + automatique",
                 "i": "Information + automobile"},
     "correct": {"h"}},
    {"id": "q3",
     "prompt": "Le traitement est automatique veut dire :",
     "options": {"j": "Qu'il est effectué par l'homme.",
                 "k": "Qu'il est effectué par la machine.",
                 "l": "Qu'il est effectué par l'homme et la machine."},
     "correct": {"k"}},
    {"id": "q4",
     "prompt": "Le mot « software » désigne :",
     "options": {"e": "la partie logicielle",
                 "c": "la partie matérielle",
                 "d": "un programme"},
     "correct": {"e", "d"}},
]

EX2_SENTENCES = [
    ("s1", "L'informatique est la **……(1)……** du traitement automatique de **……(2)……**",
     [("ex2_s1_1", {"science"}, "science"),
      ("ex2_s1_2", {"information"}, "information")]),
    ("s2", "Information = **……(1)……** + **……(2)……**",
     [("ex2_s2_1", {"donnee", "sens"}, "donnée + sens (ordre libre)"),
      ("ex2_s2_2", {"donnee", "sens"}, "donnée + sens (ordre libre)")]),
    ("s3", "Le langage de l'ordinateur est basé seulement sur deux **……(1)……** : 0 et 1. "
           "Ce langage est appelé langage **……(2)……**",
     [("ex2_s3_1", {"bits", "bit"}, "bits"),
      ("ex2_s3_2", {"binaire"}, "binaire")]),
]

EX3_ITEMS = [
    ("e", "(101100)₂ = ( … )₁₀", "dec", 44, "44"),
    ("f", "(110101)₂ = ( … )₁₀", "dec", 53, "53"),
    ("g", "(28)₁₀ = ( … )₂", "bin", 28, "11100"),
    ("h", "(65)₁₀ = ( … )₂", "bin", 65, "1000001"),
]

EX4_ITEMS = [
    {"id": "a",
     "text": "L'information est une donnée ou ensemble des données ayant un sens.",
     "expected": "Vrai", "correction": None},
    {"id": "d",
     "text": "Un système informatique est constitué uniquement de logicielle.",
     "expected": "Faux",
     "correction": "Un système informatique est constitué de la partie matérielle "
                   "(hardware) ET de la partie logicielle (software)."},
    {"id": "b",
     "text": "Les informations peuvent être sous forme texte.",
     "expected": "Vrai", "correction": None},
]

EX_TITLES = {"ex1": "التمرين 1 — الاختيار من متعدد", "ex2": "التمرين 2 — إكمال التعاريف",
             "ex3": "التمرين 3 — التحويل ثنائي/عشري", "ex4": "التمرين 4 — صحيح/خطأ مع التصحيح"}
EX_MAX = {"ex1": 4, "ex2": 6, "ex3": 4, "ex4": 6}

# ============================================================
# 3) محرك التصحيح
# ============================================================

def grade(ans, software_accept_program, ex4d_mode):
    scores = {"ex1": 0, "ex2": 0, "ex3": 0, "ex4": 0}
    details = []

    def add(ex, label, given, expected, pts, mx):
        scores[ex] += pts
        details.append({"ex": ex, "label": label, "given": given,
                        "expected": expected, "pts": pts, "max": mx})

    for q in EX1_QUESTIONS:
        correct = set(q["correct"])
        if q["id"] == "q4" and not software_accept_program:
            correct = {"e"}
        given = set(ans["ex1"][q["id"]])
        pts = 1 if given == correct else 0
        add("ex1", f"Ex1 ({q['id']}) : {q['prompt']}",
            ", ".join(sorted(given)) or "—", ", ".join(sorted(correct)), pts, 1)

    for sid, sentence, blanks in EX2_SENTENCES:
        vals = [norm(ans["ex2"][k]) for k, _, _ in blanks]
        if sid == "s2":
            ok1 = vals[0] in {"donnee", "sens"}
            ok2 = vals[1] in {"donnee", "sens"}
            if ok1 and ok2 and vals[0] == vals[1]:
                ok2 = False
            oks = [ok1, ok2]
        else:
            oks = [vals[i] in blanks[i][1] for i in range(len(blanks))]
        for i, (key, _, expected) in enumerate(blanks):
            add("ex2", f"Ex2 ({key})", ans["ex2"][key] or "—",
                expected, 1 if oks[i] else 0, 1)

    for qid, label, kind, val, exp in EX3_ITEMS:
        raw = ans["ex3"][qid]
        parsed = parse_decimal(raw) if kind == "dec" else parse_binary(raw)
        pts = 1 if parsed is not None and parsed == val else 0
        add("ex3", f"Ex3 ({qid}) {label}", raw or "—", exp, pts, 1)

    mode = {"تلقائي (كلمات مفتاحية)": "auto",
            "قبول يدوي": "accept", "رفض يدوي": "reject"}[ex4d_mode]
    for item in EX4_ITEMS:
        choice = ans["ex4"][item["id"]]["choice"]
        corr = ans["ex4"][item["id"]]["corr"]
        if item["expected"] == "Vrai":
            pts = 2 if choice == "Vrai" else 0
            expected = "Vrai"
        else:
            pts = 1 if choice == "Faux" else 0
            c = norm(corr)
            auto_ok = ("materiel" in c or "hardware" in c) and \
                      ("logiciel" in c or "software" in c)
            corr_ok = auto_ok if mode == "auto" else (mode == "accept")
            if choice == "Faux" and corr_ok:
                pts += 1
            expected = "Faux + correction : " + item["correction"]
        given = choice + (f" | {corr}" if corr else "")
        add("ex4", f"Ex4 ({item['id']})", given, expected, pts, 2)

    return {"scores": scores, "total": sum(scores.values()), "details": details}


def build_report(rec):
    s = rec["scores"]
    lines = ["======= تقرير تصحيح امتحان الإعلام الآلي =======",
             f"الطالب: {rec.get('name') or '—'}",
             f"القسم: {rec.get('classe') or '—'}",
             f"التاريخ: {rec.get('date') or '—'}",
             "-" * 46,
             f"التمرين 1: {s['ex1']}/4", f"التمرين 2: {s['ex2']}/6",
             f"التمرين 3: {s['ex3']}/4", f"التمرين 4: {s['ex4']}/6",
             f"المجموع: {rec['total']}/20  ({mention(rec['total'])})",
             "-" * 46]
    for d in rec["details"]:
        lines.append(f"[{d['pts']}/{d['max']}] {d['label']}")
        lines.append(f"    إجابة الطالب: {d['given']}")
        lines.append(f"    الصحيحة: {d['expected']}")
    return "\n".join(lines)


def serialise_answers(ans):
    return {"ex1": {k: sorted(v) for k, v in ans["ex1"].items()},
            "ex2": dict(ans["ex2"]), "ex3": dict(ans["ex3"]),
            "ex4": {k: dict(v) for k, v in ans["ex4"].items()}}


# ============================================================
# 4) السجل : تخزين، بذور، تراجع
# ============================================================

STORE = Path(__file__).with_name("corrections_store.json")


def make_record(name, classe, d, ans, soft=True, mode="auto"):
    res = grade(ans, soft, mode)
    return {"id": uuid.uuid4().hex[:8], "name": name, "classe": classe, "date": d,
            "answers": serialise_answers(ans), "settings": {"soft": soft, "mode": mode},
            "scores": res["scores"], "total": res["total"], "details": res["details"]}


def seed_records():
    a1 = {"ex1": {"q1": {"f"}, "q2": {"h"}, "q3": {"k"}, "q4": {"e", "d"}},
          "ex2": {"ex2_s1_1": "science", "ex2_s1_2": "l'information",
                  "ex2_s2_1": "donnée", "ex2_s2_2": "sens",
                  "ex2_s3_1": "bits", "ex2_s3_2": "binaire"},
          "ex3": {"e": "44", "f": "53", "g": "11100", "h": "1000001"},
          "ex4": {"a": {"choice": "Vrai", "corr": ""},
                  "d": {"choice": "Faux", "corr": "Il est constitué de la partie matérielle et de la partie logicielle."},
                  "b": {"choice": "Vrai", "corr": ""}}}
    a2 = {"ex1": {"q1": {"f"}, "q2": {"h"}, "q3": {"k"}, "q4": {"e"}},
          "ex2": {"ex2_s1_1": "science", "ex2_s1_2": "",
                  "ex2_s2_1": "donnée", "ex2_s2_2": "sens",
                  "ex2_s3_1": "chiffres", "ex2_s3_2": "binaire"},
          "ex3": {"e": "44", "f": "52", "g": "11100", "h": "100001"},
          "ex4": {"a": {"choice": "Vrai", "corr": ""},
                  "d": {"choice": "Faux", "corr": "hardware et software"},
                  "b": {"choice": "Faux", "corr": ""}}}
    a3 = {"ex1": {"q1": {"d"}, "q2": {"h"}, "q3": {"j"}, "q4": {"c"}},
          "ex2": {"ex2_s1_1": "science", "ex2_s1_2": "",
                  "ex2_s2_1": "donnée", "ex2_s2_2": "",
                  "ex2_s3_1": "bits", "ex2_s3_2": ""},
          "ex3": {"e": "44", "f": "52", "g": "11000", "h": ""},
          "ex4": {"a": {"choice": "Faux", "corr": ""},
                  "d": {"choice": "Faux", "corr": ""},
                  "b": {"choice": "Vrai", "corr": ""}}}
    return [make_record("أمينة بن يوسف", "1AS-1", "2026-11-20", a1),
            make_record("ياسين مرابط", "1AS-1", "2026-11-18", a2),
            make_record("ليلى حمداوي", "1AS-2", "2026-11-16", a3)]


def load_records():
    try:
        if STORE.exists():
            data = json.loads(STORE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    return seed_records()


def save_store():
    try:
        STORE.write_text(json.dumps(st.session_state.records, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    except Exception:
        pass


def cb_delete(ids):
    batch = [r for r in st.session_state.records if r["id"] in ids]
    st.session_state.records = [r for r in st.session_state.records if r["id"] not in ids]
    st.session_state.undo.append(batch)
    for i in ids:
        st.session_state.pop(f"sel_{i}", None)
    if st.session_state.get("loaded_id") in ids:
        st.session_state.loaded_id = None
    save_store()
    st.toast(f"🗑 حُذفت {len(batch)} نسخة — يمكن التراجع", icon="⚠️")


def cb_undo():
    if st.session_state.undo:
        batch = st.session_state.undo.pop()
        st.session_state.records = batch + st.session_state.records
        save_store()
        st.toast(f"↩️ تم استرجاع {len(batch)} نسخة", icon="✅")


def cb_edit(rec):
    a = rec["answers"]
    for q in EX1_QUESTIONS:
        sel = set(a["ex1"].get(q["id"], []))
        for letter in q["options"]:
            st.session_state[f"ex1_{q['id']}_{letter}"] = letter in sel
    for k, v in a["ex2"].items():
        st.session_state[k] = v
    for k, v in a["ex3"].items():
        st.session_state[f"ex3_{k}"] = v
    for item in EX4_ITEMS:
        e = a["ex4"].get(item["id"], {"choice": "—", "corr": ""})
        st.session_state[f"ex4_{item['id']}_choice"] = e["choice"]
        if item["expected"] == "Faux":
            st.session_state[f"ex4_{item['id']}_corr"] = e["corr"]
    st.session_state.stu_name = rec["name"]
    st.session_state.stu_classe = rec["classe"]
    try:
        st.session_state.stu_date = date.fromisoformat(rec["date"])
    except Exception:
        pass
    st.session_state.loaded_id = rec["id"]
    st.session_state.page = "work"
    st.session_state.pop("last_result", None)
    st.toast("✏️ فُتحت النسخة في المصحح للتعديل", icon="📂")


def cb_save():
    lr = st.session_state.get("last_result")
    if not lr:
        return
    rec = {"id": st.session_state.get("loaded_id") or uuid.uuid4().hex[:8],
           "name": lr["name"] or "بدون اسم", "classe": lr["classe"], "date": lr["date"],
           "answers": lr["answers"], "settings": lr["settings"],
           "scores": lr["scores"], "total": lr["total"], "details": lr["details"]}
    ids = [r["id"] for r in st.session_state.records]
    if rec["id"] in ids:
        st.session_state.records = [rec if r["id"] == rec["id"] else r
                                    for r in st.session_state.records]
        st.toast("💾 حُدّثت النسخة في السجل", icon="✅")
    else:
        st.session_state.records = [rec] + st.session_state.records
        st.toast("💾 حُفظت النسخة في السجل", icon="✅")
    st.session_state.loaded_id = rec["id"]
    save_store()


def cb_reset_form():
    for k in list(st.session_state.keys()):
        if k.startswith(("ex1_", "ex2_", "ex3_", "ex4_", "ocr_pick_")):
            del st.session_state[k]
    st.session_state.pop("last_result", None)
    st.session_state.loaded_id = None
    st.toast("🧹 فُرّغ النموذج", icon="🧹")


def cb_chip(cfg):
    for k, v in cfg.items():
        st.session_state[k] = v


def cb_rotate(d):
    st.session_state.ph_rot = (st.session_state.get("ph_rot", 0) + d) % 360


def cb_photo_reset():
    for k, v in {"ph_zoom": 760, "ph_rot": 0, "ph_contrast": 1.0,
                 "ph_bright": 1.0, "ph_gray": False, "ph_invert": False,
                 "ph_fit": False}.items():
        st.session_state[k] = v


def cb_pick(qid):
    val = st.session_state.get(f"ocr_pick_{qid}", "—")
    if val and val != "—":
        st.session_state[f"ex3_{qid}"] = val


# ============================================================
# 5) معالجة الصورة و OCR
# ============================================================

@st.cache_data(show_spinner=False)
def img_pipeline(data, rot, contrast, bright, gray, invert, maxdim=1600):
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((maxdim, maxdim))
    if rot:
        im = im.rotate(-rot, expand=True)
    if gray:
        im = ImageOps.grayscale(im).convert("RGB")
    if invert:
        im = ImageOps.invert(im)
    if contrast != 1.0:
        im = ImageEnhance.Contrast(im).enhance(contrast)
    if bright != 1.0:
        im = ImageEnhance.Brightness(im).enhance(bright)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def run_ocr(data):
    im = Image.open(io.BytesIO(data)).convert("L")
    im = ImageEnhance.Contrast(im).enhance(1.6)
    if max(im.size) < 1400:
        im = im.resize((im.width * 2, im.height * 2))
    text = ""
    for lang in ("fra", "eng", None):
        try:
            text = pytesseract.image_to_string(im, lang=lang) if lang \
                else pytesseract.image_to_string(im)
            break
        except Exception:
            continue
    bins = sorted(set(re.findall(r"\b[01]{4,8}\b", text)))[:10]
    decs = sorted(set(re.findall(r"\b\d{1,3}\b", text)), key=int)[:12]
    return text, bins, decs


# ============================================================
# 6) الهوية البصرية — «ورقة امتحان وحبر وقلم أحمر»
# ============================================================

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Space+Grotesk:wght@500;700&family=IBM+Plex+Mono:wght@500&display=swap');
:root{
  --paper:#f7f2e7; --paper2:#efe6d3; --card:#fffdf6; --line:#e0d5bc;
  --ink:#1c2b4a; --ink2:#27406e; --ink3:#31508c;
  --pen:#c8322b; --pen2:#a02019; --blue:#2456c8; --green:#177e4d;
  --amber:#c07f16; --violet:#6b4fd8; --teal:#0f7f86; --mut:#6b6252;
}
*{scrollbar-width:thin;scrollbar-color:var(--pen) var(--paper2);}
*::-webkit-scrollbar{width:10px;height:10px}
*::-webkit-scrollbar-track{background:var(--paper2);border-radius:8px}
*::-webkit-scrollbar-thumb{background:linear-gradient(180deg,var(--pen),var(--pen2));border-radius:8px;border:2px solid var(--paper2)}
*::-webkit-scrollbar-thumb:hover{background:var(--pen2)}
.stApp{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(36,86,200,.07), transparent 60%),
    radial-gradient(900px 420px at -10% 110%, rgba(200,50,43,.06), transparent 60%),
    repeating-linear-gradient(0deg, transparent 0 30px, rgba(28,43,74,.035) 30px 31px),
    var(--paper);
  color:var(--ink);
  font-family:'Cairo',system-ui,sans-serif;
}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#152238 0%,var(--ink) 55%,#20335a 100%);
  border-right:4px solid var(--pen);
}
[data-testid="stSidebar"] *{color:#ede4d0}
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="select"]>div{
  background:#0f1a2e;border:1px solid #33507e;color:#f2ead9;border-radius:10px}
[data-testid="stSidebar"] hr{border-color:#33507e}
.rtl{direction:rtl;text-align:right}
.exam-banner{
  background:linear-gradient(120deg,#152238 0%,var(--ink2) 45%,var(--ink3) 78%,#3c5f9e 100%);
  border-top:5px solid var(--pen);
  border-radius:16px;padding:20px 26px;color:var(--paper);
  display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;
  box-shadow:0 12px 30px rgba(21,34,56,.28);
  animation:rise .5s ease both;
}
.exam-banner h1{font-size:1.5rem;font-weight:800;margin:0;color:#fff}
.exam-banner .sub{font-family:'Space Grotesk';opacity:.85;font-size:.85rem;letter-spacing:.4px}
.pt-chip{display:inline-block;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.35);
  border-radius:999px;padding:2px 12px;margin:2px;font-size:.8rem;font-weight:600}
.total-ring{border:3px solid var(--pen);border-radius:50%;width:86px;height:86px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  transform:rotate(-6deg);background:rgba(200,50,43,.14);color:#fff;
  font-family:'Space Grotesk';font-weight:700;box-shadow:0 0 0 4px rgba(200,50,43,.15)}
.total-ring b{font-size:1.5rem;line-height:1}
.total-ring span{font-size:.65rem;opacity:.85}
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card);border:1px solid var(--line);border-radius:14px;
  box-shadow:0 3px 12px rgba(28,43,74,.08);animation:rise .45s ease both}
[data-testid="stMetric"]{
  background:var(--card);border:1px solid var(--line);border-left:5px solid var(--blue);
  border-radius:12px;padding:10px 14px;box-shadow:0 2px 8px rgba(28,43,74,.08);animation:rise .4s ease both}
[data-testid="stMetricLabel"]{color:var(--mut);font-weight:600}
[data-testid="stMetricValue"]{color:var(--ink);font-family:'Space Grotesk';font-weight:700}
[data-baseweb="tab-list"]{gap:6px;border-bottom:2px solid var(--line);flex-wrap:wrap}
[data-baseweb="tab"]{background:var(--paper2);border-radius:10px 10px 0 0;color:var(--mut);
  font-weight:700;font-family:'Cairo';border-top:3px solid transparent}
[data-baseweb="tab"]:nth-child(1){border-top-color:var(--blue)}
[data-baseweb="tab"]:nth-child(2){border-top-color:var(--amber)}
[data-baseweb="tab"]:nth-child(3){border-top-color:var(--violet)}
[data-baseweb="tab"]:nth-child(4){border-top-color:var(--teal)}
[data-baseweb="tab"][aria-selected="true"]{background:var(--ink);color:var(--paper)}
[data-baseweb="tab-highlight"]{background:var(--pen)}
[data-baseweb="input"],[data-baseweb="textarea"]{
  background:#fff;border:1px solid var(--line);border-radius:10px;color:var(--ink)}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within{
  border-color:var(--blue);box-shadow:0 0 0 3px rgba(36,86,200,.15)}
.stButton>button,[data-testid="stFormSubmitButton"]>button{
  background:linear-gradient(135deg,var(--pen),var(--pen2));color:#fff;border:none;
  border-radius:10px;font-weight:700;font-family:'Cairo';
  box-shadow:0 2px 0 #7c150f,0 6px 14px rgba(200,50,43,.25);transition:all .15s ease}
.stButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{
  transform:translateY(-1px);filter:brightness(1.08);color:#fff}
.stButton>button:active{transform:translateY(1px);box-shadow:0 1px 0 #7c150f}
.stDownloadButton>button{
  background:transparent;border:2px solid var(--blue);color:var(--blue);
  border-radius:10px;font-weight:700;box-shadow:none}
.stDownloadButton>button:hover{background:rgba(36,86,200,.08);color:var(--blue)}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--line);border-radius:12px}
[data-testid="stExpander"] summary{font-weight:700;color:var(--ink)}
[data-testid="stFileUploaderDropzone"]{
  background:#fff8ec;border:2px dashed var(--pen);border-radius:14px}
[data-testid="stFileUploaderDropzone"] button{
  background:var(--ink);color:#fff;border:none;border-radius:8px;font-weight:700}
.photo-frame{
  height:min(62vh,640px);overflow:auto;padding:16px;border-radius:12px;
  background:
    radial-gradient(600px 300px at 50% 0%, rgba(49,80,140,.5), transparent 70%),
    repeating-linear-gradient(45deg,#1a2a47 0 14px,#182741 14px 28px);
  border:1px solid #33507e;cursor:grab}
.photo-frame img{display:block;margin:0 auto;background:#fff;border-radius:4px;
  box-shadow:0 14px 34px rgba(0,0,0,.5)}
.score-badge{font-family:'Space Grotesk';font-weight:700;font-size:1.35rem;
  border-radius:12px;padding:6px 12px;display:inline-block;transform:rotate(-2deg)}
.pass{background:rgba(23,126,77,.12);color:var(--green);border:2px solid var(--green)}
.fail{background:rgba(200,50,43,.1);color:var(--pen);border:2px solid var(--pen)}
.rec-name{font-weight:800;font-size:1.05rem;color:var(--ink)}
.rec-meta{color:var(--mut);font-size:.82rem}
.undo-bar{background:rgba(192,127,22,.12);border:1px solid var(--amber);
  border-radius:12px;padding:8px 14px;color:#7a5210;font-weight:600}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

# ============================================================
# 7) تهيئة الحالة
# ============================================================

st.set_page_config(page_title="دفتر التصحيح — امتحان الإعلام الآلي",
                   page_icon="🖊️", layout="wide")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

st.session_state.setdefault("records", load_records())
st.session_state.setdefault("undo", [])
st.session_state.setdefault("detail_id", None)
st.session_state.setdefault("loaded_id", None)
st.session_state.setdefault("page", "work")
for k, v in {"ph_zoom": 760, "ph_rot": 0, "ph_contrast": 1.0, "ph_bright": 1.0,
             "ph_gray": False, "ph_invert": False, "ph_fit": False}.items():
    st.session_state.setdefault(k, v)

# ============================================================
# 8) الشريط الجانبي : تنقل + إعدادات
# ============================================================

with st.sidebar:
    st.markdown('<div class="rtl"><h2 style="margin:0">🖊️ دفتر التصحيح</h2>'
                '<p style="opacity:.8;margin:2px 0 10px">Informatique — 20 points</p></div>',
                unsafe_allow_html=True)
    pages = {"work": "🖊️ تصحيح نسخة", "records": "🗂️ سجل النتائج", "key": "📖 الورقة والنموذج"}
    st.radio("التنقل", list(pages), key="page",
             format_func=lambda p: pages[p] + (f"  ({len(st.session_state.records)})" if p == "records" else ""),
             label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="rtl"><b>⚙️ سلّم التنقيط والخيارات</b></div>', unsafe_allow_html=True)
    st.checkbox("سؤال software : قبول « un programme » أيضًا", value=True, key="set_soft")
    st.selectbox("نقطة تصحيح العبارة (Ex4-d)",
                 ["تلقائي (كلمات مفتاحية)", "قبول يدوي", "رفض يدوي"], key="set_mode")
    st.caption("ت1: 4ن (1 لكل سؤال) · ت2: 6ن (1 لكل خانة) · ت3: 4ن · ت4: 6ن (2 لكل عبارة)")
    st.divider()
    if OCR_OK:
        st.success("OCR متوفر — استخراج النص مفعّل", icon="🔍")
    else:
        st.info("OCR غير متوفر: thبّت pytesseract و tesseract-ocr (fra). "
                "التصحيح يعمل كاملًا بدونه_via القراءة من الصورة.", icon="ℹ️")
    st.caption(f"💾 السجل محفوظ في: {STORE.name}")

# ============================================================
# 9) صفحة التصحيح
# ============================================================

def page_work():
    st.markdown("""
    <div class="exam-banner">
      <div>
        <h1>امتحان مبادئ الإعلام الآلي — الثلاثي الأول</h1>
        <div class="sub">Examen d'informatique · Correction assistée par copie scannée</div>
        <div style="margin-top:8px">
          <span class="pt-chip">Ex 1 · 4 pts</span><span class="pt-chip">Ex 2 · 6 pts</span>
          <span class="pt-chip">Ex 3 · 4 pts</span><span class="pt-chip">Ex 4 · 6 pts</span>
        </div>
      </div>
      <div class="total-ring"><b>20</b><span>مجموع النقاط</span></div>
    </div>""", unsafe_allow_html=True)
    st.write("")

    pre = st.session_state.pop("prefill", None)
    if pre:
        cb_edit(pre)

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1.2, 1])
        c1.text_input("👤 اسم ولقب الطالب", key="stu_name", placeholder="مثال: أمينة بن يوسف")
        c2.text_input("🏫 القسم", key="stu_classe", placeholder="1AS-1")
        c3.date_input("📅 التاريخ", key="stu_date", value=date.today())
        if st.session_state.get("loaded_id"):
            st.caption(f"✏️ وضع التعديل — النسخة رقم {st.session_state.loaded_id}")

    with st.expander("🧭 كيف تصحح نسخة؟ (3 خطوات)", expanded=False):
        st.markdown('<div class="rtl">① ارفع صورة نسخة الطالب أدناه · ② اقرأ الصورة المكبرة bên cạnh '
                    'وأشّر إجاباته في النموذج (أو استعن بـ OCR) · ③ اضغط «تصحيح الورقة» ثم احفظ النتيجة في السجل.</div>',
                    unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="rtl"><b>📷 نسخة الطالب (صورة)</b></div>', unsafe_allow_html=True)
        up = st.file_uploader("ارفع صورة النسخة", type=["png", "jpg", "jpeg", "webp"],
                              key="photo", label_visibility="collapsed")
        if not PHOTO_OK:
            st.warning("مكتبة Pillow غير متوفرة — عطّل قراءة الصور وأدخل الإجابات يدويًا.")

    photo_bytes = None
    if up is not None and PHOTO_OK:
        raw = up.getvalue()
        photo_bytes = img_pipeline(raw, st.session_state.ph_rot, st.session_state.ph_contrast,
                                   st.session_state.ph_bright, st.session_state.ph_gray,
                                   st.session_state.ph_invert)
        with st.container(border=True):
            st.markdown('<div class="rtl"><b>🎛️ أدوات القراءة — تُطبّق فورًا</b></div>',
                        unsafe_allow_html=True)
            t1, t2, t3, t4 = st.columns([1.4, 1.4, 1, 1])
            t1.slider("🔎 التكبير (px)", 320, 1600, 760, 40, key="ph_zoom")
            t2.slider("◐ التباين", 0.5, 2.0, 1.0, 0.05, key="ph_contrast")
            t3.slider("☀ السطوع", 0.5, 2.0, 1.0, 0.05, key="ph_bright")
            t4.toggle("ملء العرض", key="ph_fit")
            b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
            b1.button("⟲ تدوير", on_click=cb_rotate, args=(-90,), key="rot_l")
            b2.button("⟳ تدوير", on_click=cb_rotate, args=(90,), key="rot_r")
            b3.toggle("رمادي", key="ph_gray")
            b4.toggle("عكس الألوان", key="ph_invert")
            b5.button("↺ إعادة الضبط", on_click=cb_photo_reset, key="ph_reset")
            b6.download_button("⬇️ الصورة", data=photo_bytes,
                               file_name="copie_traitee.png", mime="image/png", key="dl_photo")
            if b7.button("🔍 استخراج OCR", disabled=not OCR_OK, key="ocr_btn",
                         help="يتطلب pytesseract + tesseract-ocr"):
                with st.spinner("جارٍ قراءة النص من الصورة..."):
                    txt, bins, decs = run_ocr(raw)
                st.session_state.ocr_text, st.session_state.ocr_bins, st.session_state.ocr_decs = txt, bins, decs
                st.toast("🔍 تم استخراج النص", icon="✅")

    left, right = (st.columns([1.05, 1], gap="large") if photo_bytes else (None, st.container()))

    if photo_bytes:
        with left:
            width = "100%" if st.session_state.ph_fit else f"{st.session_state.ph_zoom}px"
            b64 = base64.b64encode(photo_bytes).decode()
            st.markdown(
                f'<div class="photo-frame"><img src="data:image/png;base64,{b64}" '
                f'style="width:{width}" alt="copie de l\'élève"></div>',
                unsafe_allow_html=True)
            st.caption("🖱️ مرّر داخل الإطار لقراءة كامل النسخة — أشرطة التمرير مصممة بهوية الدفتر.")
            if st.session_state.get("ocr_text") is not None:
                with st.expander("🔍 نص OCR + اقتراحات الأعداد (للمراجعة)"):
                    st.code(st.session_state.ocr_text or "(لا نص مقروء)", language="text")
                    st.markdown('<div class="rtl">اختر عددًا مقترحًا لتعبئة خانة التحويل相对应:</div>',
                                unsafe_allow_html=True)
                    for qid, label, kind, val, exp in EX3_ITEMS:
                        cands = st.session_state.ocr_bins if kind == "bin" else st.session_state.ocr_decs
                        st.selectbox(f"Ex3 ({qid}) — من OCR", ["—"] + cands,
                                     key=f"ocr_pick_{qid}", on_change=cb_pick, args=(qid,))

    with right:
        with st.form("exam"):
            tabs = st.tabs(["📌 ت1 (4ن)", "📌 ت2 (6ن)", "📌 ت3 (4ن)", "📌 ت4 (6ن)"])
            answers = {"ex1": {}, "ex2": {}, "ex3": {}, "ex4": {}}
            with tabs[0]:
                st.markdown("**Cocher la ou les bonnes réponses**")
                for q in EX1_QUESTIONS:
                    st.markdown(f"**{q['prompt']}**")
                    sel = set()
                    for letter, text in q["options"].items():
                        if st.checkbox(f"{letter}) {text}", key=f"ex1_{q['id']}_{letter}"):
                            sel.add(letter)
                    answers["ex1"][q["id"]] = sel
                    st.markdown("---")
            with tabs[1]:
                st.markdown("**Mots proposés :** bits – sens – binaire – donnée – science – vidéo – "
                            "automatique – décimal – information – traitement – octets – hardware")
                for sid, sentence, blanks in EX2_SENTENCES:
                    st.markdown(sentence)
                    cols = st.columns(2)
                    for i, (key, _, _) in enumerate(blanks):
                        answers["ex2"][key] = cols[i].text_input(f"الخانة ({i+1})", key=key)
                    st.markdown("---")
            with tabs[2]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Binaire → Décimal**")
                    for qid, label, kind, val, exp in EX3_ITEMS[:2]:
                        answers["ex3"][qid] = st.text_input(f"{qid}) {label}", key=f"ex3_{qid}",
                                                            placeholder="ex: 44")
                with c2:
                    st.markdown("**Décimal → Binaire**")
                    for qid, label, kind, val, exp in EX3_ITEMS[2:]:
                        answers["ex3"][qid] = st.text_input(f"{qid}) {label}", key=f"ex3_{qid}",
                                                            placeholder="ex: 11100")
            with tabs[3]:
                st.markdown("**Vrai ou Faux ? Corrigez si c'est faux.**")
                for item in EX4_ITEMS:
                    st.markdown(f"**{item['id']}) {item['text']}**")
                    choice = st.radio("choix", ["—", "Vrai", "Faux"], horizontal=True,
                                      key=f"ex4_{item['id']}_choice", label_visibility="collapsed")
                    corr = ""
                    if item["expected"] == "Faux":
                        corr = st.text_area("Correction (si Faux)", key=f"ex4_{item['id']}_corr",
                                            placeholder="صحيح العبارة هنا...")
                    answers["ex4"][item["id"]] = {"choice": choice, "corr": corr}
                    st.markdown("---")
            submitted = st.form_submit_button("✅ تصحيح الورقة")

    if submitted:
        res = grade(answers, st.session_state.set_soft, st.session_state.set_mode)
        st.session_state.last_result = {
            **res, "answers": serialise_answers(answers),
            "name": st.session_state.get("stu_name", ""),
            "classe": st.session_state.get("stu_classe", ""),
            "date": str(st.session_state.get("stu_date", date.today())),
            "settings": {"soft": st.session_state.set_soft, "mode": st.session_state.set_mode}}

    lr = st.session_state.get("last_result")
    if lr:
        st.write("")
        st.markdown('<div class="rtl"><h3>📊 نتيجة التصحيح</h3></div>', unsafe_allow_html=True)
        s = lr["scores"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("التمرين 1", f"{s['ex1']} / 4")
        c2.metric("التمرين 2", f"{s['ex2']} / 6")
        c3.metric("التمرين 3", f"{s['ex3']} / 4")
        c4.metric("التمرين 4", f"{s['ex4']} / 6")
        c5.metric("المجموع", f"{lr['total']} / 20")
        st.progress(lr["total"] / 20)
        msg = f"التقدير: {mention(lr['total'])}"
        st.success(msg) if lr["total"] >= 10 else st.error(msg)
        with st.expander("🔎 تفاصيل التصحيح سؤالًا بسؤال", expanded=True):
            for ex in ("ex1", "ex2", "ex3", "ex4"):
                st.markdown(f"#### {EX_TITLES[ex]}")
                for d in lr["details"]:
                    if d["ex"] != ex:
                        continue
                    icon = "✅" if d["pts"] == d["max"] else ("🟡" if d["pts"] > 0 else "❌")
                    st.markdown(f"{icon} **{d['label']}** — {d['pts']}/{d['max']}")
                    st.caption(f"إجابة الطالب: {d['given']} | الصحيحة: {d['expected']}")
        a1, a2, a3 = st.columns(3)
        a1.button("💾 حفظ في السجل", on_click=cb_save, key="save_rec")
        a2.download_button("⬇️ تقرير TXT", build_report(lr),
                           file_name=f"correction_{(lr['name'] or 'eleve').replace(' ', '_')}.txt",
                           mime="text/plain", key="dl_rep")
        a3.button("🧹 تفريغ النموذج", on_click=cb_reset_form, key="reset_form")


# ============================================================
# 10) صفحة السجل
# ============================================================

@st.dialog("🧾 تفاصيل النسخة", width="large")
def show_detail(rec):
    st.markdown(f'<div class="rtl"><span class="rec-name">{rec["name"]}</span> '
                f'<span class="rec-meta">· {rec["classe"]} · {rec["date"]}</span></div>',
                unsafe_allow_html=True)
    s = rec["scores"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ت1", f"{s['ex1']}/4")
    c2.metric("ت2", f"{s['ex2']}/6")
    c3.metric("ت3", f"{s['ex3']}/4")
    c4.metric("ت4", f"{s['ex4']}/6")
    c5.metric("المجموع", f"{rec['total']}/20")
    st.progress(rec["total"] / 20)
    st.caption(mention(rec["total"]))
    for ex in ("ex1", "ex2", "ex3", "ex4"):
        with st.expander(EX_TITLES[ex]):
            for d in rec["details"]:
                if d["ex"] != ex:
                    continue
                icon = "✅" if d["pts"] == d["max"] else ("🟡" if d["pts"] > 0 else "❌")
                st.markdown(f"{icon} **{d['label']}** — {d['pts']}/{d['max']}")
                st.caption(f"إجابة الطالب: {d['given']} | الصحيحة: {d['expected']}")
    st.download_button("⬇️ تحميل تقرير TXT", build_report(rec),
                       file_name=f"correction_{rec['name'].replace(' ', '_')}.txt",
                       mime="text/plain", key=f"dlg_dl_{rec['id']}")


def page_records():
    st.markdown('<div class="rtl"><h2>🗂️ سجل النتائج</h2></div>', unsafe_allow_html=True)
    recs = st.session_state.records

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 1.2, 1.2, 1.2])
        c1.text_input("🔍 بحث بالاسم", key="f_search", placeholder="اكتب جزءًا من الاسم...")
        classes = ["الكل"] + sorted({r["classe"] for r in recs if r["classe"]})
        c2.selectbox("القسم", classes, key="f_class")
        c3.selectbox("النتيجة", ["الكل", "ناجح (≥10)", "دون المعدل (<10)"], key="f_res")
        c4.selectbox("الفرز", ["الأحدث", "النقطة ↓", "النقطة ↑", "الاسم أ-ي"], key="f_sort")
        v1, v2, v3, v4, v5 = st.columns(5)
        v1.button("الكل", on_click=cb_chip, args=({"f_search": "", "f_class": "الكل", "f_res": "الكل"},), key="vw_all")
        v2.button("الناجحون", on_click=cb_chip, args=({"f_res": "ناجح (≥10)"},), key="vw_pass")
        v3.button("دون المعدل", on_click=cb_chip, args=({"f_res": "دون المعدل (<10)"},), key="vw_fail")
        v4.button("قسم 1AS-1", on_click=cb_chip, args=({"f_class": "1AS-1"},), key="vw_c1")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "name", "classe", "date", "ex1", "ex2", "ex3", "ex4", "total", "mention"])
        for r in recs:
            s = r["scores"]
            w.writerow([r["id"], r["name"], r["classe"], r["date"],
                        s["ex1"], s["ex2"], s["ex3"], s["ex4"], r["total"], mention(r["total"])])
        v5.download_button("⬇️ CSV", buf.getvalue().encode("utf-8-sig"),
                           file_name="resultats.csv", mime="text/csv", key="dl_csv")

    q = norm(st.session_state.get("f_search", ""))
    fc = st.session_state.get("f_class", "الكل")
    fr = st.session_state.get("f_res", "الكل")
    fs = st.session_state.get("f_sort", "الأحدث")
    view = [r for r in recs
            if (not q or q in norm(r["name"]))
            and (fc == "الكل" or r["classe"] == fc)
            and (fr == "الكل" or (fr.startswith("ناجح") and r["total"] >= 10)
                 or (fr.startswith("دون") and r["total"] < 10))]
    if fs == "النقطة ↓":
        view.sort(key=lambda r: -r["total"])
    elif fs == "النقطة ↑":
        view.sort(key=lambda r: r["total"])
    elif fs == "الاسم أ-ي":
        view.sort(key=lambda r: r["name"])
    else:
        view.sort(key=lambda r: r["date"], reverse=True)

    selected = [r["id"] for r in view if st.session_state.get(f"sel_{r['id']}")]
    if selected:
        st.button(f"🗑 حذف المحدد ({len(selected)})", on_click=cb_delete, args=(selected,), key="bulk_del")

    if not view:
        st.info("لا نتائج مطابقة — عدّل البحث أو الفلاتر، أو صحح نسخة جديدة.", icon="🗂️")

    for r in view:
        with st.container(border=True):
            c0, c1, c2, c3 = st.columns([0.4, 3, 1.2, 1.7])
            c0.checkbox(" ", key=f"sel_{r['id']}", label_visibility="collapsed")
            c1.markdown(f'<div class="rtl"><span class="rec-name">{r["name"]}</span><br>'
                        f'<span class="rec-meta">🏫 {r["classe"] or "—"} · 📅 {r["date"]} · '
                        f'{mention(r["total"])}</span></div>', unsafe_allow_html=True)
            cls = "pass" if r["total"] >= 10 else "fail"
            c2.markdown(f'<span class="score-badge {cls}">{r["total"]}/20</span>',
                        unsafe_allow_html=True)
            b1, b2, b3 = c3.columns(3)
            if b1.button("👁", key=f"view_{r['id']}", help="تفاصيل"):
                st.session_state.detail_id = r["id"]
            b2.button("✏️", key=f"edit_{r['id']}", help="فتح في المصحح",
                      on_click=cb_edit, args=(r,))
            b3.button("🗑", key=f"del_{r['id']}", help="حذف (مع تراجع)",
                      on_click=cb_delete, args=([r["id"]],))

    if st.session_state.undo:
        u1, u2 = st.columns([4, 1])
        u1.markdown(f'<div class="undo-bar rtl">⚠️ {len(st.session_state.undo[-1])} نسخة في سلة التراجع</div>',
                    unsafe_allow_html=True)
        u2.button("↩️ تراجع", on_click=cb_undo, key="undo_btn")

    if st.session_state.get("detail_id"):
        rec = next((r for r in recs if r["id"] == st.session_state.detail_id), None)
        st.session_state.detail_id = None
        if rec:
            show_detail(rec)


# ============================================================
# 11) صفحة الورقة والنموذج
# ============================================================

def page_key():
    st.markdown('<div class="rtl"><h2>📖 الورقة الأصلية والتصحيح النموذجي</h2></div>',
                unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### Exercice 1 (4 pts) — Cocher la ou les bonnes réponses")
        for q in EX1_QUESTIONS:
            corr = set(q["correct"])
            if q["id"] == "q4" and not st.session_state.set_soft:
                corr = {"e"}
            st.markdown(f"**{q['prompt']}**")
            for letter, text in q["options"].items():
                mark = "✅" if letter in corr else "⬜"
                st.markdown(f"{mark} {letter}) {text}")
            st.markdown("---")
    with st.container(border=True):
        st.markdown("#### Exercice 2 (6 pts) — Compléter les définitions")
        st.markdown("1) L'informatique est la **science** du traitement automatique de "
                    "**l'information**.")
        st.markdown("2) Information = **donnée** + **sens** (الترتيب حر).")
        st.markdown("3) …sur deux **bits** : 0 et 1 → langage **binaire**.")
    with st.container(border=True):
        st.markdown("#### Exercice 3 (4 pts) — Conversions")
        st.code("(101100)₂ = (44)₁₀      (110101)₂ = (53)₁₀\n"
                "(28)₁₀  = (11100)₂    (65)₁₀  = (1000001)₂", language="text")
    with st.container(border=True):
        st.markdown("#### Exercice 4 (6 pts) — Vrai/Faux + correction")
        st.markdown("✅ a) **Vrai** (2ن)")
        st.markdown("❌ d) **Faux** (1ن) + التصحيح (1ن): *Un système informatique est constitué "
                    "de la partie matérielle (hardware) ET de la partie logicielle (software).*")
        st.markdown("✅ b) **Vrai** (2ن)")
    st.caption("يمكن ضبط قبول « un programme » ونقطة تصحيح Ex4-d من الشريط الجانبي.")


# ============================================================
# 12) التوجيه
# ============================================================

if st.session_state.page == "work":
    page_work()
elif st.session_state.page == "records":
    page_records()
else:
    page_key()

st.markdown('<div class="rtl" style="opacity:.65;margin-top:18px;font-size:.8rem">'
            '🖊️ دفتر التصحيح — أداة محلية للأستاذ · البيانات في corrections_store.json</div>',
            unsafe_allow_html=True)
