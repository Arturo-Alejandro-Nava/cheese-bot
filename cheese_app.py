import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # PyMuPDF
import re

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.set_page_config(page_title="Nuestro Queso", page_icon="🧀")

# HEADER
col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=140)
    else:
        st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers - Nuestro Queso")

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# UNBLOCKABLE IMAGE DOWNLOADER (server-side)
# ─────────────────────────────────────────────────────────────
def show_image(url, caption=""):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://hcmakers.com/"
        }
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            st.image(io.BytesIO(r.content), caption=caption, width=550)
        else:
            st.markdown(f"[View image]({url})")
    except:
        st.markdown(f"[View image]({url})")

# ─────────────────────────────────────────────────────────────
# LIVE SCRAPER + HARDCODED RELIABLE IMAGES
# ─────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def get_assets():
    # Guaranteed working images (tested today)
    reliable_images = {
        "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
        "FACTORY_INSIDE": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
        "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
        "OAXACA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
        "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
        "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png"
    }

    # Build text library for AI
    image_library = "\n".join([f"DESC: {k} | URL: {v}" for k, v in reliable_images.items()])
    
    # Scrape website text (for specs, contacts, etc.)
    urls = ["https://hcmakers.com/products/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/contact-us/"]
    text = ""
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.content, 'html.parser')
            text += soup.get_text(" ", strip=True)[:3000]
        except:
            pass
    return image_library, text

image_library, website_text = get_assets()

# ─────────────────────────────────────────────────────────────
# PDF SELL SHEETS (Vision)
# ─────────────────────────────────────────────────────────────
@st.cache_resource(ttl=3600)
def get_sell_sheets():
    ai_files = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        for i, link in enumerate(links[:4]):  # max 4 PDFs
            try:
                data = requests.get(link).content
                fname = f"doc_{i}.pdf"
                with open(fname, "wb") as f:
                    f.write(data)
                remote = genai.upload_file(fname)
                while remote.state.name == "PROCESSING":
                    time.sleep(1)
                    remote = genai.get_file(remote.name)
                ai_files.append(remote)
            except:
                continue
        return ai_files
    except:
        return []

pdf_files = get_sell_sheets()

# ─────────────────────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        if "image" in msg:
            show_image(msg["image"], msg.get("caption", ""))
        st.markdown(msg["content"])

user_input = st.chat_input("Ask about products, nutrition, the plant, or sell sheets...")

if user_input:
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Consulting the cheesemonger..."):
            system_prompt = f"""
            You are the official bilingual sales rep for Nuestro Queso.
            Use ONLY the data below. Never guess.

            IMAGE LIBRARY (use these exact URLs):
            {image_library}

            WEBSITE TEXT:
            {website_text}

            RULES:
            - If the user asks to SEE something (plant, fresco, sell sheet, etc.), reply with exactly this tag: <<<IMG: URL_HERE>>>
            - Then explain in normal text.
            - Answer in the language the user used.
            """

            response = model.generate_content([system_prompt] + pdf_files + [user_input])
            raw = response.text

            # Parse image tag
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()

            if match:
                url = match.group(1).strip()
                show_image(url, "Requested image")
                st.session_state.history.append({
                    "role": "assistant",
                    "content": clean_text,
                    "image": url,
                    "caption": "Requested image"
                })
            else:
                st.session_state.history.append({"role": "assistant", "content": clean_text})

            st.markdown(clean_text)