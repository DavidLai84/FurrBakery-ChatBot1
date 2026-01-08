import os
import sys
from flask import Flask, render_template_string, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# CONFIG
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
MY_PHONE_NUMBER = os.environ.get("MY_PHONE_NUMBER")

# SETUP AI
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # Using the Flash model (Faster/Cheaper)
    model = genai.GenerativeModel('gemini-3-flash-preview')
else:
    print("WARNING: GEMINI_API_KEY is missing!", file=sys.stderr)

# HTML UI with "Enter Key" Support
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
        .error { background: #ffcccc; text-align: center; color: red; }
        .input-area { margin-top: 15px; display: flex; gap: 10px; }
        input { flex: 1; padding: 10px; border-radius: 20px; border: 1px solid #ccc; font-size: 16px; }
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
        const inputField = document.getElementById('user-input');

        // LISTEN FOR ENTER KEY
        inputField.addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                event.preventDefault(); // Stop screen from refreshing
                sendMessage();
            }
        });
        
        async function sendMessage() {
            const text = inputField.value;
            if (!text) return;

            addMessage(text, 'user');
            inputField.value = ''; // Clear box immediately

            try {
                // Send to Server
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });

                if (!response.ok) {
                    throw new Error("Server Error: " + response.status);
                }

                const data = await response.json();
                addMessage(data.reply, 'bot');

                if (data.is_order) {
                    const btn = document.createElement('a');
                    btn.className = 'wa-btn';
                    btn.href = `https://wa.me/{{ my_number }}?text=${encodeURIComponent(data.order_summary)}`;
                    btn.innerText = "CONFIRM ORDER ON WHATSAPP";
                    chatBox.appendChild(btn);
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            } catch (error) {
                console.error("Error:", error);
                addMessage("Error: " + error.message, 'error');
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
    print("--- MSG RECEIVED ---", flush=True)
    try:
        data = request.json
        user_msg = data.get('message')
        
        if not model:
            return jsonify({"reply": "System Error: AI model not loaded."}), 500
        
        # SYSTEM PROMPT
        # Edit this text to change your shop's behavior!
        system_instruction = """
        You are a helpful sales assistant.
        If user confirms order, start reply with "ORDER_CONFIRMED:".
        Otherwise answer briefly.
        """
        
        full_prompt = f"{system_instruction}\nUser: {user_msg}\nAssistant:"
        
        response = model.generate_content(full_prompt)
        ai_text = response.text
        
        is_order = False
        order_summary = ""
        
        if "ORDER_CONFIRMED:" in ai_text:
            is_order = True
            order_summary = ai_text.replace("ORDER_CONFIRMED:", "").strip()
            ai_text = "Click below to send this to WhatsApp."

        return jsonify({"reply": ai_text, "is_order": is_order, "order_summary": order_summary})

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return jsonify({"reply": "I am having trouble thinking right now."}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
