# -*- coding: utf-8 -*-
"""
app.py — تطبيق تصحيح ورقة امتحان «الإعلام الآلي» (Informatique) — النقطة من 20
التمرين 1: 4ن | التمرين 2: 6ن | التمرين 3: 4ن | التمرين 4: 6ن

التشغيل:
    pip install streamlit
    streamlit run app.py
"""

import re
import unicodedata
from datetime import date

import streamlit as st

# ============================================================
# 1) أدوات مساعدة
# ============================================================

def norm(txt):
    """توحيد النص: تصغير الحروف، حذف العلامات الفرنسية وأدوات التعريف."""
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
# 2) محتوى الامتحان والتصحيح النموذجي (عدّل من هنا عند الحاجة)
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
     "correct": {"e", "d"}},  # يمكن حصرها في e من الشريط الجانبي
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

# ============================================================
# 3) دالة التصحيح
# ============================================================

def grade(ans, software_accept_program, ex4d_mode):
    scores = {"ex1": 0, "ex2": 0, "ex3": 0, "ex4": 0}
    details = []

    def add(ex, label, given, expected, pts, mx):
        scores[ex] += pts
        details.append({"ex": ex, "label": label, "given": given,
                        "expected": expected, "pts": pts, "max": mx})

    # ---- التمرين 1 : نقطة لكل سؤال (تطابق تام للمجموعة المختارة) ----
    for q in EX1_QUESTIONS:
        correct = set(q["correct"])
        if q["id"] == "q4" and not software_accept_program:
            correct = {"e"}
        given = ans["ex1"][q["id"]]
        pts = 1 if given == correct else 0
        add("ex1", f"Ex1 ({q['id']}) : {q['prompt']}",
            ", ".join(sorted(given)) or "—", ", ".join(sorted(correct)), pts, 1)

    # ---- التمرين 2 : نقطة لكل خانة ----
    for sid, sentence, blanks in EX2_SENTENCES:
        vals = [norm(ans["ex2"][k]) for k, _, _ in blanks]
        if sid == "s2":  # donnée + sens : الترتيب حر بشرط اختلاف الكلمتين
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

    # ---- التمرين 3 : نقطة لكل تحويل ----
    for qid, label, kind, val, exp in EX3_ITEMS:
        raw = ans["ex3"][qid]
        parsed = parse_decimal(raw) if kind == "dec" else parse_binary(raw)
        pts = 1 if parsed is not None and parsed == val else 0
        add("ex3", f"Ex3 ({qid}) {label}", raw or "—", exp, pts, 1)

    # ---- التمرين 4 : نقطتان لكل عبارة ----
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


def build_report(res, student):
    s = res["scores"]
    lines = ["======= تقرير تصحيح امتحان الإعلام الآلي =======",
             f"الطالب: {student.get('name') or '—'}",
             f"القسم: {student.get('classe') or '—'}",
             f"التاريخ: {student.get('date') or '—'}",
             "-" * 45,
             f"التمرين 1: {s['ex1']}/4",
             f"التمرين 2: {s['ex2']}/6",
             f"التمرين 3: {s['ex3']}/4",
             f"التمرين 4: {s['ex4']}/6",
             f"المجموع: {res['total']}/20  ({mention(res['total'])})",
             "-" * 45]
    for d in res["details"]:
        lines.append(f"[{d['pts']}/{d['max']}] {d['label']}")
        lines.append(f"    إجابة الطالب: {d['given']}")
        lines.append(f"    الصحيحة: {d['expected']}")
    return "\n".join(lines)


def reset_all():
    for k in list(st.session_state.keys()):
        if k.startswith(("ex1_", "ex2_", "ex3_", "ex4_")) or k in ("result", "student"):
            del st.session_state[k]


# ============================================================
# 4) واجهة التطبيق
# ============================================================

st.set_page_config(page_title="تصحيح امتحان الإعلام الآلي", page_icon="📝", layout="wide")
st.title("📝 تصحيح امتحان: مبادئ الإعلام الآلي")
st.caption("Examen d'informatique — Correction automatique — Note sur 20")

with st.sidebar:
    st.header("🧑‍🎓 معلومات الطالب")
    name = st.text_input("الاسم واللقب")
    classe = st.text_input("القسم")
    date_exam = st.date_input("تاريخ التصحيح", value=date.today())
    st.header("⚙️ خيارات التصحيح")
    soft_prog = st.checkbox("سؤال software: قبول « un programme » أيضًا", value=True)
    ex4d_mode = st.selectbox("نقطة تصحيح العبارة (Ex4-d)",
                             ["تلقائي (كلمات مفتاحية)", "قبول يدوي", "رفض يدوي"])
    st.info("سلّم التنقيط: 4 + 6 + 4 + 6 = 20 نقطة")

