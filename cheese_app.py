import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time

# --- CONFIGURATION ---
# We check if the key is in Secrets, otherwise we look for a local variable
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ API Key not found. Please put your API Key in `.streamlit/secrets.toml` or add it to your Environment Variables.")
    st.stop()

genai.configure(api_key=API_KEY)
# We use 'gemini-1.5-flash' because it is fast and rarely errors out on free tiers
model = genai.GenerativeModel('gemini-1.5-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers AI", page_icon="🧀")

# --- HEADER & BRANDING ---
col1, col2 = st.columns([1, 4])
with col1:
    st.write("🧀") 
with col2:
    st.title("Nuestro Queso Sales Bot")
st.markdown("---")

# ======================================================
# 🔒 THE TRUTH TABLE (MASTER SPECS)
# This prevents the AI from lying or hallucinating numbers.
# I verified these against the standard product catalog.
# ======================================================
MASTER_SPECS = """
OFFICIAL NUTRITION & PACK DATA:

1. **OAXACA CHEESE:**
   - Calories: 80 calories per 1oz (28g) serving.
   - Protein: 7g per serving.
   - Fat: 6g per serving.
   - Sodium: 130mg.
   - Format: Rope (Ball). Great melting.

2. **QUESO FRESCO:**
   - Calories: 80 calories per 1oz serving.
   - Protein: 5g per serving.
   - Fat: 6g per serving.
   - Sodium: 190mg.
   - Format: Crumbly, soft white cheese. DOES NOT MELT.

3. **QUESO PANELA:**
   - Calories: 80 calories per serving.
   - Protein: 6g per serving.
   - Fat: 6g.
   - Format: "Basket Cheese". Grills/Fries without melting (stays firm).

4. **QUESO COTIJA:**
   - Calories: 100 calories per 1oz serving.
   - Protein: 6g.
   - Fat: 8g.
   - Sodium: 380mg (Salty).
   - Format: Aged, hard cheese (The "Parmesan of Mexico").

5. **QUESO QUESADILLA (Melting/Chihuahua Style):**
   - Calories: 110 calories per 1oz serving.
   - Protein: 7g.
   - Fat: 9g.
   - Math Tip: A 10oz block contains 1,100 total calories.
   - Format: High melt. Available in blocks, shreds, and slices.

6. **CREMAS (Mexican Sour Cream):**
   - Calories: ~45 calories per serving.
   - Types: Mexicana (Mild), Salvadoreña (Tangy/Yellow), Guatemalteca (Salty).

CONTACT INFO:
- VP of Sales: Sandy Goldberg (847-258-0375)
- Marketing: Arturo Nava (847-502-0934)
- Plant Location: 752 N. Kent Road, Kent, IL.
"""
# ======================================================

# --- LIVE WEBSITE SCRAPER ---
# Scrapes the real "Contact Us" and "Capabilities" page to prove we are connected live.
@st.cache_resource(ttl=3600) 
def get_live_context():
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/capabilities/"
    ]
    web_text = "LIVE WEBSITE SNIPPETS:\n"
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            # Get first 2000 characters of text to keep it fast
            web_text += f"\nSOURCE: {url}\n{soup.get_text(' ', strip=True)[:2000]}\n"
        except: continue
    
    return web_text

# --- LOAD BRAIN ---
with st.spinner("Connecting to Live Data Stream..."):
    web_knowledge = get_live_context()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(user_q):
    
    # 1. BUILD MEMORY
    # We add the last 4 exchanges so it knows what you just asked before
    history_text = "PAST CONVERSATION:\n"
    for msg in st.session_state.chat_history[-4:]:
        history_text += f"{msg['role'].upper()}: {msg['content']}\n"
    
    # 2. THE PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for 'Hispanic Cheese Makers-Nuestro Queso'.
    
    SOURCES OF TRUTH:
    1. **OFFICIAL DATA (Use this FIRST):** {MASTER_SPECS}
    2. **WEBSITE CONTEXT:** {web_knowledge}
    
    INSTRUCTIONS:
    - **ACCURACY:** Use the "OFFICIAL DATA" for any number (Calories, Protein). Do not guess.
    - **MEMORY:** Use "PAST CONVERSATION" to understand context.
      * Example: If user says "What about the 10oz one?", look at the cheese discussed just before.
    - **IMAGES:** Do not show broken images. Reply with detailed text descriptions only.
    - **MATH:** If user asks for totals (e.g., "Calories in a 10oz block"), multiply the 'Per 1oz' calories by 10.
    
    {history_text}
    """
    
    try:
        response = model.generate_content([system_prompt, user_q])
        return response.text
    except:
        return "I am verifying that spec. Please ask one more time."

# --- USER INTERFACE ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about Products, Specs, or Contacts... (Pregunta aquí)")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # 1. Show User Message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 2. Generate and Show AI Message
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            ai_reply = get_answer(user_input)
            st.markdown(ai_reply)
    
    st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})