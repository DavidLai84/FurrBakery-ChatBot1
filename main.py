import os
import sys
import pandas as pd
from flask import Flask, render_template_string, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURATION FROM RENDER ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
MY_PHONE_NUMBER = os.environ.get("MY_PHONE_NUMBER")

# NEW: Get Model Name from Environment (Default to flash if not set)
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

# SETUP AI
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    print(f"--- STARTING BOT WITH MODEL: {MODEL_NAME} ---", flush=True)
    model = genai.GenerativeModel(MODEL_NAME)
else:
    print("WARNING: GEMINI_API_KEY is missing!", file=sys.stderr)

# --- FUNCTION TO LOAD EXCEL ---
def load_products_from_excel():
    try:
        # Check if file exists first
        if not os.path.exists('product.xlsx'):
            return "Error: product.xlsx file not found on server."
            
        df = pd.read_excel('product.xlsx')
        
        product_text = ""
        for index, row in df.iterrows():
            # Check for NaN (Empty cells) to prevent errors
            p_name = row['Product Name'] if pd.notna(row['Product Name']) else "Unknown"
            p_price = row['Price'] if pd.notna(row['Price']) else "$0"
            p_desc = row['Description'] if pd.notna(row['Description']) else ""
            p_img = row['Image URL'] if pd.notna(row['Image URL']) else ""
            
            product_text += f"""
            ITEM #{row['Number']}: {p_name} ({p_price})
            - Desc: {p_desc}
            - Ingredients: {row['Ingredient']}
            - Image: {p_img}
            - Note: {row['Remarks']}
            --------------------------------
            """
        return product_text
    except Exception as e:
        print(f"Error reading Excel: {e}", flush=True)
        return "Error loading product list."

# Load data on startup
PRODUCT_DATA = load_products_from_excel()

# HTML UI
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pet Bakery Chat</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #fff5e6; }
        h2 { text-align: center; color: #8B4513; }
        #chat-box { height: 450px; overflow-y: scroll; background: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .message { margin: 10px 0; padding: 12px; border-radius: 15px; max-width: 80%; line-height: 1.4; }
        .user { background: #8B4513; color: white; margin-left: auto; text-align: right; border-bottom-right-radius: 2px; }
        .bot { background: #f0f0f0; color: #333; margin-right: auto; text-align: left; border-bottom-left-radius: 2px; }
        .bot img { max-width: 100%; border-radius: 10px; margin-top: 5px; border: 2px solid #ddd; }
        .input-area { margin-top: 15px; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border-radius: 25px; border: 1px solid #ccc; font-size: 16px; outline: none; }
        button { padding: 10px 25px; background: #E67E22; color: white; border: none; border-radius: 25px; cursor: pointer; font-weight: bold; }
        .wa-btn { display: block; width: 100%; background: #25D366; color: white; text-align: center; padding: 12px; margin-top: 10px; text-decoration: none; border-radius: 10px; font-weight: bold; box-sizing: border-box; }
    </style>
</head>
<body>
    <h2>🐶 The Pet Bakery 🐱</h2>
    <div id="chat-box"></div>
    <div class="input-area">
        <input type="text" id="user-input" placeholder="Ask about our cakes...">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script>
        const chatBox = document.getElementById('chat-box');
        const inputField = document.getElementById('user-input');

        inputField.addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMessage();
            }
        });
        
        async function sendMessage() {
            const text = inputField.value;
            if (!text) return;

            addMessage(text, 'user');
            inputField.value = '';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();
                addBotMessageHTML(data.reply);

                if (data.is_order) {
                    const btn = document.createElement('a');
                    btn.className = 'wa-btn';
                    btn.href = `https://wa.me/{{ my_number }}?text=${encodeURIComponent(data.order_summary)}`;
                    btn.innerText = "CLICK TO CONFIRM ORDER (WhatsApp)";
                    chatBox.appendChild(btn);
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            } catch (error) {
                console.error("Error:", error);
                addMessage("Error: Connection Failed.", 'error');
            }
        }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.innerText = text;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function addBotMessageHTML(htmlContent) {
            const div = document.createElement('div');
            div.className = `message bot`;
            div.innerHTML = htmlContent;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, my_number=MY_PHONE_NUMBER)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get('message')
        
        # Reload Excel on every message? 
        # Uncomment the next line if you want instant updates without restarting Render
        # PRODUCT_DATA = load_products_from_excel()

        system_instruction = f"""
        You are the sales assistant for 'The Pet Bakery'.
        
        RULES:
        1. NO READY STOCK. ALL ORDERS REQUIRE 3-5 DAYS ADVANCE NOTICE.
        2. Only sell items from the list below.
        3. If showing a product, you MUST display the image using: <br><img src="URL"><br>
        
        CURRENT MENU:
        {PRODUCT_DATA}
        
        If user orders:
        1. Get Date, Flavor, Quantity.
        2. Start reply with "ORDER_CONFIRMED:" followed by summary.
        """
        
        full_prompt = f"{system_instruction}\nUser: {user_msg}\nAssistant:"
        
        response = model.generate_content(full_prompt)
        ai_text = response.text
        
        is_order = False
        order_summary = ""
        
        if "ORDER_CONFIRMED:" in ai_text:
            is_order = True
            order_summary = ai_text.replace("ORDER_CONFIRMED:", "").strip()
            ai_text = "Perfect! Click below to send your order via WhatsApp."

        return jsonify({"reply": ai_text, "is_order": is_order, "order_summary": order_summary})

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return jsonify({"reply": "My oven is overheating! (System Error)"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
