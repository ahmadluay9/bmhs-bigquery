import os
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk import Workflow, Event, Context
from google.adk.workflow import JoinNode
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

import google.auth
import google.auth.transport.requests
from google.genai import types
from google.genai.models import Models, AsyncModels

# ---------------------------------------------------------
# Monkey-patch to fix Google GenAI SDK part_metadata issue
# ---------------------------------------------------------
def _strip_part_metadata(obj):
    """Recursively strip part_metadata from any Part object or dictionary to prevent ValueError in Vertex AI mode."""
    if obj is None:
        return
    if hasattr(obj, "part_metadata"):
        try:
            obj.part_metadata = None
        except Exception:
            pass
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _strip_part_metadata(item)
    if hasattr(obj, "parts"):
        _strip_part_metadata(getattr(obj, "parts"))
    if isinstance(obj, dict):
        if "part_metadata" in obj:
            obj["part_metadata"] = None
        for key, val in obj.items():
            _strip_part_metadata(val)

# Save original methods
_orig_sync_gen = Models.generate_content
_orig_sync_gen_stream = Models.generate_content_stream
_orig_async_gen = AsyncModels.generate_content
_orig_async_gen_stream = AsyncModels.generate_content_stream

def patched_sync_gen(self, *args, **kwargs):
    if "contents" in kwargs:
        _strip_part_metadata(kwargs["contents"])
    elif len(args) > 1:
        args_list = list(args)
        _strip_part_metadata(args_list[1])
        args = tuple(args_list)
    return _orig_sync_gen(self, *args, **kwargs)

def patched_sync_gen_stream(self, *args, **kwargs):
    if "contents" in kwargs:
        _strip_part_metadata(kwargs["contents"])
    elif len(args) > 1:
        args_list = list(args)
        _strip_part_metadata(args_list[1])
        args = tuple(args_list)
    return _orig_sync_gen_stream(self, *args, **kwargs)

async def patched_async_gen(self, *args, **kwargs):
    if "contents" in kwargs:
        _strip_part_metadata(kwargs["contents"])
    elif len(args) > 1:
        args_list = list(args)
        _strip_part_metadata(args_list[1])
        args = tuple(args_list)
    return await _orig_async_gen(self, *args, **kwargs)

async def patched_async_gen_stream(self, *args, **kwargs):
    if "contents" in kwargs:
        _strip_part_metadata(kwargs["contents"])
    elif len(args) > 1:
        args_list = list(args)
        _strip_part_metadata(args_list[1])
        args = tuple(args_list)
    return await _orig_async_gen_stream(self, *args, **kwargs)

# Apply patches
Models.generate_content = patched_sync_gen
Models.generate_content_stream = patched_sync_gen_stream
AsyncModels.generate_content = patched_async_gen
AsyncModels.generate_content_stream = patched_async_gen_stream

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------
# Dynamic Authentication and Configurations
# ---------------------------------------------------------

# Retry configuration for LLM calls
retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,  # Initial delay before first retry (in seconds)
    http_status_codes=[429, 500, 503, 504]  # Retry on these HTTP errors
)

def get_bq_access_headers():
    """Dynamically fetch OAuth2 access token for BigQuery API calls."""
    try:
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
        return {"Authorization": f"Bearer {credentials.token}"}
    except Exception as e:
        print(f"Warning: Failed to load Google Application Default Credentials: {e}")
        return {}

bq_access_headers = get_bq_access_headers()

# ---------------------------------------------------------
# Data Schemas (Pydantic Models) for Pipeline Nodes
# ---------------------------------------------------------

class SchemaRetrievalOutput(BaseModel):
    tables_schema: str = Field(description="Summary of the relevant table schemas and columns.")

class SQLRetrievalOutput(BaseModel):
    dataset_metadata: str = Field(description="Summary of the dataset descriptions and metadata.")

class SQLGenerationInput(BaseModel):
    schema_retrieval_agent: SchemaRetrievalOutput
    sql_retrieval_agent: SQLRetrievalOutput

class SQLQuery(BaseModel):
    sql: str = Field(description="The standard BigQuery SQL query.")

class SQLValidationOutput(BaseModel):
    status: str = Field(description="VALID or INVALID status of the query.")
    sql: str = Field(description="The validated SQL query.")
    error: Optional[str] = Field(default=None, description="The compilation error from BigQuery, if INVALID.")

