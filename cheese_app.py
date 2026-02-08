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

# --- HEADER ---
# [1, 10, 1] gives the middle column LOTS of space so text doesn't wrap 
col1, col2, col3 = st.columns([1, 10, 1])

with col2:
    # 1. CENTERED LOGO
    # We use a nested column to shrink the logo so it isn't giant
    sub_col1, sub_col2, sub_col3 = st.columns([2, 1, 2])
    with sub_col2:
        possible_names = ["logo_new.png", "logo_new.jpg", "logo.jpg", "logo.png", "logo"]
        for p in possible_names:
            if os.path.exists(p):
                st.image(p, use_container_width=True)
                break
        else:
            st.write("🧀")

    # 2. TWO-LINE ELEGANT TITLE (Matching Screenshot Font)
    st.markdown(
        """
        <style>
        .header-text {
            font-family: 'Times New Roman', serif;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 3px;
            line-height: 1.5;
            color: #FFFFFF; /* White/Light Grey to show on dark mode */
        }
        .line-one {
            font-size: 26px; /* Slightly larger */
            font-weight: 300;
        }
        .line-two {
            font-size: 26px;
            font-weight: 300;
        }
        </style>
        
        <div class="header-text">
            <div class="line-one">Hispanic Cheese Makers</div>
            <div class="line-two">Nuestro Queso</div>
        </div>
        """, 
        unsafe_allow_html=True
    )

st.markdown("---")

# --- 1. DATA LOADING (Cached) ---
@st.cache_resource(ttl=3600) 
def load_all_data():
    # A. Live Scrape
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
with st.spinner("System initializing..."):
    live_web_text, ai_pdfs = load_all_data()

# --- CHAT INTERFACE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input at the bottom
if prompt := st.chat_input("How can I help you? / ¿Cómo te puedo ayudar?"):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        # The spinner ensures it says "Thinking" while connecting
        with st.spinner("Thinking..."):
            system_prompt = f"""
            You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
            
            RULES:
            1. **VIDEO REQUESTS**: IF asked for video/visuals, Reply EXACTLY: 
               "You can watch our trend videos and category insights on our Knowledge Hub: https://hcmakers.com/category-knowledge/"
               (Do not link videos directly, send them to the Hub).
            
            2. **DATA**: Use the PDF tables for specific numbers (Protein, Specs).
            3. **CONTACT**: Plant is in Kent, IL.
            4. **NO IMAGES**: Text only.
            5. **LANG**: English or Spanish.
            
            WEBSITE CONTEXT:
            {live_web_text}
            """
            
            payload = [system_prompt] + ai_pdfs + [prompt]
            
            try:
                # Get the Stream
                stream = model.generate_content(payload, stream=True)
                
                # Filter Text Only
                def text_stream():
                    for chunk in stream:
                        if chunk.text:
                            yield chunk.text

                # Write it live
                response = st.write_stream(text_stream)
                
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            except:
                st.error("Just a moment, re-connecting...")