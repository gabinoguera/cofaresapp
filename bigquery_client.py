from google.cloud import bigquery
from dotenv import load_dotenv
import os
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import discoveryengine_v1 as discoveryengine

load_dotenv()  # Carga las variables desde .env al entorno
client = bigquery.Client(project='dataton-2024-team-01-cofares')
# Ahora puedes acceder a las variables de entorno
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Configuración del cliente de Vertex AI
PROJECT_ID = "dataton-2024-team-01-cofares"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)
multimodal_model = GenerativeModel("gemini-1.5-flash-001")

# Inicializa el cliente de Discovery Engine
discovery_client = discoveryengine.RankServiceClient()  

class BigQueryClient:
    def __init__(self, project_id):
        self.client = bigquery.Client(project=project_id)
    # ... otros métodos y funcionalidades ...

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
    LIMIT 5;
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

# Función para reranking de productos
def rerank_products(prompt, products):
    # Configura el nombre completo del recurso de configuración de ranking
    ranking_config = discovery_client.ranking_config_path(
        project=PROJECT_ID,
        location=LOCATION,
        ranking_config="default_ranking_config",
    )
    
    # Prepara los registros para el ranking
    records = [
        discoveryengine.RankingRecord(
            id=str(index),
            title=product["nombre"],
            content=product["descripcion"] + " " + product["modo_implementacion"]
        )
        for index, product in enumerate(products)
    ]
    
    # Crea la solicitud de ranking
    request = discoveryengine.RankRequest(
        ranking_config=ranking_config,
        model="semantic-ranker-512@latest",
        top_n=5,  # Ajusta según sea necesario
        query=prompt,
        records=records,
    )
    
    # Envía la solicitud de ranking
    response = discovery_client.rank(request=request)  # Cambiado para usar el cliente de discovery
    
    # Procesa la respuesta
    ranked_products = []
    for record in response.records:
        ranked_products.append(products[int(record.id)])
    
    return ranked_products

PROJECT_ID = "dataton-2024-team-01-cofares"  # @param {type:"string"}
LOCATION = "us-central1"  # @param {type:"string"}

# Importa el modelo de Gemini Flash 1.5
import vertexai
vertexai.init(project=PROJECT_ID, location=LOCATION)
from vertexai.generative_models import GenerativeModel

multimodal_model = GenerativeModel("gemini-1.5-flash-001")

# Función para generar una respuesta basada en el contexto
def generate_response(prompt, products):
    # Crear un contexto a partir de los productos obtenidos
    context = "Aquí están los productos encontrados:\n"
    for product in products:
        context += f"- Nombre: {product['nombre']}, Descripción: {product['descripcion']}, Modo de implementación: {product['modo_implementacion']}\n"

    # Formar el prompt para el modelo
    prompt = f"""{context}\nUsando la información relevante del contexto,
    proporciona una respuesta a la consulta: {prompt}.
    Si el contexto no proporciona \
    ninguna información relevante \
    responde con \
    [No he podido encontrar un buen resultado \
    para la consulta en la base de datos] \
    Formatea la respuesta en párrafos claros y, \
    si es relevante, organiza los elementos en listas \
    para que sea más fácil de leer.
    """

    # Generar la respuesta
    response = multimodal_model.generate_content(prompt)

    return response.text

# Asegúrate de que este bloque solo se ejecute si el archivo es ejecutado directamente
#if __name__ == "__main__":
#    # Ejemplo de uso
#    prompt = "producto para el colesterol"
#    products = get_products(prompt)  # Llamar a la función para obtener productos#

    # Imprimir los productos obtenidos
#    print("Productos obtenidos:")
#   for product in products:
#        print(f"Nombre: {product['nombre']}, Descripción: {product['descripcion']}, Modo de implementación: {product['modo_implementacion']}, Distancia: {product['distance_to_query']}")

    # Llamar a la función de reranking
#   ranked_products = rerank_products(prompt, products)

    # Imprimir los productos rankeados
#    print("Productos rankeados:")
#    for product in ranked_products:
#        print(f"Nombre: {product['nombre']}, Distancia: {product['distance_to_query']}")

    # Generar y mostrar la respuesta
#    response_text = generate_response(prompt, products)#
    print(response_text)