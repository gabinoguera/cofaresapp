import os
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

load_dotenv()  # Carga las variables desde .env al entorno
client = bigquery.Client(project='dataton-2024-team-01-cofares')
# Ahora puedes acceder a las variables de entorno
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Configuración del cliente de Vertex AI
PROJECT_ID = "dataton-2024-team-01-cofares"
LOCATION = "us-central1"

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
          MODEL `dataton-2024-team-01-cofares.datos_cofares.text_embedding`,
          (SELECT @prompt AS content),  -- Aquí usamos el parámetro
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
      ML.DISTANCE(
        qe.query_embedding,
        e.ml_generate_embedding_result,
        'COSINE'
      ) AS distance_to_query
    FROM
      `dataton-2024-team-01-cofares.datos_cofares.data_final_temp` AS d
    INNER JOIN
      `dataton-2024-team-01-cofares.datos_cofares.SalidaEmbeddings_temp` AS e
      ON d.codigo_web = e.title
    INNER JOIN QueryEmbedding AS qe
      ON TRUE
    ORDER BY
      distance_to_query
    LIMIT 10;
    """.format(prompt)
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

        descripcion = row.descripcion
        if not row.descripcion:
            descripcion = '-'
        
        modo_implementacion = row.modo_implementacion
        if not row.modo_implementacion:
            modo_implementacion = '-'


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
            "distance_to_query": row.distance_to_query
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
            content=product["descripcion"] + " " + product["modo_implementacion"]
        )
        for index, product in enumerate(products)
    ]
    
    request = discoveryengine.RankRequest(
        ranking_config=ranking_config,
        model="semantic-ranker-512@latest",
        top_n=10, # cantidad de productos a rankear
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
            "distance_to_query": products[int(record.id)]["distance_to_query"]
        }
        for record in response.records[:5] # cantidad de productos a mostrar
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
                        "distance_to_query": {"type": "number", "description": "Semantic distance to query"}
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

def generate_response(prompt):  # Eliminamos el parámetro products
    #chat = multimodal_model.start_chat()

    instruction_prompt = f"""
    # Instrucción
    Eres Cofarma, una asistente farmacéutica experta.\
    Tu tarea consiste en responder eficazmente a las consultas de los profesionales de farmacia.\
    Te proporcionamos una lista de productos procedentes de la base de datos y previamente rankeados por relevancia.\
    Primero debes leer atentamente la entrada del usuario,\
    y luego desarrollar una respuesta basada en los Criterios proporcionados en la sección Producto a continuación.\
    
    # Producto
    ## Definición de la herramienta
    Tienes acceso a una lista de productos de una base de datos de productos de farmacia "{tools}"\
    que han sido reordenados para proporcionar la mejor respuesta posible a la consulta de un profesional de farmacia.\
    Las instrucciones para realizar la tarea de respuesta a una pregunta se proporcionan en la consulta del usuario.\
    
    ## Criterios
    - Si la entrada del profesional de farmacia es un saludo, preséntese cordialmente como Cofarma el asistente de búsqueda.\
        Ejemplos de saludos: «hola», “hola”, “¿Qué tal?”.\
    - Si es necesario, puede pedir detalles aclaratorios para ajustar la búsqueda a resultados eficientes.\
    - Si la entrada solicita búsquedas no relacionadas con productos de farmacia, aclare que ese no es su propósito como asistente de búsqueda de productos de farmacia.\
        Ejemplos de solicitudes no pertinentes: «Quiero la receta de una lasaña», “Quiero pedir una pizza”, “¿Qué tiempo hace hoy?”.\
    - Cuando la entrada sea relevante para activar la búsqueda de productos de farmacia, utiliza "tools" para recibir una lista de productos de farmacia clasificados que ayuden al usuario con su tarea. Acepta la solicitud del usuario y proporciónale la lista de productos.
    - No sugieras ni añadas productos que no estén en la lista proporcionada por el reranker.

    ### Prompt

        Aquí está la consulta del experto farmacéutico: {prompt}
    """

    try:
        response = chat.send_message(instruction_prompt)
        response.candidates[0].content.parts[0]
        
        # Verificar si hay una llamada a función
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    # Ejecutar búsqueda de productos
                    products = get_products(prompt)
                    if not products:
                        return "Lo siento, no encontré productos que coincidan con tu búsqueda."
                    
                    ranked_products = rerank_products(prompt, products)
                    
                    # Enviar los resultados al modelo para generar una respuesta contextual
                    results_prompt = f"""
                    Basado en la búsqueda "{prompt}", he encontrado estos productos:
                    {[product['nombre'] for product in ranked_products['products']]}
                    
                    Por favor, genera una respuesta útil que:
                    1. Mencione los productos encontrados
                    2. Explique por qué son relevantes
                    """
                    
                    final_response = chat.send_message(results_prompt)
                    return {
                        "type": "product_search",
                        "message": final_response.text,
                        "products": ranked_products["products"]
                    }
                
        # Si no hay llamada a función, devolver la respuesta conversacional
        return {
            "type": "conversation",
            "message": response.text
        }
                    
    except Exception as e:
        return f"Lo siento, ocurrió un error: {str(e)}"