with st.form("exam"):
    tabs = st.tabs(["📌 التمرين 1 (4ن)", "📌 التمرين 2 (6ن)",
                    "📌 التمرين 3 (4ن)", "📌 التمرين 4 (6ن)"])
    answers = {"ex1": {}, "ex2": {}, "ex3": {}, "ex4": {}}

    with tabs[0]:
        st.markdown("**Cocher la ou les bonnes réponses** — ضع علامة على الإجابة/الإجابات الصحيحة")
        for q in EX1_QUESTIONS:
            st.markdown(f"**{q['prompt']}**")
            selected = set()
            for letter, text in q["options"].items():
                if st.checkbox(f"{letter}) {text}", key=f"ex1_{q['id']}_{letter}"):
                    selected.add(letter)
            answers["ex1"][q["id"]] = selected
            st.markdown("---")

    with tabs[1]:
        st.markdown("**Compléter avec les mots proposés :** bits – sens – binaire – donnée – "
                    "science – vidéo – automatique – décimal – information – traitement – octets – hardware")
        for sid, sentence, blanks in EX2_SENTENCES:
            st.markdown(sentence)
            cols = st.columns(2)
            for i, (key, _, _) in enumerate(blanks):
                answers["ex2"][key] = cols[i].text_input(f"الخانة ({i + 1})", key=key)
            st.markdown("---")

    with tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Binaire → Décimal**")
            for qid, label, kind, val, exp in EX3_ITEMS[:2]:
                answers["ex3"][qid] = st.text_input(f"{qid}) {label}", key=f"ex3_{qid}",
                                                    placeholder="décimal, ex: 44")
        with c2:
            st.markdown("**Décimal → Binaire**")
            for qid, label, kind, val, exp in EX3_ITEMS[2:]:
                answers["ex3"][qid] = st.text_input(f"{qid}) {label}", key=f"ex3_{qid}",
                                                    placeholder="binaire, ex: 11100")

    with tabs[3]:
        st.markdown("**Vrai ou Faux ? puis corrigez l'expression si elle est fausse**")
        for item in EX4_ITEMS:
            st.markdown(f"**{item['id']}) {item['text']}**")
            choice = st.radio("الاختيار", ["—", "Vrai", "Faux"], horizontal=True,
                              key=f"ex4_{item['id']}_choice", label_visibility="collapsed")
            corr = ""
            if item["expected"] == "Faux":
                corr = st.text_area("Correction (si Faux)", key=f"ex4_{item['id']}_corr",
                                    placeholder="اكتب تصحيح العبارة هنا...")
            answers["ex4"][item["id"]] = {"choice": choice, "corr": corr}
            st.markdown("---")

    submitted = st.form_submit_button("✅ تصحيح الورقة")

if submitted:
    st.session_state["result"] = grade(answers, soft_prog, ex4d_mode)
    st.session_state["student"] = {"name": name, "classe": classe, "date": str(date_exam)}

# ---- عرض النتائج ----
res = st.session_state.get("result")
if res:
    student = st.session_state.get("student", {})
    st.header("📊 النتيجة")
    if student.get("name"):
        st.write(f"الطالب: **{student['name']}** — القسم: {student.get('classe') or '—'}")
    s = res["scores"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("التمرين 1", f"{s['ex1']} / 4")
    c2.metric("التمرين 2", f"{s['ex2']} / 6")
    c3.metric("التمرين 3", f"{s['ex3']} / 4")
    c4.metric("التمرين 4", f"{s['ex4']} / 6")
    c5.metric("المجموع", f"{res['total']} / 20")
    st.progress(res["total"] / 20)
    msg = f"التقدير: {mention(res['total'])}"
    st.success(msg) if res["total"] >= 10 else st.error(msg)

    with st.expander("🔎 تفاصيل التصحيح سؤالًا بسؤال", expanded=True):
        for ex_key, ex_title in [("ex1", "التمرين 1"), ("ex2", "التمرين 2"),
                                 ("ex3", "التمرين 3"), ("ex4", "التمرين 4")]:
            st.markdown(f"#### {ex_title}")
            for d in res["details"]:
                if d["ex"] != ex_key:
                    continue
                icon = "✅" if d["pts"] == d["max"] else ("🟡" if d["pts"] > 0 else "❌")
                st.markdown(f"{icon} **{d['label']}** — {d['pts']}/{d['max']}")
                st.caption(f"إجابة الطالب: {d['given']} | الصحيحة: {d['expected']}")

    report = build_report(res, student)
    st.download_button("⬇️ تحميل تقرير التصحيح (TXT)", report,
                       file_name=f"correction_{(student.get('name') or 'eleve').replace(' ', '_')}.txt",
                       mime="text/plain")
    st.button("🗑️ تفريغ الإجابات والنتيجة", on_click=reset_all)

with st.expander("📖 التصحيح النموذجي (للمستاذ)"):
    st.markdown("""
- **Ex1 (4 pts)** : f / h / k / e (+d حسب الخيار)
- **Ex2 (6 pts)** : science, information, donnée + sens, bits, binaire
- **Ex3 (4 pts)** : 44 , 53 , 11100 , 1000001
- **Ex4 (6 pts)** : a = Vrai (2ن) ، d = Faux (1ن) + التصحيح (1ن) ، b = Vrai (2ن)
""")
