import os
import logging
from google.cloud import bigquery
from dotenv import load_dotenv
import vertexai
from google.cloud import discoveryengine_v1 as discoveryengine
from vertexai import generative_models as genai  # Añadir esta línea
from vertexai.generative_models import (
    FunctionDeclaration,
    GenerationConfig,
    Tool,
)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Archivo de log
        logging.StreamHandler()            # Consola
    ]
)

logger = logging.getLogger(__name__)

load_dotenv()  # Carga las variables desde .env al entorno
client = bigquery.Client(project='dataton-2024-team-01-cofares')
# Ahora puedes acceder a las variables de entorno
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Configuración del cliente de Vertex AI
PROJECT_ID = "dataton-2024-team-01-cofares"
LOCATION = "europe-west4"

# Inicializa el cliente de Discovery Engine
discovery_client = discoveryengine.RankServiceClient() 

def get_products(prompt):
    client = bigquery.Client(project=project_id)
    query = """
    WITH QueryEmbedding AS (
      SELECT
        ml_generate_embedding_result AS query_embedding
      FROM
        ML.GENERATE_EMBEDDING(
          MODEL `dataton-2024-team-01-cofares.datos_cofares.text_gecko`,  -- Añadidos los backticks
          (SELECT @prompt AS content),
          STRUCT(TRUE AS flatten_json_output, 'RETRIEVAL_QUERY' AS task_type)
        )
    )
    SELECT
      d.nombre_completo_material AS nombre,
      d.txt_mas_informacion_del_producto AS descripcion,
      d.txt_instrucciones_de_uso AS modo_implementacion,
      d.codigo_web,
      d.URI_primera_imagen,
      d.codigo_nacional,
      d.nombre_matricula_nivel0 AS matricula0,
      d.nombre_matricula_nivel1 AS matricula1,
      d.txt_composicion AS composicion,
      d.forma,
      d.color,
      d.descripcion_visual,
      d.empaque,
      d.zona_de_aplicacion,
      ML.DISTANCE(
        qe.query_embedding,
        d.ml_generate_embedding_result,
        'COSINE'
      ) AS distance_to_query
    FROM
      `dataton-2024-team-01-cofares.datos_cofares.data_and_embeddings` as d
    INNER JOIN QueryEmbedding AS qe
      ON TRUE
    ORDER BY
      distance_to_query
    LIMIT 100;
    """
    
    # Imprimir la consulta SQL generada para depuración
    #print(query)  # Esto te ayudará a verificar la consulta

    # Configura el parámetro para el prompt
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("prompt", "STRING", prompt)
        ]
    )

    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    products = []
    for row in results:
        # Asignación de valores con lógica adicional
        descripcion = row.descripcion if row.descripcion else '-'
        modo_implementacion = row.modo_implementacion if row.modo_implementacion else '-'

        # Cambia la URL si es necesario
        imagen_url = row.URI_primera_imagen 
        if imagen_url and imagen_url.startswith('gs:/'):
            imagen_url = imagen_url.replace('gs://dataton-2024-team-01-cofares-datastore/imagenes/', 'https://storage.googleapis.com/dataton-2024-team-01-cofares-datastore/imagenes/reto_cofares/')

        products.append({
            "codigo_web": row.codigo_web,
            "nombre": row.nombre,
            "codigo_nacional": row.codigo_nacional,
            "descripcion": descripcion,
            "modo_implementacion": modo_implementacion,
            "imagen_url": imagen_url,
            "distance_to_query": row.distance_to_query,
            "matricula0": row.matricula0,
            "matricula1": row.matricula1,
            "composicion": row.composicion,
            "forma": row.forma,
            "color": row.color,
            "descripcion_visual": row.descripcion_visual,
            "empaque": row.empaque,
            "zona_de_aplicacion": row.zona_de_aplicacion
        })
    return products

