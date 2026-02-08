import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import glob

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers", page_icon="🧀")

# --- HEADER (Styled to match your Screenshot) ---
col1, col2, col3 = st.columns([3, 2, 3])

with col2:
    # 1. Logo
    possible_names = ["logo_new.png", "logo_new.jpg", "logo.jpg", "logo.png", "logo"]
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            break
    else:
        st.write("🧀")

    # 2. CUSTOM TITLE (Matches your font screenshot)
    # Serif font, Uppercase, Letter Spacing, Dark Blue/Grey color
    st.markdown(
        """
        <style>
        .custom-title {
            font-family: "Times New Roman", Times, serif;
            color: #3b4d61; 
            text-align: center;
            font-size: 18px; 
            letter-spacing: 2px;
            line-height: 1.4;
            text-transform: uppercase;
            font-weight: 400;
            margin-top: 10px;
            margin-bottom: 20px;
        }
        </style>
        
        <div class="custom-title">
            Hispanic Cheese Makers<br>
            Nuestro Queso
        </div>
        """, 
        unsafe_allow_html=True
    )

st.markdown("---")

# --- 1. DATA LOADING (Cached) ---
@st.cache_resource(ttl=3600) 
def load_all_data():
    # A. Scrape Website
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    web_text = ""
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean = soup.get_text(' ', strip=True)[:4000]
            web_text += f"\nSOURCE: {url}\nTEXT: {clean}\n"
        except: continue
        
    # B. Load PDFs
    pdfs = []
    local_files = glob.glob("*.pdf")
    for f in local_files:
        try: pdfs.append(genai.upload_file(f))
        except: pass

    return web_text, pdfs

# --- INITIAL LOAD ---
# This spinner runs once on startup
with st.spinner("Initializing System..."):
    live_web_text, ai_pdfs = load_all_data()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous chat messages
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- INPUT & RESPONSE ---
if prompt := st.chat_input("How can I help you? / ¿Cómo te puedo ayudar?"):
    
    # 1. Show User Text
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # 2. Generate Response
    with st.chat_message("assistant"):
        # Shows "Thinking..." text/spinner briefly before streaming starts
        with st.spinner("Thinking..."):
            
            system_prompt = f"""
            You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
            
            RULES:
            1. **VIDEO/TRENDS LINKS**: 
               - ONLY provide the "Category Knowledge" link (https://hcmakers.com/category-knowledge/) IF the user explicitly asks for **videos**, **market trends**, or **visual insights**.
            
            2. **SPECS**: Use the PDF tables for numbers (Protein, Pack sizes).
            3. **CONTACT**: Plant: Kent, IL (847-258-0375).
            4. **NO IMAGES**: Text descriptions only.
            5. **LANG**: English or Spanish.
            
            WEBSITE CONTEXT:
            {live_web_text}
            """
            
            payload = [system_prompt] + ai_pdfs + [prompt]
            
            try:
                # 3. STREAM THE RESPONSE (The "Fast" part)
                stream = model.generate_content(payload, stream=True)
                
                # 4. DATA CLEANER (The "Fix Error" part)
                # We pull just the words out of the raw stream to prevent crashes
                def stream_text_generator():
                    for chunk in stream:
                        if chunk.text:
                            yield chunk.text

                # 5. PRINT TO SCREEN
                response = st.write_stream(stream_text_generator)
                
                # 6. SAVE TO MEMORY
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                
            except:
                st.error("Connection refreshing... please try again.")