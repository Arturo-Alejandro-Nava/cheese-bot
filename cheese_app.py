import streamlit as st
import google.generativeai as genai
import os

# --- CONFIGURATION ---
# 1. This grabs the key securely from the Cloud Safe (Streamlit Secrets)
API_KEY = st.secrets["GOOGLE_API_KEY"]

# 2. Connect to the Vision-Enabled "Gemini 2.0" Engine
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- THE WEBPAGE LAYOUT ---
st.set_page_config(page_title="Nuestro Queso Sales Assistant", page_icon="🧀")

st.title("🧀 Nuestro Queso - 24/7 Virtual Sales Rep")
st.write("Upload a Product Catalog, Spec Sheet, or Sell Sheet.")

# --- STEP 1: UPLOAD HANDLER ---
# Food companies use images/PDFs heavily, so we allow both.
uploaded_file = st.file_uploader("Upload Catalog/Sell Sheet", type=["pdf", "png", "jpg", "jpeg"])

# Check if a file is uploaded
if uploaded_file is not None:
    
    # --- STEP 2: HANDLE THE FILE ---
    # We save the file securely to a temp folder so the AI can "Look" at it.
    with open("temp_product_catalog.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.success("✅ Product Data Loaded. Ready for inquiries.")

    # --- STEP 3: THE CHAT FORM (Supports 'Enter' Key) ---
    with st.form(key='chat_form'):
        user_question = st.text_input("Ask a question about our cheeses, specs, or pairings:")
        submit_button = st.form_submit_button("Ask Sales Rep")

    if submit_button:
        if user_question:
            try:
                with st.spinner("Consulting the cheesemonger..."):
                    
                    # 1. Upload the file to Google's Enterprise Brain
                    sample_file = genai.upload_file(path="temp_product_catalog.pdf", display_name="Cheese Catalog")
                    
                    # 2. DEFINE THE CHEESE EXPERT BRAIN
                    system_prompt = """
                    You are a Senior Sales Representative for "Nuestro Queso" (Hispanic Cheese Makers).
                    The user has uploaded a product catalog or Sell Sheet.
                    
                    YOUR GOAL: Educate the buyer and recommend the perfect cheese from the document.
                    
                    RULES:
                    1. Answer strictly based on the text/images in the provided document.
                    2. PRODUCT MATCHING:
                       - If they ask for MELTING: Recommend Oaxaca (The "Mexican String Cheese").
                       - If they ask for GRILLING/FRYING: Recommend Panela or Queso Blanco (Mention they do not melt).
                       - If they ask for TOPPING/SALTY: Recommend Cotija (The "Parmesan of Mexico").
                    3. ALWAYS mention specific awards (like "Gold Medal Winner") if the text mentions them.
                    4. Check for Specs: If asked about pack sizes, ingredients, or allergens, be precise.
                    5. Tone: Helpful, professional, and proud of the quality (SQF Level 3 Plant).
                    6. If the info is not in the file, say: "I'd check with our sales team directly at sales@hcmakers.com just to be sure."
                    """
                    
                    # 3. Ask the Question
                    response = model.generate_content([system_prompt, sample_file, user_question])
                    
                    # 4. Display Result
                    st.write("### 🧀 Sales Rep Answer:")
                    st.write(response.text)
                    
            except Exception as e:
                st.error(f"System Error: {e}")
        else:
            st.warning("Please type a question first.")