def rerank_products(prompt, products):
    ranking_config = discovery_client.ranking_config_path(
        project=PROJECT_ID,
        location=LOCATION,
        ranking_config="default_ranking_config",
    )
    
    records = [
        discoveryengine.RankingRecord(
            id=str(index),
            title=product["nombre"],
            content=" ".join(filter(None, [  # Filtrar valores None y unir con espacios
                str(product["descripcion"] or ""),
                str(product["modo_implementacion"] or ""),
                str(product.get("descripcion_visual", "") or ""),
                str(product.get("matricula0", "") or ""),
                str(product.get("matricula1", "") or ""),
                str(product.get("composicion", "") or ""),
                str(product.get("forma", "") or ""),
                str(product.get("color", "") or ""),
                str(product.get("empaque", "") or ""),
                str(product.get("zona_de_aplicacion", "") or ""),
                str(product.get("codigo_web", "") or ""),
                str(product.get("codigo_nacional", "") or "")
            ]))
        )
        for index, product in enumerate(products)
    ]
    
    request = discoveryengine.RankRequest(
        ranking_config=ranking_config,
        model="semantic-ranker-512@latest",
        top_n=50, # cantidad de productos a rankear
        query=prompt,
        records=records,
    )
    
    response = discovery_client.rank(request=request)
    
    # Aseguramos que los productos están formateados según el esquema
    ranked_products = [
        {
            "codigo_web": products[int(record.id)]["codigo_web"],
            "nombre": products[int(record.id)]["nombre"],
            "codigo_nacional": products[int(record.id)]["codigo_nacional"],
            "descripcion": products[int(record.id)]["descripcion"],
            "modo_implementacion": products[int(record.id)]["modo_implementacion"],
            "imagen_url": products[int(record.id)]["imagen_url"],
            "distance_to_query": products[int(record.id)]["distance_to_query"],
            "descripcion_visual": products[int(record.id)].get("descripcion_visual", ""),
            "matricula0": products[int(record.id)].get("matricula0", ""),
            "matricula1": products[int(record.id)].get("matricula1", ""),
            "composicion": products[int(record.id)].get("composicion", ""),
            "forma": products[int(record.id)].get("forma", ""),
            "color": products[int(record.id)].get("color", ""),
            "empaque": products[int(record.id)].get("empaque", ""),
            "zona_de_aplicacion": products[int(record.id)].get("zona_de_aplicacion", "")
        }
        for record in response.records[:20] # cantidad de productos a mostrar
    ]
    
    return {"products": ranked_products}

# Define el schema
product_schema = FunctionDeclaration(
    name="product_query",
    description="Fetches relevant product information based on a search prompt.",
    parameters={
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo_web": {"type": "string", "description": "Product web code"},
                        "nombre": {"type": "string", "description": "Product name"},
                        "codigo_nacional": {"type": "string", "description": "National product code"},
                        "descripcion": {"type": "string", "description": "Product description"},
                        "modo_implementacion": {"type": "string", "description": "Mode of implementation"},
                        "imagen_url": {"type": "string", "description": "Image URL"},
                        "distance_to_query": {"type": "number", "description": "Semantic distance to query"},
                        "descripcion_visual": {"type": "string", "description": "Visual description of the product"},
                        "matricula0": {"type": "string", "description": "Level 0 registration name"},
                        "matricula1": {"type": "string", "description": "Level 1 registration name"},
                        "composicion": {"type": "string", "description": "Composition of the product"},
                        "forma": {"type": "string", "description": "Form of the product"},
                        "color": {"type": "string", "description": "Color of the product"},
                        "empaque": {"type": "string", "description": "Packaging of the product"},
                        "zona_de_aplicacion": {"type": "string", "description": "Application area of the product"}
                    }
                }
            }
        }
    }
)

# Define tools antes de inicializar el modelo
tools = [Tool(function_declarations=[product_schema])]


vertexai.init(project=PROJECT_ID, location=LOCATION)

# Model definition
multimodal_model = genai.GenerativeModel(
"gemini-1.5-flash",
generation_config=GenerationConfig(temperature=0),
tools=tools)

chat = multimodal_model.start_chat(response_validation=False)
# Lista para almacenar el historial de mensajes
message_history = []
# Construir el historial de la conversación
#historial_conversacion = "\n".join([f"{message['role']}: {message['content']}" for message in message_history])


def refine_query_with_keywords(message_history):

    try:
        # Crear un prompt para el modelo que refine la consulta
        refinement_prompt = """
        Eres un asistente experto en extracción de palabras clave. A continuación, tienes el historial de una conversación:

        Historial de conversación:
        {}

        Extrae las palabras clave más importantes de la consulta del usuario en base al historial y devuélvelas en un formato de texto claro.
        Formato esperado: palabras clave separadas por comas.
        """.format(
            "\n".join([f"{message['role'].capitalize()}: {message['content']}" for message in message_history])
        )

        # Enviar el prompt al modelo para generar el refinamiento
        refinement_response = chat.send_message(refinement_prompt)

        # Obtener la respuesta generada
        prompt = refinement_response.text.strip()

        logger.info(f"Query refinada generada: {prompt}")
        return prompt

    except Exception as e:
        logger.error(f"Error en refine_query_with_keywords: {str(e)}")
        # En caso de error, devolvemos una consulta vacía o un mensaje genérico
        return "consulta vacía"
    

