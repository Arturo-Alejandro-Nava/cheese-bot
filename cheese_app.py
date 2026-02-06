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

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo", "logo.jpg", "logo.png", "logo.jpeg"]
    for name in possible_names:
        if os.path.exists(name):
            st.image(name, width=130)
            break
    else:
        st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. THE UNBLOCKABLE IMAGE DOWNLOADER ---
def download_and_show_image(url, caption=""):
    """
    Downloads image on the server-side to bypass Hotlink/CORS protection.
    Acts like a real browser visiting hcmakers.com directly.
    """
    try:
        # These headers trick the server into thinking we are a real user
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }
        
        # Download the image bytes
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            # Create a memory stream so Streamlit can read it
            image_bytes = io.BytesIO(response.content)
            st.image(image_bytes, caption=caption, width=500)
        else:
            # Fallback if really blocked
            st.markdown(f"**Image Available:** [Click here to view]({url})")
            
    except Exception as e:
        # Fallback if connection fails
        st.markdown(f"**Image Link:** [Click here to view]({url})")

# --- 2. OMNI-SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_data():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/"
    ]
    
    site_text = ""
    # HARDCODED URLS (Tested and working)
    available_images = [
        "DESC: Cheese Fries Package | URL: https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
        "DESC: Oaxaca Bites Package | URL: https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
        "DESC: Manufacturing Plant Factory | URL: https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
        "DESC: Factory Inside Production Line | URL: https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "DESC: Quality Lab | URL: https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
        "DESC: Office | URL: https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
        "DESC: Queso Fresco | URL: https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
        "DESC: Cotija | URL: https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png"
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean_text = soup.get_text(" ", strip=True)[:4000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            # Scrape dynamic images
            for img in soup.find_all('img'):
                src = img.get('data-src') or img.get('src')
                alt = img.get('alt', 'Image')
                
                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    # Simple Filter
                    if "uploads" in src and "logo" not in src:
                        available_images.append(f"DESC: {alt} | URL: {src}")
        except: continue

    return site_text, "\n".join(available_images)

# --- 3. DOC VISUALS ---
@st.cache_resource(ttl=3600)
def process_pdf_visuals():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    doc_images = "\n--- DOCUMENTS (Local Preview Files) ---\n"
    
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 6
        for link in links:
            if count >= limit: break
            href = link['href']
            
            # Grab PDFs/Zips
            pdf_bytes = None
            fname = "Doc"
            try:
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                elif href.endswith('.zip'):
                    # Simplify to skip huge zip files for reliability
                    continue
            except: continue

            if pdf_bytes:
                local = f"doc_{count}.pdf"
                with open(local, "wb") as f: f.write(pdf_bytes)
                remote = genai.upload_file(path=local, display_name=fname)
                ai_files.append(remote)
                
                try:
                    doc = fitz.open(local)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images += f"DESC: Sell Sheet {fname} | FILE: {img_path}\n"
                except: pass
                count += 1
        
        # Wait for AI
        active = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE": active.append(f); break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active, doc_images
    except: return [], ""

# --- LOAD DATA ---
with st.spinner("Connecting to Live System..."):
    web_text, web_img_list = get_website_data()
    doc_ai_files, doc_img_list = process_pdf_visuals()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_response(question):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. IMAGE LIST: Verified URLs.
    2. DOC LIST: Local previews.
    3. TEXT & PDFs: Info sources.
    
    RULES:
    1. **FINDING IMAGES**:
       - Scan 'IMAGE LIST' for matching 'DESC' tags (Fuzzy Match).
       - *Example:* If user asks for "Bites" and list has "Oaxaca Bites", use that URL.
       - OUTPUT: `<<<IMG: URL_HERE>>>`
    2. **PLANT vs OFFICE**: Use distinct images.
    3. **LANGUAGE**: English or Spanish.
    4. **ACCURACY**: Do not invent URLs.
    
    IMAGE LIST:
    {web_img_list}
    
    DOC LIST:
    {doc_img_list}
    
    WEBSITE:
    {web_text}
    """
    
    payload = [system_prompt] + doc_ai_files + [question]
    try:
        return model.generate_content(payload).text
    except: return "Retrieving..."

# --- UI RENDERER ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            # Here we render historical images securely too
            download_and_show_image(message["image_url"])
        st.markdown(message["content"])

# NEW CLEANER INPUT
with st.form(key="chat_form"):
    user_input = st.text_input("How can I help you? / ¿Cómo te puedo ayudar?")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Processing request..."):
            raw = get_smart_response(user_input)
            
            # Detect Image Tag
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            if img_match:
                url = img_match.group(1)
                # This uses the SERVER-SIDE downloader to show the image
                download_and_show_image(url) 
                st.session_state.chat_history.append({"role": "assistant", "content": clean, "image_url": url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean})
            
            st.markdown(clean)