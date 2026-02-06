import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import re

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.set_page_config(page_title="Nuestro Queso", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    # Looks for any logo variant
    possible = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130)
            found = True
            break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. UNBLOCKABLE IMAGE DOWNLOADER (The Logic Fix) ---
def show_image(url, caption=""):
    """
    Downloads image on server to bypass browser security blocks.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        # Force a fresh download with timeout
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            st.image(io.BytesIO(r.content), caption=caption, width=500)
        else:
            # Clickable fallback
            st.markdown(f"**Image:** [Click to View]({url})")
    except:
        st.markdown(f"**Link:** [View Image]({url})")

# --- 2. ASSET BUILDER ---
@st.cache_resource(ttl=3600)
def get_assets():
    # 1. HARDCODED IMAGES (Guaranteed to work)
    reliable_images = {
        "PLANT / FACTORY (Aerial)": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
        "PLANT / FACTORY (Inside)": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "OFFICE / HQ (Map)": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
        "QUALITY LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
        "OAXACA BITES PACKAGE": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
        "CHEESE FRIES PACKAGE": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
        "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
        "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
        "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
        "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png"
    }

    # Format text for AI
    image_library = "--- IMAGE LIBRARY ---\n"
    for k, v in reliable_images.items():
        image_library += f"DESC: {k} | URL: {v}\n"
    
    # 2. Scrape Text
    urls = ["https://hcmakers.com/products/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/about-us/"]
    text = "--- WEBSITE TEXT ---\n"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean = soup.get_text(" ", strip=True)[:3000]
            text += f"SOURCE: {u}\nCONTENT: {clean}\n"
        except: pass
        
    return image_library, text

# --- 3. PDF HANDLER ---
@st.cache_resource(ttl=3600)
def get_sell_sheets():
    ai_files = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Grab first 4 PDFs or Zip contents
        links = [a['href'] for a in soup.find_all('a', href=True)]
        count = 0
        
        for link in links:
            if count >= 4: break
            if link.endswith('.pdf'):
                data = requests.get(link).content
                fname = f"doc_{count}.pdf"
                with open(fname, "wb") as f: f.write(data)
                
                remote = genai.upload_file(fname)
                ai_files.append(remote)
                count += 1
                
        # Wait for AI
        ready = []
        for f in ai_files:
            while f.state.name == "PROCESSING":
                time.sleep(1)
                f = genai.get_file(f.name)
            if f.state.name == "ACTIVE": ready.append(f)
        return ready
    except: return []

# --- INITIALIZATION ---
image_lib, web_txt = get_assets()
pdf_docs = get_sell_sheets()

# --- CHAT LOOP ---
if "history" not in st.session_state:
    st.session_state.history = []

# Display History
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        if "image" in msg:
            show_image(msg["image"]) # Displays securely
        st.markdown(msg["content"])

# User Input (Modern Chat Bar)
user_input = st.chat_input("Ask about cheese, specs, images, or documents...")

if user_input:
    # 1. User
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. AI
    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            system_prompt = f"""
            You are the Bilingual Sales AI for "Nuestro Queso".
            
            ASSETS:
            {image_lib}
            
            RULES:
            1. **IMAGES:** If user asks to SEE something (Bites, Fries, Plant, Office), you MUST use the EXACT URL from the IMAGE LIBRARY above.
               - Format your response start with: `<<<IMG: URL_HERE>>>`
               - "Office" = Use 'OFFICE / HQ (Map)' image.
               - "Plant" = Use 'PLANT' or 'FACTORY' image.
            
            2. **DOCS:** Use attached PDFs for numbers.
            3. **LANGUAGE:** English or Spanish.
            
            WEBSITE TEXT:
            {web_txt}
            """
            
            # Send to Brain
            payload = [system_prompt] + pdf_docs + [user_input]
            try:
                response = model.generate_content(payload)
                raw_text = response.text
                
                # Check for Image Tag
                match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
                clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw_text).strip()
                
                if match:
                    url = match.group(1)
                    show_image(url) # Render immediately
                    st.session_state.history.append({
                        "role": "assistant",
                        "content": clean_text,
                        "image": url
                    })
                else:
                    st.session_state.history.append({
                        "role": "assistant", 
                        "content": clean_text
                    })
                
                st.markdown(clean_text)
                
            except:
                st.error("Connection reset. Please try again.")