import re
import cv2
import numpy as np
import pandas as pd
import streamlit as st

W, H = 1000, 1414   # format interne (ratio A4)
MARK, M = 36, 50    # repères noirs de coins et marge

def layout(n_q, n_opt):
    dy = min(50, (H - 400) // n_q)
    r = int(min(20, dy / 2 - 3))
    return 250, dy, 320, 105, r   # start_y, dy, start_x, dx, rayon

def corner_centers():
    return np.float32([
        [M + MARK/2, M + MARK/2], [W - M - MARK/2, M + MARK/2],
        [M + MARK/2, H - M - MARK/2], [W - M - MARK/2, H - M - MARK/2]])

def make_sheet(n_q, n_opt):
    img = np.full((H, W), 255, np.uint8)
    for x, y in [(M, M), (W-M-MARK, M), (M, H-M-MARK), (W-M-MARK, H-M-MARK)]:
        cv2.rectangle(img, (x, y), (x+MARK, y+MARK), 0, -1)
    cv2.putText(img, "Feuille de reponses - QCM", (150, 160), 0, 1.0, 0, 2)
    cv2.putText(img, "Nom : ____________________________", (150, 205), 0, 0.7, 0, 2)
    sy, dy, sx, dx, r = layout(n_q, n_opt)
    for j in range(n_opt):
        cv2.putText(img, chr(65+j), (sx + j*dx - 8, sy - 40), 0, 0.8, 0, 2)
    for i in range(n_q):
        y = sy + i*dy
        cv2.putText(img, f"{i+1:02d}", (230, y+8), 0, 0.7, 0, 2)
        for j in range(n_opt):
            cv2.circle(img, (sx + j*dx, y), r, 0, 2)
    return img

def find_markers(binary):
    h, w = binary.shape
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if cw < 15 or ch < 15 or not (0.6 < cw/ch < 1.6):
            continue
        if area/(cw*ch) < 0.7 or not (0.00005*w*h < area < 0.01*w*h):
            continue
        cands.append((x + cw/2, y + ch/2))
    src = []
    for cx, cy in [(0, 0), (w, 0), (0, h), (w, h)]:
        if not cands:
            return None
        src.append(min(cands, key=lambda p: (p[0]-cx)**2 + (p[1]-cy)**2))
    if len({(round(x), round(y)) for x, y in src}) < 4:
        return None
    return np.float32(src)

def read_answers(file_bytes, n_q, n_opt, seuil=0.35):
    img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Image illisible")
    binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    src = find_markers(binary)
    if src is None:
        raise ValueError("Reperes de coins introuvables (scan net, feuille entiere ?)")
    mat = cv2.getPerspectiveTransform(src, corner_centers())
    warped = cv2.warpPerspective(binary, mat, (W, H))
    sy, dy, sx, dx, r = layout(n_q, n_opt)
    yy, xx = np.mgrid[0:H, 0:W]
    answers = []
    for i in
