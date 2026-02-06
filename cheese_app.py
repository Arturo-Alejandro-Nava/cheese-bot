import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Nuestro Queso Assistant", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 5])
with col1:
    st.write("🧀")
with col2:
    st.title("Nuestro Queso - Digital Concierge")

# --- THE AUTOMATIC WEB SCRAPER ---
# We use @st.cache_resource so it only scrapes once per hour/session,
# not every time you ask a question (keeps it fast).
@st.cache_resource(ttl=3600) 
def load_live_website_data():
    # THE LIST OF PAGES TO MONITOR
    # (The bot will read these exact pages for updates)
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/category-knowledge/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/"
    ]
    
    combined_text = ""
    
    try:
        for url in urls:
            # Visit the page
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                # Clean the HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get the raw text, remove extra whitespace
                page_text = soup.get_text(separator=' ', strip=True)
                
                # Add to our knowledge bank
                combined_text += f"\n--- SOURCE: {url} ---\n{page_text}\n"
    except Exception as e:
        return f"Error connecting to website: {e}"
        
    return combined_text

# Load the data (Display a small loading spinner initially)
with st.spinner("Syncing with live website data..."):
    website_knowledge = load_live_website_data()

st.success("✅ Connected to HCMakers.com Live Data")

# --- THE CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # Prompt logic
    system_prompt = f"""
    You are the official Customer Service AI for "Nuestro Queso" (Hispanic Cheese Makers).
    
    SOURCE DATA:
    I have scraped the live text from the official website. Use the text below to answer questions.
    
    RULES:
    1. Answer strictly based on the text provided below.
    2. USE EXACT DETAILS: If the text mentions specific award years, factory size (75k sq ft), or contact names, use them.
    3. NAVIGATION: If the information comes from a specific URL (like the products page), provide that link to the user.
    4. TONE: Professional, warm, expert.
    5. LANGUAGE: Answer in the language the user uses (English or Spanish).
    
    WEBSITE DATA START:
    {website_knowledge}
    WEBSITE DATA END
    """
    
    response = model.generate_content([system_prompt, question])
    return response.text

# --- USER INTERFACE ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("How can I help you? / ¿Cómo te puedo ayudar?")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})