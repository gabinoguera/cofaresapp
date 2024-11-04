from google.cloud import bigquery, discoveryengine_v1 as discoveryengine
import vertexai
from vertexai.generative_models import (
    FunctionDeclaration,
    Tool,
    GenerativeModel
)

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
client = bigquery.Client(project=project_id)

# Vertex AI configuration
PROJECT_ID = "dataton-2024-team-01-cofares"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)
multimodal_model = GenerativeModel("gemini-1.5-flash-001")

# Discovery Engine configuration
discovery_client = discoveryengine.RankServiceClient()

class BigQueryClient:
    def __init__(self, project_id):
        self.client = bigquery.Client(project=project_id)

    def get_products(self, prompt):
        query = """
        WITH QueryEmbedding AS (
          SELECT ml_generate_embedding_result AS query_embedding
          FROM ML.GENERATE_EMBEDDING(
            MODEL `dataton-2024-team-01-cofares.datos_cofares.text_embedding`,
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
          ML.DISTANCE(qe.query_embedding, e.ml_generate_embedding_result, 'COSINE') AS distance_to_query
        FROM `dataton-2024-team-01-cofares.datos_cofares.data_final_temp` AS d
        INNER JOIN `dataton-2024-team-01-cofares.datos_cofares.SalidaEmbeddings_temp` AS e
          ON d.codigo_web = e.title
        INNER JOIN QueryEmbedding AS qe ON TRUE
        ORDER BY distance_to_query
        LIMIT 10;
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prompt", "STRING", prompt)
            ]
        )
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()

        if not results:
            return []

        products = [
            {
                "codigo_web": row.codigo_web,
                "nombre": row.nombre,
                "codigo_nacional": row.codigo_nacional,
                "descripcion": row.descripcion or "-",
                "modo_implementacion": row.modo_implementacion or "-",
                "imagen_url": row.URI_primera_imagen,
                "distance_to_query": row.distance_to_query
            } for row in results
        ]
        return products

    def rerank_products(self, prompt, products):
        ranking_config = discovery_client.ranking_config_path(
            project=PROJECT_ID, location=LOCATION, ranking_config="default_ranking_config"
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
            top_n=5,
            query=prompt,
            records=records,
        )
        response = discovery_client.rank(request=request)
        ranked_products = [products[int(record.id)] for record in response.records]
        return ranked_products


class QueryManager:
    def __init__(self, project_id):
        self.bigquery_client = BigQueryClient(project_id)
        self.multimodal_model = multimodal_model

    def process_query(self, prompt):
        # Define the function declaration
        function_declaration = FunctionDeclaration(
            name="product_query",
            description="Retrieves product information from the database based on the query.",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The query text for the product search"
                    }
                },
                "required": ["prompt"]
            }
        )

        # Create the tool with the function_declaration
        tool = Tool(function_declarations=[function_declaration])

        # Update prompt for clarity and specific instructions
        formatted_prompt = f"""
        Consulta recibida de un farmacéutico:
        "{prompt}"
        Responde de la siguiente manera:
        - Si el usuario pregunta por un producto o hace una solicitud específica sobre productos, usa 'product_query' para activar la función de búsqueda.
        - Si el usuario solo está saludando o hace una pregunta general, responde de manera adecuada y no actives la función de búsqueda.
        - Si no comprendes completamente la consulta, responde con 'clarify_request' para pedir más detalles.
        """

        # Generate the response using tools and function declarations
        response = self.multimodal_model.generate_content(
            formatted_prompt,
            tools=[tool]
        )

        # Check if a function was called and handle it
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call and function_call.name == "product_query":
            # Only proceed with product search if the model's response indicates it's a product query
            products = self.bigquery_client.get_products(prompt)
            if not products:
                return "Lo siento, no encontré ningún producto que coincida con la búsqueda."
            ranked_products = self.bigquery_client.rerank_products(prompt, products)
            return self.generate_response(prompt, ranked_products)

        elif 'clarify_request' in response.text:
            return "¿Podrías proporcionar más detalles sobre el producto que buscas?"

        # If the response is a general greeting or other reply, return it directly
        return response.text if response.text else "Lo siento, no pude procesar tu solicitud."

    def generate_response(self, prompt, products):
        if not products:
            return "Lo siento, no encontré ningún producto que coincida con la búsqueda."
        
        response = "Aquí están algunos productos relevantes:\n"
        for product in products:
            response += f"- Nombre: {product['nombre']}, Descripción: {product['descripcion']}\n"
        return response