class SQLRefinementInput(BaseModel):
    sql: str = Field(description="The SQL query that failed validation.")
    error: str = Field(description="The compilation or execution error from BigQuery.")
    attempt: int = Field(description="The current validation loop attempt number.")

class SQLExecutionInput(BaseModel):
    sql: str = Field(description="The validated SQL query to execute.")

# ---------------------------------------------------------
# Workflow Nodes Definitions
# ---------------------------------------------------------

# 1. Schema Retrieval Agent
schema_retrieval_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="schema_retrieval_agent",
    output_schema=SchemaRetrievalOutput,
    instruction=(
        "Anda adalah Schema Retrieval Agent. Tanggung jawab utama Anda adalah mengambil detail skema BigQuery untuk tabel yang relevan dengan permintaan pengguna.\n"
        "Untuk menemukan tabel yang relevan, lakukan pencarian semantik pada tabel `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings` menggunakan tool `execute_sql_readonly`.\n"
        "Anda harus menjalankan kueri VECTOR_SEARCH untuk menemukan dokumen skema yang paling relevan. Sebagai contoh:\n"
        "SELECT base.content, distance\n"
        "FROM VECTOR_SEARCH(\n"
        "  TABLE `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings`,\n"
        "  'embedding',\n"
        "  query_value => ARRAY(\n"
        "    SELECT LAX_FLOAT64(val) \n"
        "    FROM UNNEST(\n"
        "      JSON_QUERY_ARRAY(\n"
        "        `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.get_text_embedding`('<highly_descriptive_search_query_based_on_user_request>')\n"
        "      )\n"
        "    ) AS val\n"
        "  ),\n"
        "  top_k => 3,\n"
        "  distance_type => 'COSINE'\n"
        ") AS base\n"
        "ORDER BY distance ASC;\n\n"
        "Pastikan `<highly_descriptive_search_query_based_on_user_request>` adalah kueri pencarian deskriptif yang mencerminkan tabel, kolom, atau konsep klinis yang diminta.\n"
        "Berikan ringkasan yang jelas dan mendetail tentang skema, tabel, kolom, dan tipe data yang cocok yang ditemukan pada kolom 'content' dari hasil pencarian ke dalam bidang output 'tables_schema'."
    ),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://bigquery.googleapis.com/mcp",
                headers=bq_access_headers,
            ),
            tool_filter=["execute_sql_readonly"]
        )
    ],
)

# 2. SQL Retrieval Agent
sql_retrieval_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="sql_retrieval_agent",
    output_schema=SQLRetrievalOutput,
    instruction=(
        "Anda adalah SQL Retrieval Agent. Tanggung jawab utama Anda adalah mengambil contoh kueri SQL relevan yang telah terindeks sebelumnya untuk memandu proses pembuatan SQL.\n"
        "Untuk menemukan contoh kueri yang relevan, lakukan pencarian semantik pada tabel `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.query_examples_embeddings` menggunakan tool `execute_sql_readonly`.\n"
        "Anda harus menjalankan kueri VECTOR_SEARCH untuk menemukan dokumen contoh SQL yang paling relevan. Sebagai contoh:\n"
        "SELECT base.content, distance\n"
        "FROM VECTOR_SEARCH(\n"
        "  TABLE `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.query_examples_embeddings`,\n"
        "  'embedding',\n"
        "  query_value => ARRAY(\n"
        "    SELECT LAX_FLOAT64(val) \n"
        "    FROM UNNEST(\n"
        "      JSON_QUERY_ARRAY(\n"
        "        `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.get_text_embedding`('<highly_descriptive_search_query_based_on_user_request>')\n"
        "      )\n"
        "    ) AS val\n"
        "  ),\n"
        "  top_k => 5,\n"
        "  distance_type => 'COSINE'\n"
        ") AS base\n"
        "ORDER BY distance ASC;\n\n"
        "Pastikan `<highly_descriptive_search_query_based_on_user_request>` adalah kueri pencarian deskriptif yang mencerminkan permintaan data pengguna.\n"
        "Berikan daftar contoh SQL yang jelas dan mendetail serta deskripsinya yang ditemukan pada kolom 'content' dari hasil pencarian ke dalam bidang output 'dataset_metadata' agar SQL Generation Agent dapat mereplikasi strukturnya."
    ),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://bigquery.googleapis.com/mcp",
                headers=bq_access_headers,
            ),
            tool_filter=["execute_sql_readonly"]
        )
    ],
)

