from boring_semantic_layer import MCPSemanticModel
from semantic_model import build_models
from ga4_semantic_model import build_ga4_model

models = {**build_models(), **build_ga4_model()}

server = MCPSemanticModel(
    models=models,
    name="Multi-Source Semantic Layer (Shopify + GA4)",
)

if __name__ == "__main__":
    server.run(transport="http", host="127.0.0.1", port=8000)