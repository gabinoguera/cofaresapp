import logging
import random
from time import sleep

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Productos simulados
MOCK_PRODUCTS = [
    {
        "codigo_web": "P001",
        "nombre": "Crema Hidratante Facial",
        "descripcion": "Crema hidratante para todo tipo de pieles. Hidratación 24h.",
        "tipo": ["facial", "hidratante"],
        "distance_to_query": "0.95"
    },
    {
        "codigo_web": "P002",
        "nombre": "Crema de Manos Reparadora",
        "descripcion": "Crema reparadora intensiva para manos secas y agrietadas.",
        "tipo": ["manos", "reparadora"],
        "distance_to_query": "0.92"
    },
    {
        "codigo_web": "P003",
        "nombre": "Crema Corporal Nutritiva",
        "descripcion": "Crema corporal con aceites naturales para nutrición profunda.",
        "tipo": ["corporal", "nutritiva"],
        "distance_to_query": "0.88"
    }
]

# Preguntas de refinamiento
REFINEMENT_QUESTIONS = {
    "crema": {
        "question": "¿Qué tipo de crema buscas? Tenemos cremas faciales, de manos y corporales.",
        "keywords": ["facial", "manos", "corporal"]
    },
    "vitamina": {
        "question": "¿Qué tipo de vitaminas necesitas? Tenemos vitamina C, complejo B y multivitamínicos.",
        "keywords": ["c", "b", "multi"]
    }
}

# Variable para mantener el estado de la conversación
conversation_state = {
    "needs_refinement": False,
    "current_topic": None,
    "previous_question": None
}

def generate_response(prompt_user):
    """Simula la generación de respuestas con refinamiento de consultas"""
    try:
        prompt_lower = prompt_user.lower()
        
        # Manejo de saludos
        if any(word in prompt_lower for word in ["hola", "buenos días", "buenas"]):
            conversation_state["needs_refinement"] = False
            return {
                "type": "conversation",
                "message": "¡Hola! Soy el asistente virtual de la farmacia. ¿En qué puedo ayudarte?"
            }
        
        # Manejo de despedidas
        if any(word in prompt_lower for word in ["adiós", "gracias", "hasta luego"]):
            conversation_state["needs_refinement"] = False
            return {
                "type": "conversation",
                "message": "¡Gracias por tu consulta! ¿Hay algo más en lo que pueda ayudarte?"
            }

        # Verificar si necesitamos refinar la búsqueda
        if "crema" in prompt_lower and not any(keyword in prompt_lower for keyword in REFINEMENT_QUESTIONS["crema"]["keywords"]):
            conversation_state["needs_refinement"] = True
            conversation_state["current_topic"] = "crema"
            return {
                "type": "conversation",
                "message": REFINEMENT_QUESTIONS["crema"]["question"]
            }
        
        # Procesar respuesta al refinamiento
        if conversation_state["needs_refinement"]:
            topic = conversation_state["current_topic"]
            if topic and any(keyword in prompt_lower for keyword in REFINEMENT_QUESTIONS[topic]["keywords"]):
                conversation_state["needs_refinement"] = False
                # Filtrar productos según la respuesta
                filtered_products = [
                    product for product in MOCK_PRODUCTS 
                    if any(keyword in prompt_lower for keyword in product["tipo"])
                ]
                if filtered_products:
                    return {
                        "type": "product_search",
                        "message": f"He encontrado estos productos específicos para ti:",
                        "products": filtered_products
                    }

        # Búsqueda general de productos
        sleep(0.5)  # Simular tiempo de procesamiento
        selected_products = random.sample(MOCK_PRODUCTS, min(2, len(MOCK_PRODUCTS)))
        
        return {
            "type": "product_search",
            "message": f"He encontrado {len(selected_products)} productos que podrían interesarte:",
            "products": selected_products
        }
        
    except Exception as e:
        logger.error(f"Error en generate_response: {str(e)}")
        return {
            "type": "error",
            "message": f"Ha ocurrido un error: {str(e)}"
        }