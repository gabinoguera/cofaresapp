from flask import Flask, render_template, request, jsonify
from bigquery_client import generate_response
import logging
import os

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)

def serialize_response(obj):
    """Función auxiliar para serializar objetos no JSON-serializables"""
    if hasattr(obj, 'text'):
        return obj.text
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, (list, tuple)):
        return [serialize_response(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_response(v) for k, v in obj.items()}
    return str(obj)

@app.route("/", methods=["GET"])
def home():
    """Cargar la interfaz principal del chatbot."""
    return render_template("home.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Procesa las consultas del usuario y devuelve la respuesta del backend."""
    try:
        data = request.get_json()
        prompt_user = data.get("prompt", "")

        if not prompt_user:
            return jsonify({"error": "No se proporcionó ningún prompt"}), 400

        # Llama a la función de respuesta en el backend
        response = generate_response(prompt_user)
        
        # Serializar la respuesta
        serialized_response = serialize_response(response)

        # Filtrar solo los campos necesarios
        if isinstance(serialized_response, dict) and serialized_response.get("type") == "product_search":
            products = serialized_response.get("products", [])
            filtered_products = []
            for product in products:
                product_dict = {
                    "codigo_web": product.get("codigo_web"),
                    "nombre": product.get("nombre"),
                    "descripcion": product.get("descripcion"),
                    "distance_to_query": product.get("distance_to_query", "N/A")  # Agregamos distancia
                }
                filtered_products.append(product_dict)
                
            return jsonify({
                "response": serialized_response.get("message"), 
                "products": filtered_products
            })

        # Envía solo el mensaje generado al frontend
        return jsonify({
            "response": serialized_response.get("message") 
            if isinstance(serialized_response, dict) 
            else serialized_response
        })

    except Exception as e:
        logger.error(f"Error en /chat: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)