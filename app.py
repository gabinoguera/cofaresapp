# app.py
from flask import Flask, render_template, request, jsonify
from bigquery_client import get_products, generate_response, rerank_products  # Importar las funciones necesarias

app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():
    # Verificar que el JSON de la solicitud no sea None
    if not request.json or 'prompt' not in request.json:
        return jsonify({"error": "No se proporcionó un prompt"}), 400

    prompt = request.json.get("prompt")
    
    try:
        products = get_products(prompt)  # Obtener productos
        ranked_products = rerank_products(prompt, products)  # Rerankear productos
        response_text = generate_response(prompt, ranked_products)  # Generar respuesta usando productos rerankeados
        return jsonify({"response": response_text})
    except Exception as e:
        # Manejo de errores generales
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return render_template("home.html")