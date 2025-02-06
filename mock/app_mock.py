from flask import Flask, render_template, request, jsonify
from .bigquery_client_mock import generate_response  # Añadimos el punto para importación relativa
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Flask con la nueva ubicación de las carpetas static y templates
app = Flask(__name__, 
           static_folder='static_mock',
           template_folder='templates_mock')

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

        # Llama a la función de respuesta en el backend mock
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
                    "distance_to_query": "simulado"  # Valor simulado para distance_to_query
                }
                filtered_products.append(product_dict)
                
            return jsonify({
                "response": serialized_response.get("message"), 
                "products": filtered_products,
                "response_time": 0.5  # Tiempo de respuesta simulado
            })

        # Envía solo el mensaje generado al frontend
        return jsonify({
            "response": serialized_response.get("message") 
            if isinstance(serialized_response, dict) 
            else serialized_response,
            "response_time": 0.5  # Tiempo de respuesta simulado
        })

    except Exception as e:
        logger.error(f"Error en /chat: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)