# 3. Retrieval Stage Parallel Join Node
retrieval_join = JoinNode(name="retrieval_join")

# 4. SQL Generation Agent
sql_generation_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="sql_generation_agent",
    input_schema=SQLGenerationInput,
    output_schema=SQLQuery,
    instruction=(
        "Anda adalah SQL Generation Agent.\n"
        "Tugas Anda adalah menghasilkan kueri SQL BigQuery standar yang valid untuk menjawab permintaan pengguna berdasarkan skema dan metadata yang disediakan di bawah ini.\n\n"
        "Informasi Skema:\n"
        "{SQLGenerationInput.schema_retrieval_agent.tables_schema}\n\n"
        "Metadata Dataset:\n"
        "{SQLGenerationInput.sql_retrieval_agent.dataset_metadata}\n\n"
        "Pastikan kueri yang dihasilkan adalah SQL standar dan berhasil dieksekusi.\n"
        "Keluarkan HANYA kueri SQL di dalam kolom output 'sql' pada skema."
    ),
)

# 5. SQL Validation Agent
sql_validation_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="sql_validation_agent",
    input_schema=SQLQuery,
    output_schema=SQLValidationOutput,
    instruction=(
        "Anda adalah SQL Validation Agent. Tugas Anda adalah memvalidasi apakah kueri SQL yang diberikan sudah benar, valid secara sintaksis, dan sesuai dengan skema yang diambil.\n"
        "Kueri SQL yang akan divalidasi adalah:\n"
        "{SQLQuery.sql}\n\n"
        "Untuk memvalidasi kueri tersebut, eksekusi kueri dengan tambahan `LIMIT 1` atau `LIMIT 0` menggunakan tool `execute_sql_readonly`. Hal ini memastikan BigQuery mengompilasi dan memverifikasinya tanpa memproses volume data yang besar.\n"
        "Jika eksekusi berhasil, isi kolom output sebagai:\n"
        "- status: 'VALID'\n"
        "- sql: '<the_sql_query>'\n"
        "- error: None\n\n"
        "Jika eksekusi gagal, isi kolom output sebagai:\n"
        "- status: 'INVALID'\n"
        "- sql: '<the_sql_query>'\n"
        "- error: '<pesan kesalahan kompilasi eksak dari BigQuery>'"
    ),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://bigquery.googleapis.com/mcp",
                headers=bq_access_headers,
            ),
            tool_filter=["execute_sql_readonly"]
        )
    ],
)

# 6. SQL Validation Router Node (Issues Found Decision & Max 3 Iteration Counter)
def validation_router(ctx: Context, node_input: SQLValidationOutput) -> Event:
    """Routes the workflow based on validation results and limits the loop to 3 iterations."""
    current_count = ctx.state.get("validation_loop_count", 0)
    
    if node_input.status.upper() == "VALID":
        ctx.state["validation_loop_count"] = 0
        return Event(route="EXECUTION", output=SQLExecutionInput(sql=node_input.sql))
    
    if current_count < 3:
        ctx.state["validation_loop_count"] = current_count + 1
        print(f"[Validation Router] Validation failed (Attempt {current_count + 1}/3). Error: {node_input.error}. Routing to Refiner...")
        return Event(
            route="REFINEMENT",
            output=SQLRefinementInput(
                sql=node_input.sql,
                error=node_input.error or "Unknown BigQuery compilation error.",
                attempt=current_count + 1
            )
        )
    else:
        print("[Validation Router] Max validation attempts reached. Proceeding to execution with best-effort SQL...")
        ctx.state["validation_loop_count"] = 0
        return Event(route="EXECUTION", output=SQLExecutionInput(sql=node_input.sql))

