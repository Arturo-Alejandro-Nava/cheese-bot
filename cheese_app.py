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

# --- 1. SECURE IMAGE RENDERER ---
def render_secure_image(url_or_path, caption):
    if not url_or_path.startswith("http"):
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)
        return

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/",
            "Accept": "image/*"
        }
        r = requests.get(url_or_path, headers=headers, timeout=5)
        if r.status_code == 200:
            st.image(r.content, caption=caption, width=500)
        else:
            st.markdown(f"**Image:** [View Link]({url_or_path})")
    except:
        st.markdown(f"**Source:** [View]({url_or_path})")

# --- 2. THE "BRUTE FORCE" MEDIA SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_comprehensive_data():
    urls = [
        "https://hcmakers.com/", # Main page (has the slider)
        "https://hcmakers.com/products/",
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/category-knowledge/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/"
    ]
    
    site_text = ""
    found_image_urls = [] # Keep list to deduplicate
    
    # 1. HARDCODED "VIP" IMAGES (In case dynamic scraping misses one)
    vip_images = [
        ("Cheese Plant / Factory Aerial", "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg"),
        ("Cheese Plant / Factory Inside", "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg"),
        ("Quality Lab", "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg"),
        ("Cheese Fries Package", "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png"), 
        ("Oaxaca Bites Package", "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png")
    ]
    
    final_image_list_text = "\n--- EXTENSIVE IMAGE LIBRARY (BRUTE FORCE) ---\n"
    
    # Add VIPs
    for desc, url in vip_images:
        final_image_list_text += f"IMAGE_DESC: {desc} | URL: {url}\n"
        found_image_urls.append(url)

    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            content = r.text
            
            # A. EXTRACT TEXT (Using Soup)
            soup = BeautifulSoup(content, 'html.parser')
            clean_text = soup.get_text(" ", strip=True)[:3000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            # B. EXTRACT *EVERY* IMAGE URL (Regex Pattern Match)
            # This catches images in Scripts, CSS, and Sliders
            # Matches: https://... .png, .jpg, .jpeg, .webp
            pattern = r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)'
            matches = re.findall(pattern, content)
            
            for src in matches:
                # Cleaning
                if '\\' in src: src = src.replace('\\', '') # Fix JSON encoding
                
                # Filter Junk
                lower_src = src.lower()
                if any(x in lower_src for x in ['logo', 'icon', 'svg', 'favicon', 'arrow', 'blank', 'facebook']):
                    continue
                
                # Deduplicate
                if src in found_image_urls: continue
                
                # Infer Description from Filename
                filename = src.split('/')[-1]
                # Format: "hcm_fresco_cheese.png" -> "hcm fresco cheese"
                desc_guess = filename.replace('-', ' ').replace('_', ' ').replace('.png','').replace('.jpg','')
                
                final_image_list_text += f"IMAGE_GUESS: {desc_guess} | URL: {src}\n"
                found_image_urls.append(src)

        except: continue

    return site_text, final_image_list_text

# --- 3. DOCUMENT PROCESSOR ---
@st.cache_resource(ttl=3600)
def process_pdf_visuals():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    doc_images_list = []
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            if count >= 6: break
            href = link['href']
            
            pdf_data = None
            fname = "Doc"
            
            try:
                if href.endswith('.pdf'):
                    pdf_data = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                elif href.endswith('.zip'):
                    # Zips omitted for speed/reliability in image focus
                    continue
            except: continue

            if pdf_data:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_data)
                
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                
                # Thumbnail
                try:
                    doc = fitz.open(local_path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images_list.append(f"IMAGE: PDF SELL SHEET PREVIEW {fname} | FILE: {img_path}")
                except: pass
                count += 1
                
        active_files = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    active_files.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active_files, "\n".join(doc_images_list)
    except: return [], ""

# --- LOAD ---
with st.spinner("Hunting for all site images..."):
    web_text, web_images = get_comprehensive_data()
    doc_files, doc_images = process_pdf_visuals()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_response(question):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. **IMAGE LIBRARY (Below)**: This list contains EVERY image URL found on the website.
    2. **DOCUMENT IMAGES (Below)**: PNG Previews of documents.
    3. **PDFS**: For nutrition/specs.
    4. **WEBSITE TEXT**: For general info.
    
    RULES FOR IMAGES:
    1. **SEARCH HARD**: If the user wants to see "Fries" or "Bites" or "Fresco", SCAN the `IMAGE_GUESS` fields in the library. 
       - Look for filenames like `cheese-fries` or `bites`. 
       - Be fuzzy. `OaxacaBites-web.png` MATCHES "Oaxaca Bites".
    2. **DISPLAY**: Start response with `<<<IMG: URL_HERE>>>`.
    3. **OFFICE vs PLANT**: "Office" should try to find an office/people photo. "Plant" MUST use the aerial/factory photo.
    4. **DOCUMENTS**: If asking for a document view, use the `.png` file.
    
    IMAGE LIBRARY:
    {web_images}
    
    DOCUMENT PREVIEWS:
    {doc_images}
    
    WEBSITE CONTEXT:
    {web_text}
    """
    
    payload = [system_prompt] + doc_files + [question]
    try:
        response = model.generate_content(payload)
        return response.text
    except: return "Retrieving assets..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            render_secure_image(message["image_url"], "Found Asset")
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding visuals..."):
            raw_text = get_smart_response(user_input)
            
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
            clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw_text).strip()
            
            if img_match:
                img_url = img_match.group(1)
                render_secure_image(img_url, "Found Result")
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text, "image_url": img_url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text})
            
            st.markdown(clean_text)