#INTENTAMOS ACTUALIZAR EL HISTORIAL DE MENSAJES
def generate_response(prompt_user):
    # Agregar el mensaje del usuario al historial
    message_history.append({"role": "user", "content": prompt_user})

    # Prompt principal
    instruction_prompt = f"""
        # Instrucción
        Eres Cofinder, un asistente farmacéutico experto.

        Tu tarea consiste en responder eficazmente a las consultas de los profesionales de farmacia.
        Te proporcionamos una lista de productos de parafarmacia y veterinaria procedentes de la base de datos y previamente rankeados por relevancia.
        Primero debes leer atentamente la entrada del usuario, y luego desarrollar una respuesta basada en los Criterios proporcionados
        en la sección Producto a continuación.

        # Producto
        ## Definición de la herramienta
        Tienes acceso a una lista de productos de una base de datos de productos de farmacia y veterinaria "{tools}"
        que han sido reordenados para proporcionar la mejor respuesta posible a la consulta de un profesional.  
        Las instrucciones para realizar la tarea de respuesta a una pregunta se proporcionan en la consulta del usuario.

        ## Criterios
        - Si la entrada del profesional (farmacia o veterinaria) es un saludo, preséntese cordialmente como Cofinder el asistente de búsqueda.
            Ejemplos de saludos: «hola», “hola”, “¿Qué tal?”.

        - Si es necesario, puede pedir detalles aclaratorios para ajustar la búsqueda a resultados eficientes.
            Por ejemplo, si el usuario pide "un producto para la tos", pregunte: "¿Para un humano o un animal? ¿Qué tipo de animal? ¿Qué edad tiene?".
            O si el usuario pide "un producto para el dolor", pregunte: "¿Qué tipo de dolor? ¿Para qué especie? ¿Hay alguna contraindicación?".

        - Si la entrada solicita búsquedas no relacionadas con productos de parafarmacia o veterinaria,
            aclare que ese no es su propósito como asistente de búsqueda de productos de parafarmacia y veterinaria.
            Ejemplos de solicitudes no pertinentes: «Quiero la receta de una lasaña», “Quiero pedir una pizza”, “¿Qué tiempo hace hoy?”.

        - Cuando la entrada sea relevante para activar la búsqueda de productos de parafarmacia o veterinaria, utiliza "tools"
        para recibir una lista de productos de parafarmacia y veterinaria clasificados que ayuden al usuario con su tarea.
        Acepta la solicitud del usuario y proporciónale la lista de productos sin reescribirla.

        - No sugieras ni añadas productos que no estén en la lista proporcionada por el reranker. Tampoco inventes información.

        ### Ejemplos de entradas de usuario y respuestas:

        Entrada: Hola

        Respuesta: ¡Hola! Soy Cofinder, su asistente de búsqueda para productos farmacéuticos y veterinarios. ¿En qué puedo ayudarle?

        Entrada: Busco un antiinflamatorio para perros.

        Respuesta: Por favor, especifique el tamaño y la raza del perro para poder ofrecerle una mejor recomendación. Una vez que me proporcione esta información, accederé a la base de datos.

        Entrada: Necesito un jarabe para la tos para niños, que no sea en cápsulas.

        Respuesta: Accediendo a la base de datos... [Aquí se insertaría la lista de "tools" filtrada según la consulta, priorizando jarabes para la tos infantil, no en cápsulas].

        Entrada: Quiero pedir una pizza.

        Respuesta: Lo siento, pero no estoy programado para gestionar pedidos de comida. Soy un asistente de búsqueda para productos farmacéuticos y veterinarios. ¿Puedo ayudarle con alguna otra consulta relacionada con estos productos?

        Entrada: Leche sin lactosa para bebé.

        Respuesta: Accediendo a la base de datos... [Aquí se insertaría la lista de "tools" filtrada según la consulta, priorizando productos sin lactosa para bebés].

        ### Prompt

        Aquí está la consulta del experto farmacéutico: {prompt_user} 
    """

    try:
        # Enviar el mensaje al modelo
        response = chat.send_message(instruction_prompt)
        response_text = response.candidates[0].content.parts[0]

        # Agregar la respuesta del modelo al historial
        message_history.append({"role": "assistant", "content": response_text})

        # Verificar si hay una llamada a función
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    # Refinar la query utilizando el historial actualizado
                    prompt = refine_query_with_keywords(message_history)

                    # Ejecutar búsqueda de productos
                    products = get_products(prompt)
                    if not products:
                        return {
                            "type": "error",
                            "message": "Lo siento, no encontré productos que coincidan con tu búsqueda."
                        }
                    
                    ranked_products = rerank_products(prompt, products)
                    
                    # Devolver directamente la lista de productos
                    return {
                        "type": "product_search",
                        "message": "He encontrado los siguientes productos:",
                        "products": ranked_products["products"]
                    }

        # Si no hay llamada a función, devolver la respuesta conversacional
        return {
            "type": "conversation",
            "message": response_text
        }
                    
    except Exception as e:
        logger.error(f"Error en generate_response: {str(e)}")
        return {
            "type": "error",
            "message": f"Lo siento, ocurrió un error: {str(e)}"
        }