from flask import Flask, render_template, request, jsonify
from bigquery_client import generate_response  # Importa la función desde tu backend
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    """Cargar la interfaz principal del chatbot."""
    return render_template("home.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Procesa las consultas del usuario y devuelve la respuesta del backend."""
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")

        if not prompt:
            return jsonify({"error": "No se proporcionó ningún prompt"}), 400

        # Llama a la función de respuesta en el backend
        response = generate_response(prompt)

        # Filtrar solo los campos necesarios
        if response.get("type") == "product_search":
            products = response["products"]
            filtered_products = [
                {
                    "codigo_web": product["codigo_web"],
                    "nombre": product["nombre"],
                    "descripcion": product["descripcion"]
                }
                for product in products
            ]
            return jsonify({"response": response["message"], "products": filtered_products})

        # Envía solo el mensaje generado al frontend
        return jsonify({"response": response["message"] if isinstance(response, dict) else response})

    except Exception as e:
        logger.error(f"Error en /chat: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == "__main__":
    app.run(debug=True)
