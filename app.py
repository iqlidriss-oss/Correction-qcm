import streamlit as st
import cv2
import numpy as np
import pandas as pd

st.set_page_config(page_title="Correction QCM", layout="centered")
st.title("📝 Correction QCM - Automatique")
st.write("طلع تصويرة ديال ورقة QCM، ودخل الأجوبة الصحيحة باش يحسب ليك النقطة.")

nb_q = st.number_input("عدد الأسئلة", min_value=1, max_value=50, value=10)
key_text = st.text_input("الأجوبة الصحيحة (مثال: A,B,C,D,A,B...)", value="A,B,C,D,A,B,C,D,A,B")
uploaded = st.file_uploader("طلع تصويرة الورقة", type=["jpg","jpeg","png"])

if uploaded is not None:
    file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    st.image(img, caption="الورقة", use_container_width=True)

    if st.button("صحح"):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bubbles = []
        for c in contours:
            area = cv2.contourArea(c)
            if 200 < area < 5000:
                x, y, w, h = cv2.boundingRect(c)
                aspect = w / float(h)
                if 0.7 < aspect < 1.3:
                    bubbles.append((y, x, w, h))

        bubbles = sorted(bubbles)[:nb_q*4]
        bubbles = sorted(bubbles, key=lambda b: (b[0]//50, b[1]))

        correct_list = [x.strip().upper() for x in key_text.split(",")]
        letters = ["A","B","C","D"]
        results = []
        score = 0

        for i in range(min(nb_q, len(bubbles)//4)):
            group = bubbles[i*4:(i+1)*4]
            group = sorted(group, key=lambda b: b[1])
            best = 0
            best_idx = 0
            for j, (y,x,w,h) in enumerate(group):
                roi = thresh[y:y+h, x:x+w]
                filled = cv2.countNonZero(roi)
                if filled > best:
                    best = filled
                    best_idx = j
            chosen = letters[best_idx] if best > 50 else "-"
            correct = correct_list[i] if i < len(correct_list) else "?"
            ok = (chosen == correct)
            if ok:
                score += 1
            results.append({"السؤال": i+1, "جواب التلميذ": chosen, "الصحيح": correct, "النتيجة": "✅" if ok else "❌"})

        st.success(f"النقطة: {score} / {nb_q}")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
        if len(bubbles) < nb_q*4:
            st.warning(f"لقيت غير {len(bubbles)} فقاعة. جرب تصويرة واضحة ومقادة.")
else:
    st.info("طلع تصويرة باش نبداو.")
