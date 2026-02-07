import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import io
import zipfile

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
    possible = ["logo.jpg", "logo.png", "logo.jpeg"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",   
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    combined_text = "LIVE WEBSITE TEXT CONTENT:\n"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            resp = requests.get(url, headers=headers)
            soup = BeautifulSoup(resp.content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            combined_text += f"\n--- SOURCE: {url} ---\n{text[:6000]}\n"
        except: continue  
    return combined_text

# --- 2. LIVE PDF DOWNLOADER (Scrapes Zips & PDFs) ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 6 
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            pdf_bytes = None
            fname = "Doc"
            
            # Direct PDF
            if href.endswith('.pdf'):
                try: 
                    pdf_bytes = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                except: continue
            # Unzip Strategy
            elif href.endswith('.zip'):
                try:
                    z_data = requests.get(href, headers=headers).content
                    with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                        for f in z.namelist():
                            if f.endswith('.pdf'):
                                pdf_bytes = z.read(f)
                                fname = f
                                break
                except: continue

            if pdf_bytes:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_bytes)
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                count += 1
        
        ready_files = []
        for f in ai_files:
            attempts = 0
            while f.state.name == "PROCESSING" and attempts < 10:
                time.sleep(1); f = genai.get_file(f.name); attempts += 1
            if f.state.name == "ACTIVE": ready_files.append(f)
            
        return ready_files
    except: return []

# --- INITIAL LOAD ---
with st.spinner("Accessing Database & Sell Sheets..."):
    web_text = get_website_text()
    knowledge_docs = process_live_pdfs()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    KNOWLEDGE BASE:
    1. **VISUAL SELL SHEETS (Attached PDF files):** These contain the Nutrition Facts Tables.
    2. **WEBSITE TEXT (Below):** For contact info and factory details.
    
    CRITICAL BEHAVIOR RULES:
    1. **ANSWER IMMEDIATELY:** If asked about Protein, Fat, or Calories, look at ANY of the attached PDF tables.
       - **DO NOT** ask the user which "Pack Size" (e.g. 5lb vs 10oz).
       - Nutrition facts per serving (1oz) are usually the same across all packs.
       - JUST READ THE NUMBER from the first Fresco document you find.
       
    2. **NO "I DON'T KNOW":** You have the files attached. Search them. The info IS there.
       
    3. **LINKS:** Provide direct URLs to website sections if relevant.
    4. **LANGUAGE:** English or Spanish (Detect User Language).
    5. **SCOPE:** Only answer questions about Our Products.
    
    LIVE WEBSITE CONTEXT:
    {web_text}
    """
    
    payload = [system_prompt] + knowledge_docs + [question]
    try:
        return model.generate_content(payload).text
    except Exception as e:
        return "I am re-reading the Sell Sheets. Please ask again in 5 seconds."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about specifications, nutrition, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User Msg
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI Msg
    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})