from google.cloud import bigquery, discoveryengine_v1 as discoveryengine
from vertexai.preview.generative_models import GenerativeModel, Tool, FunctionDeclaration, AutomaticFunctionCallingResponder

import vertexai
from vertexai.generative_models import (
    FunctionDeclaration,
    Tool,
    GenerativeModel,
    AutomaticFunctionCallingResponder
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
        LIMIT 5;
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
        self.multimodal_model = GenerativeModel("gemini-1.5-flash-001")

    def process_query(self, prompt):
        # Define Function Declarations for Gemini to understand available tools
        function_declarations = [
            FunctionDeclaration(
                name="product_query",
                description="Fetches relevant product information from the database based on the query.",
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
        ]

        # Define Tool instance with the get_products function
        tool = Tool(
            function=self.bigquery_client.get_products,
            function_declaration=function_declarations[0]
        )

        # Build the prompt to clarify the user's intent
        formatted_prompt = f"""
        Consulta recibida de un farmacéutico:
        "{prompt}"
        Responde de la siguiente manera:
        - Si es una solicitud de búsqueda de producto, usa 'product_query' y activa la función de búsqueda.
        - Si es un saludo, responde con un saludo.
        - Si requiere más detalles, responde con 'clarify_request'.
        """

        # Use Gemini to interpret the intent and potentially call functions as needed
        response = self.multimodal_model.generate_content(
            formatted_prompt,
            tools=[tool],
            automatic_function_calling=AutomaticFunctionCallingResponder.AUTO
        )

        # Handle the output based on the response's intent
        if response.tool == "product_query":
            products = response.tool_call_args.get("results", [])
            if not products:
                return "Lo siento, no encontré ningún producto que coincida con la búsqueda."
            ranked_products = self.bigquery_client.rerank_products(prompt, products)
            return self.generate_response(prompt, ranked_products)

        elif 'clarify_request' in response.text:
            return "¿Podrías proporcionar más detalles sobre el producto que buscas?"

        return response.text if response.text else "Lo siento, no pude procesar tu solicitud."

    def generate_response(self, prompt, products):
        if not products:
            return "Lo siento, no encontré ningún producto que coincida con la búsqueda."
        
        response = "Aquí están algunos productos relevantes:\n"
        for product in products:
            response += f"- Nombre: {product['nombre']}, Descripción: {product['descripcion']}\n"
        return response