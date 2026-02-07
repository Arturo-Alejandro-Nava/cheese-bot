import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time

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

# --- 1. LIVE TEXT SCRAPER (The Knowledge) ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    # We scrape the critical pages for latest info
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
            # Extract Clean Text
            text = soup.get_text(separator=' ', strip=True)
            combined_text += f"\n--- SOURCE: {url} ---\n{text[:6000]}\n"
        except:
            continue
            
    return combined_text

# --- 2. LIVE PDF DOWNLOADER (The Data) ---
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
        limit = 6 # Scan top 6 docs
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            pdf_bytes = None
            fname = "Doc"
            
            # Simple PDF Finder (Skips Zips to avoid errors)
            if href.endswith('.pdf'):
                try: 
                    pdf_bytes = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                except: continue

            if pdf_bytes:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_bytes)
                
                # Upload to AI for analysis
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                count += 1
        
        # Wait for Google to process files
        ready_files = []
        for f in ai_files:
            attempts = 0
            while f.state.name == "PROCESSING" and attempts < 10:
                time.sleep(1)
                f = genai.get_file(f.name)
                attempts += 1
            if f.state.name == "ACTIVE": ready_files.append(f)
            
        return ready_files

    except: return []

# --- INITIAL LOAD ---
with st.spinner("Syncing Live Website Data & PDF Specs..."):
    web_text = get_website_text()
    knowledge_docs = process_live_pdfs()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    KNOWLEDGE BASE:
    1. **LIVE PDFS (Attached):** Read these visual documents for specific Nutrition numbers, Ingredients, Pack Sizes, and Pallet Configs.
    2. **WEBSITE TEXT (Below):** Use this for contact info, factory location, and about us.
    
    RULES:
    1. **NO IMAGES:** Provide text-only responses. Be descriptive.
    2. **ACCURACY:** Do not hallucinate numbers. Read the PDF tables exactly.
    3. **LINKS:** If the user asks about a topic, provide the specific URL from the website context (e.g. `https://hcmakers.com/quality`).
    4. **CONTACTS:** Use the scraped contact info for emails/phones.
    5. **LANGUAGE:** English or Spanish (Detect User Language).
    6. **SCOPE:** Only answer questions about Nuestro Queso.
    
    LIVE WEBSITE CONTEXT:
    {web_text}
    """
    
    # Send User Q + Live PDFs + Prompt
    payload = [system_prompt] + knowledge_docs + [question]
    
    try:
        return model.generate_content(payload).text
    except Exception as e:
        return "I am updating the database. Please ask again in 10 seconds."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about cheese specs, nutrition, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User Msg
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI Msg
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})