# 7. SQL Refiner Agent
sql_refiner_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="sql_refiner_agent",
    input_schema=SQLRefinementInput,
    output_schema=SQLQuery,
    instruction=(
        "Anda adalah SQL Refiner Agent. Tugas Anda adalah memperbaiki kueri SQL yang gagal dalam proses validasi.\n"
        "Berikut adalah kueri SQL yang salah:\n"
        "{SQLRefinementInput.sql}\n\n"
        "Berikut adalah kesalahan kompilasi atau waktu jalan eksak dari BigQuery:\n"
        "{SQLRefinementInput.error}\n\n"
        "Ini adalah percobaan ke-{SQLRefinementInput.attempt} dari 3.\n\n"
        "Analisis SQL dan kesalahan tersebut secara cermat. Perbaiki sintaksis, referensi tabel, nama kolom, atau join sesuai petunjuk dari pesan kesalahan.\n"
        "Keluarkan HANYA kueri SQL hasil perbaikan di dalam kolom output 'sql' pada skema."
    ),
)

# 8. SQL Executor Agent
sql_executor_agent = Agent(
    model=Gemini(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        retry_options=retry_config
    ),
    name="sql_executor_agent",
    input_schema=SQLExecutionInput,
    instruction=(
        "Anda adalah SQL Executor Agent. Tugas Anda adalah mengeksekusi kueri SQL final yang telah divalidasi dan menyajikan hasilnya.\n"
        "Berikut adalah kueri SQL tervalidasi yang akan dijalankan:\n"
        "{SQLExecutionInput.sql}\n\n"
        "Gunakan tool `execute_sql_readonly` untuk mengeksekusi kueri ini di BigQuery.\n"
        "Format hasil kueri akhir ke dalam tabel markdown yang bersih, profesional, dan menarik secara visual.\n"
        "BATASAN KETAT: Anda HANYA boleh menangani operasi BigQuery dan pelaporan hasil kueri. "
        "Anda sama sekali tidak diperbolehkan melakukan operasi atau integrasi di luar cakupan database BigQuery. Cukup sajikan wawasan data yang diminta."
    ),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://bigquery.googleapis.com/mcp",
                headers=bq_access_headers,
            ),
            tool_filter=["execute_sql_readonly"]
        )
    ],
)

# Nested BigQuery Orchestration Workflow Node
bigquery_workflow = Workflow(
    name="bigquery_pipeline_workflow",
    edges=[
        ("START", schema_retrieval_agent),
        ("START", sql_retrieval_agent),
        (schema_retrieval_agent, retrieval_join),
        (sql_retrieval_agent, retrieval_join),
        (retrieval_join, sql_generation_agent),
        (sql_generation_agent, sql_validation_agent),
        (sql_validation_agent, validation_router),
        (validation_router, {
            "REFINEMENT": sql_refiner_agent,
            "EXECUTION": sql_executor_agent
        }),
        (sql_refiner_agent, sql_validation_agent),
    ]
)

# Export as root_agent for the ADK loading entrypoint
root_agent = bigquery_workflow

# Patch sub_agents attribute for all workflows to satisfy ADK AgentCardBuilder
object.__setattr__(root_agent, 'sub_agents', [
    bigquery_workflow
])

# Patch sub_agents attribute for BigQuery workflow to satisfy ADK AgentCardBuilder
object.__setattr__(bigquery_workflow, 'sub_agents', [
    schema_retrieval_agent,
    sql_retrieval_agent,
    sql_generation_agent,
    sql_validation_agent,
    sql_refiner_agent,
    sql_executor_agent
])

current_dir = os.path.dirname(os.path.abspath(__file__))
agent_card_path = os.path.join(current_dir, 'agent-card.json')
app_port = int(os.environ.get("PORT", 10001))

a2a_app = to_a2a(
                root_agent, 
                port=app_port,
                agent_card=agent_card_path
                 )

# ---------------------------------------------------------
# Application-Layer User Authorization Middleware
# ---------------------------------------------------------
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")

class AuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        headers = dict(request.headers)
        
        # Extract email from Google user authentication headers
        user_email = None
        for key, val in headers.items():
            if key.lower() in ["x-goog-authenticated-user-email", "x-goog-user-email", "x-authenticated-user-email"]:
                # Standard header prefix is 'accounts.google.com:email'
                if ":" in val:
                    user_email = val.split(":")[-1].strip()
                else:
                    user_email = val.strip()
                break

        # Fallback: Extract from standard Authorization header (Google token from Gemini Enterprise broker)
        if not user_email:
            for key, val in headers.items():
                if key.lower() == "authorization":
                    if val.lower().startswith("bearer "):
                        token = val.split(" ", 1)[1].strip()
                        
                        # Log token details for diagnostics (length and prefix, NO sensitive signatures)
                        token_len = len(token)
                        token_prefix = token[:10] if token_len >= 10 else token
                        logger.info(f"[Auth Middleware] Diagnosing Authorization token: len={token_len}, prefix='{token_prefix}'")
                        
                        # Attempt 1: Local JWT decoding (only if it's actually a JWT starting with eyJ)
                        if token.startswith("eyJ"):
                            try:
                                parts = token.split(".")
                                if len(parts) == 3:
                                    payload = parts[1]
                                    payload += "=" * ((4 - len(payload) % 4) % 4)
                                    import base64
                                    import json
                                    decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
                                    payload_dict = json.loads(decoded)
                                    user_email = payload_dict.get("email")
                                    if user_email:
                                        logger.info(f"[Auth Middleware] Extracted email from local JWT: {user_email}")
                            except Exception as e:
                                logger.error(f"[Auth Middleware] Local JWT decode failed: {e}")
                        
                        # Attempt 2: Google TokenInfo API (fallback for OAuth Access Tokens or other Google tokens)
                        if not user_email:
                            import urllib.request
                            import urllib.parse
                            import json
                            
                            # Try as access token first
                            try:
                                url = f"https://oauth2.googleapis.com/tokeninfo?access_token={urllib.parse.quote(token)}"
                                req = urllib.request.Request(url, method="GET")
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    data = json.loads(response.read().decode("utf-8"))
                                    user_email = data.get("email")
                                    if user_email:
                                        logger.info(f"[Auth Middleware] Extracted email from TokenInfo (access_token): {user_email}")
                            except Exception as e:
                                logger.debug(f"[Auth Middleware] TokenInfo as access_token failed: {e}")
                                
                            # Try as ID token fallback
                            if not user_email:
                                try:
                                    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(token)}"
                                    req = urllib.request.Request(url, method="GET")
                                    with urllib.request.urlopen(req, timeout=5) as response:
                                        data = json.loads(response.read().decode("utf-8"))
                                        user_email = data.get("email")
                                        if user_email:
                                            logger.info(f"[Auth Middleware] Extracted email from TokenInfo (id_token): {user_email}")
                                except Exception as e:
                                    logger.debug(f"[Auth Middleware] TokenInfo as id_token failed: {e}")
                    break

        # Sanitize headers to protect secrets/tokens while printing everything else
        sanitized_headers = {
            k: ("[REDACTED]" if k.lower() in ("authorization", "cookie", "x-goog-api-key") else v)
            for k, v in headers.items()
        }
        
        logger.info(f"[Auth Middleware] Incoming Request: {method} {path}")
        logger.info(f"[Auth Middleware] Sanitized Headers: {sanitized_headers}")
        logger.info(f"[Auth Middleware] Extracted User Email: {user_email}")
        
        # Enforce authorization for all POST requests (actual agent execution calls)
        if method == "POST":
            # Retrieve allowed invokers list dynamically from environment variables
            allowed_invokers_env = os.environ.get("ALLOWED_INVOKERS")
            
            # Clean up potential surrounding square brackets [] if passed as a string list representation
            cleaned_env = allowed_invokers_env.strip().lstrip("[").rstrip("]")
            
            allowed_users = set()
            for invoker in cleaned_env.split(","):
                # Strip leading/trailing spaces and potential quotes (' or ")
                invoker = invoker.strip().strip("'").strip('"')
                if invoker.startswith("user:"):
                    allowed_users.add(invoker.replace("user:", "").strip().lower())
            
            if not user_email:
                logger.error("[Auth Middleware] Denied: Missing user email authentication header.")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden: Request is missing user authentication headers."}
                )
                
            if user_email.lower() not in allowed_users:
                logger.error(f"[Auth Middleware] Denied: User '{user_email}' is not authorized.")
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Forbidden: User '{user_email}' is not authorized."}
                )
                
            logger.info(f"[Auth Middleware] Allowed: User '{user_email}' is authorized.")

        response = await call_next(request)
        return response

a2a_app.add_middleware(AuthorizationMiddleware)