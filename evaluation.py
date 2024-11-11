
#Source: https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/evaluation/evaluate_rag_gen_ai_evaluation_service_sdk.ipynb

import vertexai
import inspect
import logging
import warnings

# General
from IPython.display import HTML, Markdown, display
import pandas as pd
import plotly.graph_objects as go

# Main
from vertexai.evaluation import EvalTask, MetricPromptTemplateExamples, PointwiseMetric


# Configuración del cliente de Vertex AI
PROJECT_ID = "dataton-2024-team-01-cofares"
LOCATION = "us-central1"
EXPERIMENT = "rag-eval-01"

vertexai.init(project=PROJECT_ID, location=LOCATION)

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# ----------------------Helper functions----------------------

def print_doc(function):
    print(f"{function.__name__}:\n{inspect.getdoc(function)}\n")


def display_eval_report(eval_result, metrics=None):
    """Display the evaluation results."""

    title, summary_metrics, report_df = eval_result
    metrics_df = pd.DataFrame.from_dict(summary_metrics, orient="index").T
    if metrics:
        metrics_df = metrics_df.filter(
            [
                metric
                for metric in metrics_df.columns
                if any(selected_metric in metric for selected_metric in metrics)
            ]
        )
        report_df = report_df.filter(
            [
                metric
                for metric in report_df.columns
                if any(selected_metric in metric for selected_metric in metrics)
            ]
        )

    # Display the title with Markdown for emphasis
    display(Markdown(f"## {title}"))

    # Display the metrics DataFrame
    display(Markdown("### Summary Metrics"))
    display(metrics_df)

    # Display the detailed report DataFrame
    display(Markdown("### Report Metrics"))
    display(report_df)


def display_explanations(df, metrics=None, n=1):
    style = "white-space: pre-wrap; width: 800px; overflow-x: auto;"
    df = df.sample(n=n)
    if metrics:
        df = df.filter(
            ["instruction", "context", "reference", "completed_prompt", "response"]
            + [
                metric
                for metric in df.columns
                if any(selected_metric in metric for selected_metric in metrics)
            ]
        )

    for index, row in df.iterrows():
        for col in df.columns:
            display(HTML(f"{col}: {row[col]}"))
        display(HTML(""))


def plot_radar_plot(eval_results, max_score=5, metrics=None):
    fig = go.Figure()

    for eval_result in eval_results:
        title, summary_metrics, report_df = eval_result

        if metrics:
            summary_metrics = {
                k: summary_metrics[k]
                for k, v in summary_metrics.items()
                if any(selected_metric in k for selected_metric in metrics)
            }

        fig.add_trace(
            go.Scatterpolar(
                r=list(summary_metrics.values()),
                theta=list(summary_metrics.keys()),
                fill="toself",
                name=title,
            )
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max_score])), showlegend=True
    )

    fig.show()


def plot_bar_plot(eval_results, metrics=None):
    fig = go.Figure()
    data = []

    for eval_result in eval_results:
        title, summary_metrics, _ = eval_result
        if metrics:
            summary_metrics = {
                k: summary_metrics[k]
                for k, v in summary_metrics.items()
                if any(selected_metric in k for selected_metric in metrics)
            }

        data.append(
            go.Bar(
                x=list(summary_metrics.keys()),
                y=list(summary_metrics.values()),
                name=title,
            )
        )

    fig = go.Figure(data=data)

    # Change the bar mode
    fig.update_layout(barmode="group")
    fig.show()
     
# ----------------------Dataset----------------------

"""To evaluate the RAG generated answers,
the evaluation dataset is required to contain the following fields:

Prompt: The user supplied prompt consisting of the User Question and the RAG Retrieved Context
Response: The RAG Generated Answer

Your dataset must include a minimum of one evaluation example.
We recommend around 100 examples to ensure high-quality aggregated metrics
and statistically significant results."""

#El siguiente template a sido generado con Gemini a modo de ejemplo de implementación

import pandas as pd

# Ejemplos de preguntas de los usuarios
questions = [
    "Busco una crema para las estrías",
    "Necesito un suplemento de vitamina D para personas mayores",
    "¿Tienes algún producto para la caída del cabello?",
    "Quiero una crema hidratante para piel sensible",
    "¿Hay algún spray nasal para alergias?"
]

# Contexto recuperado por el sistema RAG (simulación de descripciones de productos relevantes)
retrieved_contexts = [
    "CREMA ACEITE ROSA MOSQU 50ML: Contiene aceite de rosa mosqueta, ideal para mejorar la apariencia de estrías. Pack Uresim Serum Ác.Hialurónico: hidrata y mejora la elasticidad de la piel.",
    "Vitamina D3 1000 IU: formulado especialmente para personas mayores, ayuda a mejorar la salud ósea. CalciD3: suplemento combinado de calcio y vitamina D para fortalecer huesos.",
    "Shampoo anti-caída con biotina: fortalece el cabello y reduce la caída. Tónico capilar de romero: revitaliza el cuero cabelludo y favorece el crecimiento.",
    "Crema hidratante Avène para piel sensible: reduce rojeces e hidrata profundamente. Eucerin UltraSENSITIVE: fórmula calmante para piel reactiva.",
    "Spray nasal antialérgico con azelastina: alivia los síntomas de alergia. Rhinomer Fuerza Suave: spray de agua de mar para limpiar fosas nasales y reducir congestión."
]

# Respuestas generadas por el sistema RAG
generated_answers = [
    "Aquí tienes opciones: CREMA ACEITE ROSA MOSQU 50ML, ideal para estrías, y Pack Uresim Serum Ác.Hialurónico, que mejora la elasticidad de la piel.",
    "Te recomiendo Vitamina D3 1000 IU y CalciD3, ambos beneficiosos para la salud ósea en personas mayores.",
    "Para la caída del cabello, prueba el shampoo con biotina y el tónico de romero para fortalecer y revitalizar.",
    "Para piel sensible, puedes utilizar Avène o Eucerin UltraSENSITIVE, ambas hidratantes calmantes.",
    "Disponemos de spray nasal con azelastina para alergias y Rhinomer Fuerza Suave para descongestionar."
]

# Creación del DataFrame para el dataset de evaluación
eval_dataset = pd.DataFrame(
    {
        "prompt": [
            "Consulta: " + question + " Contexto: " + context
            for question, context in zip(questions, retrieved_contexts)
        ],
        "response": generated_answers,
    }
)

# Mostrar el dataset de evaluación
eval_dataset

# ----------------------Metricas----------------------

"""Select and create metrics
You can run evaluation for just one metric, or a combination of metrics.
For this example, we select a few RAG-related predefined metrics, and create a few of our own custom metrics."""

# Explore predefined metrics: https://cloud.google.com/vertex-ai/generative-ai/docs/models/metrics-templates
# See all the available metric examples MetricPromptTemplateExamples.list_example_metric_names()

