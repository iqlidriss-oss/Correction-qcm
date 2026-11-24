import streamlit as st
import pandas as pd

st.set_page_config(page_title="Correction Examen Info", layout="centered")
st.title("📝 Correction - Examen Informatique")
st.write("1ère Année Collège - La science informatique")
st.divider()

if "results" not in st.session_state:
    st.session_state.results = []

nom = st.text_input("اسم التلميذ / Nom de l'élève")
classe = st.selectbox("القسم / Classe", ["1AC1", "1AC2", "1AC3", "1AC4", "1AC5", "1AC6", "Autre"])

st.subheader("Exercice 1 (4 pts) - Cocher la bonne réponse")
ex1_q1 = st.checkbox("1. Schéma: Donnée -> Traitement -> Résultat")
ex1_q2 = st.checkbox("2. Informatique = Information + automatique")
ex1_q3 = st.checkbox("3. Traitement automatique = effectué par la machine")
ex1_q4 = st.checkbox("4. Software = la partie logicielle")

st.subheader("Exercice 2 (6 pts) - Compléter")
ex2_q1 = st.selectbox("1. L'informatique est la science du traitement automatique de l'information", ["0 - غلط", "1 - نصف صحيح", "2 - صحيح"])
ex2_q2 = st.selectbox("2. Information = donnée + sens", ["0 - غلط", "1 - نصف صحيح", "2 - صحيح"])
ex2_q3 = st.selectbox("3. Langage basé sur deux bits / langage binaire", ["0 - غلط", "1 - نصف صحيح", "2 - صحيح"])

st.subheader("Exercice 3 (4 pts) - Conversion")
ex3_q1 = st.checkbox("1. (101100)₂ = 44₁₀")
ex3_q2 = st.checkbox("2. (110101)₂ = 53₁₀")
ex3_q3 = st.checkbox("3. (28)₁₀ = (11100)₂")
ex3_q4 = st.checkbox("4. (65)₁₀ = (1000001)₂")

st.subheader("Exercice 4 (6 pts) - Vrai / Faux")
ex4_q1 = st.checkbox("a) Information = donnée ayant un sens -> Vrai (2 pts)")
ex4_q2 = st.checkbox("d) Système = uniquement logicielle -> Faux (2 pts)")
ex4_q3 = st.checkbox("b) Informations peuvent être sous forme texte -> Vrai (2 pts)")

if st.button("✅ احسب النقطة / Calculer", type="primary"):
    if not nom:
        st.warning("كتب اسم التلميذ عاد كليكي")
    else:
        note_ex1 = sum([ex1_q1, ex1_q2, ex1_q3, ex1_q4]) * 1
        note_ex2 = int(ex2_q1[0]) + int(ex2_q2[0]) + int(ex2_q3[0])
        note_ex3 = sum([ex3_q1, ex3_q2, ex3_q3, ex3_q4]) * 1
        note_ex4 = sum([ex4_q1, ex4_q2, ex4_q3]) * 2
        total = note_ex1 + note_ex2 + note_ex3 + note_ex4

        st.success(f"النقطة ديال {nom} : {total} / 20")
        st.write(f"Ex1: {note_ex1}/4 | Ex2: {note_ex2}/6 | Ex3: {note_ex3}/4 | Ex4: {note_ex4}/6")

        st.session_state.results.append({
            "Nom": nom,
            "Classe": classe,
            "Ex1 /4": note_ex1,
            "Ex2 /6": note_ex2,
            "Ex3 /4": note_ex3,
            "Ex4 /6": note_ex4,
            "Total /20": total
        })
        st.rerun()

st.divider()
st.subheader("📋 لائحة التلاميذ المصححين")

if len(st.session_state.results) > 0:
    df = pd.DataFrame(st.session_state.results)
    st.dataframe(df, use_container_width=True)
    st.write(f"عدد التلاميذ: {len(df)} | المعدل: {df['Total /20'].mean():.2f} / 20")
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 تحميل Excel / CSV", csv, "notes.csv", "text/csv")
    if st.button("🗑️ مسح الكل"):
        st.session_state.results = []
        st.rerun()
else:
    st.info("مازال ما صححتي حتى واحد. بدا بأول تلميذ.")
