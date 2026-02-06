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

# --- 1. BYPASS IMAGE RENDERER (The Fix) ---
def render_image(url_or_path, caption):
    # A. Local File (PDF Screenshot) - Use Standard Streamlit
    if not url_or_path.startswith("http"):
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)
        return

    # B. Web URL - Use HTML Injection (Forces User Browser to Load It)
    # This bypasses server-side 403 blocking
    st.markdown(
        f"""
        <div style="text-align: left;">
            <img src="{url_or_path}" alt="{caption}" width="500" style="border-radius: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.1);">
            <p style="font-size: 14px; color: gray; margin-top: 5px;">{caption}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. OMNI-SCRAPER (Images + Text) ---
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
    # HARDCODED VIPS (We explicitly add these so they are never missed)
    available_images = [
        "DESC: Cheese Fries Package / Ready to Fry | URL: https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
        "DESC: Oaxaca Bites Package / Snacks | URL: https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
        "DESC: Manufacturing Plant Factory Aerial | URL: https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
        "DESC: Inside Factory / Production Line | URL: https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "DESC: Quality Lab | URL: https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
        "DESC: Office Headquarters Map Location | URL: https://hcmakers.com/wp-content/uploads/2020/08/display.jpg" # Fallback office img
    ]
    
    seen = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # TEXT
            clean_text = soup.get_text(" ", strip=True)[:4000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            # IMAGES (Regex to find hidden ones)
            content_str = str(r.content)
            # Find anything ending in image extensions
            pattern = r'https?://[^"\s\'>]+\.(?:png|jpg|jpeg|webp)'
            matches = re.findall(pattern, content_str)
            
            for src in matches:
                # Cleaning
                if '\\' in src: src = src.replace('\\', '')
                if src in seen: continue
                
                # Filter Junk
                if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'spacer', 'facebook', 'twitter', 'blank']): continue
                
                # Attempt to guess description from filename
                fname = src.split('/')[-1]
                desc_guess = fname.replace('-', ' ').replace('_', ' ').replace('.png', '').replace('.jpg', '')
                
                available_images.append(f"DESC: {desc_guess} | URL: {src}")
                seen.append(src)
        except: continue

    return site_text, "\n".join(available_images)

# --- 3. DOCUMENT VISUALS ---
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
            
            # Logic for Direct PDF or Zip extraction (same as before)
            pdf_bytes = None
            fname = "Doc"
            try:
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                elif href.endswith('.zip'):
                    # Omitted deep zip logic to keep script reliable/fast for images
                    continue 
            except: continue

            if pdf_bytes:
                local = f"doc_{count}.pdf"
                with open(local, "wb") as f: f.write(pdf_bytes)
                
                # AI Upload
                remote = genai.upload_file(path=local, display_name=fname)
                ai_files.append(remote)
                
                # Visual Preview (PyMuPDF)
                try:
                    doc = fitz.open(local)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images += f"DESC: Sell Sheet for {fname} | FILE: {img_path}\n"
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
with st.spinner("Syncing Visual Library..."):
    web_text, web_img_list = get_website_data()
    doc_ai_files, doc_img_list = process_pdf_visuals()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_response(question):
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. IMAGE LIST (Below): Valid URLs for products (Fries, Bites, Fresco) and Facilities.
    2. DOC LIST (Below): Local png previews for sell sheets.
    3. WEB TEXT: For facts.
    4. PDFS: Attached for data.
    
    RULES:
    1. **FIND THE IMAGE**: If asked to see something (e.g. "Cheese Fries", "Bites"), SEARCH the IMAGE LIST. 
       - Fuzzy match: If filename is `CheeseFries-web.png`, match it to "Cheese Fries".
       - Output tag: `<<<IMG: URL_HERE>>>`
    
    2. **PLANT vs OFFICE**: 
       - Plant/Factory = Manufacturing images (aerial or inside).
       - Office = Corporate images.
    
    3. **SELL SHEETS**: Use the local FILE path (e.g. `<<<IMG: preview_0.png>>>`) if they want to see the document.
    
    4. **ACCURACY**: Do not make up links. Only use what is listed.
    
    IMAGE LIST:
    {web_img_list}
    {doc_img_list}
    
    WEB CONTEXT:
    {web_text}
    """
    
    payload = [system_prompt] + doc_ai_files + [question]
    try:
        return model.generate_content(payload).text
    except: return "Retrieving..."

# --- UI RENDERER ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        # Show image if saved in history
        if "image_url" in message:
            render_image(message["image_url"], "Found")
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about cheese fries, bites, or factory...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Locating..."):
            raw = get_smart_response(user_input)
            
            # Parse special image tag
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            if img_match:
                url = img_match.group(1)
                render_image(url, "Result")
                st.session_state.chat_history.append({"role": "assistant", "content": clean, "image_url": url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean})
            
            st.markdown(clean)