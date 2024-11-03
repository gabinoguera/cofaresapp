# app.py
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from intent_recognition import QueryManager  # Ensure QueryManager is correctly defined in intent_recognition.py
import os
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Fetch project ID and initialize QueryManager
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
if not project_id:
    logging.error("Environment variable 'GOOGLE_CLOUD_PROJECT' not found.")
    raise ValueError("Missing 'GOOGLE_CLOUD_PROJECT' environment variable.")

# Instantiate the QueryManager
query_manager = QueryManager(project_id)

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")

@app.route("/chat", methods=["POST"])
def chat():
    # Check for prompt in request
    if not request.json or 'prompt' not in request.json:
        return jsonify({"error": "No prompt provided"}), 400

    prompt = request.json.get("prompt")
    try:
        # Process query through QueryManager
        response_text = query_manager.process_query(prompt)

        # Structure the response for the front-end
        return jsonify({
            "response": response_text
        })
    except Exception as e:
        logging.exception("Error processing query")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Enable logging and run app
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True)