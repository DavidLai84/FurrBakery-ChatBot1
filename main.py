import os
from flask import Flask, render_template_string, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. SETUP API KEY (From Render Environment Variables)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
MY_PHONE_NUMBER = os.environ.get("MY_PHONE_NUMBER") # Your number (e.g., 60123456789)

# 2. CONFIGURE GEMINI
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# 3. THE HTML UI (The Chat Window)
# We put HTML inside Python to keep it in one file for simplicity
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>My AI Assistant</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f0f2f5; }
        #chat-box { height: 400px; overflow-y: scroll; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .message { margin: 10px 0; padding: 10px; border-radius: 10px; }
        .user { background: #dcf8c6; text-align: right; margin-left: 20%; }
        .bot { background: #e9e9eb; text-align: left; margin-right: 20%; }
        .input-area { margin-top: 15px; display: flex; gap: 10px; }
        input { flex: 1; padding: 10px; border-radius: 20px; border: 1px solid #ccc; }
        button { padding: 10px 20px; background: #25D366; color: white; border: none; border-radius: 20px; cursor: pointer; }
        .wa-btn { display: block; width: 100%; background: #25D366; color: white; text-align: center; padding: 10px; margin-top: 10px; text-decoration: none; border-radius: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <h2>Chat with us</h2>
    <div id="chat-box"></div>
    <div class="input-area">
        <input type="text" id="user-input" placeholder="Ask about products...">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script>
        const chatBox = document.getElementById('chat-box');
        
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const text = input.value;
            if (!text) return;

            // Show User Message
            addMessage(text, 'user');
            input.value = '';

            // Send to Server
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();

            // Show Bot Message
            addMessage(data.reply, 'bot');

            // If AI detects order is ready, show WhatsApp Button
            if (data.is_order) {
                const btn = document.createElement('a');
                btn.className = 'wa-btn';
                // This link opens WhatsApp on their phone and messages YOU
                btn.href = `https://wa.me/{{ my_number }}?text=${encodeURIComponent(data.order_summary)}`;
                btn.innerText = "CONFIRM ORDER ON WHATSAPP";
                chatBox.appendChild(btn);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.innerText = text;
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
    user_msg = request.json.get('message')
    
    # SYSTEM PROMPT: TEACH THE AI WHO IT IS
    # This instructs the AI to detect when to close the deal
    system_instruction = f"""
    You are a helpful sales assistant for 'My Shop'.
    We sell: Red Shoes ($50), Blue Shirts ($20).
    Answer questions briefly.
    
    IMPORTANT LOGIC:
    If the user confirms they want to buy or place an order:
    1. Start your reply with "ORDER_CONFIRMED:"
    2. Then write a short summary of the order.
    3. Example: "ORDER_CONFIRMED: I would like to buy 1 Red Shoe."
    
    If they are just chatting, just reply normally.
    """
    
    full_prompt = f"{system_instruction}\nUser: {user_msg}\nAssistant:"
    
    response = model.generate_content(full_prompt)
    ai_text = response.text
    
    # Check if AI triggered the order
    is_order = False
    order_summary = ""
    
    if "ORDER_CONFIRMED:" in ai_text:
        is_order = True
        # Clean up the text so the user sees a nice message
        order_summary = ai_text.replace("ORDER_CONFIRMED:", "").strip()
        ai_text = "Great! Click the button below to send your order details to our WhatsApp."

    return jsonify({"reply": ai_text, "is_order": is_order, "order_summary": order_summary})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
