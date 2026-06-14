import json
import os
import functions_framework

# Mengatur environment variables agar SDK menggunakan Vertex AI (Enterprise) di region us-central1
os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = "eikon-dev-ai-team"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

from google import genai
from google.genai.types import EmbedContentConfig

# Inisialisasi client Google Gen AI SDK
client = genai.Client()

@functions_framework.http
def get_vertex_embeddings(request):
    """
    Cloud Function HTTP yang menerima payload batch dari BigQuery Remote Function,
    meminta text embedding menggunakan SDK google-genai terbaru ke Vertex AI,
    dan mengembalikan hasilnya kembali ke BigQuery.
    """
    try:
        request_json = request.get_json(silent=True)
        if not request_json or "calls" not in request_json:
            return json.dumps({"replies": []}), 400, {"Content-Type": "application/json"}

        calls = request_json.get("calls", [])
        replies = []

        # BigQuery mengirimkan data dalam bentuk batch (array di dalam array)
        # Ambil teks yang akan diekstrak embedding-nya
        texts_to_embed = [call[0] for call in calls if call and len(call) > 0]
        
        if not texts_to_embed:
            return json.dumps({"replies": []}), 200, {"Content-Type": "application/json"}

        # Membaca konfigurasi dinamis yang dikirimkan oleh BQ Remote Function (userDefinedContext)
        user_context = request_json.get("userDefinedContext", {})
        model_name = user_context.get("model", "gemini-embedding-001")
        output_dim_str = user_context.get("output_dimensionality", "768")
        
        try:
            output_dim = int(output_dim_str)
        except ValueError:
            output_dim = 768

        # Melakukan panggilan batch embedding ke model gemini-embedding-001
        response = client.models.embed_content(
            model=model_name,
            contents=texts_to_embed,
            config=EmbedContentConfig(
                output_dimensionality=output_dim
            )
        )

        # Memetakan hasil vektor kembali ke format balasan BigQuery
        if response.embeddings:
            for embedding in response.embeddings:
                replies.append(embedding.values)
        else:
            raise Exception("Model tidak mengembalikan data embedding.")

        # Mengembalikan response berformat JSON yang diharapkan oleh BigQuery
        return json.dumps({"replies": replies}), 200, {"Content-Type": "application/json"}

    except Exception as e:
        # Mengembalikan pesan error ke log BigQuery jika terjadi kendala teknis
        return json.dumps({"errorMessage": str(e)}), 400, {"Content-Type": "application/json"}