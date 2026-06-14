
---

## 🤖 Agent System Architecture & Workflows

Our AI agent solution uses the **Google Agent Development Kit (ADK)** to orchestrate multiple sub-agents in a highly secured, parallelized pipeline. Below are the visual maps of how prompts are authorized, how data is retrieved, and how the multi-agent orchestration generates, refines, and executes queries.

### 📊 Agent Workflow Chart

This flowchart details how requests pass through the application-layer security gateway into the parallel retrieval stage, compile validation loop, refinement logic, and final database execution.

```mermaid
flowchart TD
    %% Styling definitions
    classDef startEnd fill:#1a73e8,stroke:#1557b0,stroke-width:2px,color:#fff;
    classDef agent fill:#f1f3f4,stroke:#dadce0,stroke-width:2px,color:#202124;
    classDef tool fill:#e8f0fe,stroke:#1a73e8,stroke-width:1.5px,color:#1a73e8;
    classDef decision fill:#fef7e0,stroke:#f9ab00,stroke-width:2px,color:#202124;
    classDef route fill:#e6f4ea,stroke:#137333,stroke-width:1.5px,color:#137333;
    classDef error fill:#fce8e6,stroke:#c5221f,stroke-width:1.5px,color:#c5221f;

    START([<b>Start</b><br/>User Prompt]) --> AuthMiddleware{<b>Auth Middleware</b><br/>Starlette BaseHTTP}
    
    AuthMiddleware -->|Unauthorized| Deny[<b>403 Forbidden</b><br/>Reject Request]
    AuthMiddleware -->|Authorized| ParallelStart[<b>Parallel Stage Start</b>]
    
    ParallelStart --> SchemaAgent[<b>Schema Retrieval Agent</b>]
    ParallelStart --> SQLSearchAgent[<b>SQL Retrieval Agent</b>]
    
    SchemaAgent -->|MCP: execute_sql_readonly / VECTOR_SEARCH| BQ_Metadata[(BigQuery Embeddings Table)]
    SQLSearchAgent -->|MCP: execute_sql_readonly / VECTOR_SEARCH| VectorDB[(BigQuery Examples Embeddings Table)]
    
    BQ_Metadata -.-> SchemaAgent
    VectorDB -.-> SQLSearchAgent
    
    SchemaAgent --> JoinNode{<b>Retrieval Join Node</b><br/>JoinNode}
    SQLSearchAgent --> JoinNode
    
    JoinNode --> GenAgent[<b>SQL Generation Agent</b><br/>Write Standard SQL]
    
    GenAgent --> ValAgent[<b>SQL Validation Agent</b>]
    
    ValAgent -->|MCP: execute_sql_readonly LIMIT 0| BQ_DryRun[(BigQuery DryRun Compile)]
    BQ_DryRun -.-> ValAgent
    
    ValAgent --> Router{<b>Validation Router</b><br/>Decision Node}
    
    Router -->|INVALID & attempt < 3| RefineAgent[<b>SQL Refiner Agent</b><br/>Fix Syntax Errors]
    RefineAgent -->|Corrected SQL| ValAgent
    
    Router -->|VALID or attempt >= 3| ExecAgent[<b>SQL Executor Agent</b>]
    
    ExecAgent -->|MCP: execute_sql_readonly| BQ_Execute[(BigQuery Execution)]
    BQ_Execute -.-> ExecAgent
    
    ExecAgent --> FinalOutput([<b>End</b><br/>Render Markdown Table])

    %% Apply classes
    class START,FinalOutput startEnd;
    class SchemaAgent,SQLSearchAgent,GenAgent,ValAgent,RefineAgent,ExecAgent agent;
    class BQ_Metadata,VectorDB,BQ_DryRun,BQ_Execute tool;
    class AuthMiddleware,JoinNode,Router decision;
    class Deny error;
```

### 🔄 Agent Sequence Chart

This sequence diagram illustrates the temporal interactions, parallel processes, back-and-forth validation loops, and security boundaries across the lifetime of a single prompt execution.

```mermaid
sequenceDiagram
    autonumber
    actor User as Authorized User
    participant App as Gemini Enterprise App
    participant Middleware as Auth Middleware
    participant Workflow as BigQuery Pipeline Workflow
    participant SchemaAgent as Schema Retrieval Agent
    participant SQLSearchAgent as SQL Retrieval Agent
    participant External as BigQuery & Vector DB
    participant GenAgent as SQL Generation Agent
    participant ValAgent as SQL Validation Agent
    participant RefineAgent as SQL Refiner Agent
    participant ExecAgent as SQL Executor Agent

    User->>App: Input text prompt / question
    App->>Middleware: Brokered OIDC Request (JWT / Bearer token)
    
    alt Unauthorized User
        Middleware-->>App: 403 Forbidden
        App-->>User: Show authorization error
    else Authorized User
        Middleware->>Workflow: Initiate Workflow with Prompt
        
        par Retrieve Schemas
            Workflow->>SchemaAgent: Prompt / Request context
            SchemaAgent->>External: BQ API: execute_sql_readonly (VECTOR_SEARCH)
            External-->>SchemaAgent: Matched schemas & metadata from embeddings
            SchemaAgent-->>Workflow: tables_schema output
        and Retrieve Few-Shot Examples
            Workflow->>SQLSearchAgent: Prompt / Request context
            SQLSearchAgent->>External: BQ API: execute_sql_readonly (VECTOR_SEARCH)
            External-->>SQLSearchAgent: Similar SQL templates & descriptions from embeddings
            SQLSearchAgent-->>Workflow: dataset_metadata output
        end

        Workflow->>GenAgent: tables_schema + dataset_metadata
        GenAgent-->>Workflow: Generated standard SQL query
        
        loop Validation Loop (Up to 3 attempts)
            Workflow->>ValAgent: Generated SQL query
            ValAgent->>External: BQ API: execute_sql_readonly (LIMIT 0/1 dry-run)
            External-->>ValAgent: Compilation status (SUCCESS or ERROR message)
            ValAgent-->>Workflow: SQLValidationOutput (VALID/INVALID)
            
            alt SQL is INVALID and attempt < 3
                Workflow->>RefineAgent: Incorrect SQL + BQ Error + Attempt number
                RefineAgent-->>Workflow: Corrected SQL query
            else SQL is VALID or attempt == 3
                Note over Workflow: Break loop and route to Execution
            end
        end
        
        Workflow->>ExecAgent: Final SQL query
        ExecAgent->>External: BQ API: execute_sql_readonly (actual execution)
        External-->>ExecAgent: Query result rows
        ExecAgent-->>Workflow: Formatted markdown result table
        Workflow-->>Middleware: Final markdown output
        Middleware-->>App: Authorized HTTP 200 Response
        App-->>User: Display markdown query results & tables
    end
```

### 📖 Step-by-Step Pipeline Execution

The system uses a highly structured, self-correcting multi-agent flow. Here is what happens under the hood during a single user query execution:

#### 1. Ingress & Application-Layer Authentication
* **Trigger**: An authorized user submits a natural-language query to the **Gemini Enterprise App**.
* **Request Route**: The request passes to our Cloud Run container as an HTTP POST request carrying Google-signed OIDC ID tokens.
* **Authentication Middleware**: A custom Starlette `BaseHTTPMiddleware` extracts user emails from identity headers (`X-Goog-Authenticated-User-Email` or through local JWT and Google TokenInfo API decoding).
* **Policy Check**: The email is matched against the `ALLOWED_INVOKERS` environment variable list.
  * *If Unauthorized*: Aborts the request immediately and returns an HTTP `403 Forbidden` response.
  * *If Authorized*: Resolves user identity and forwards the prompt to initiate the `bigquery_pipeline_workflow`.

#### 2. Parallel Context Retrieval
Upon initialization, the workflow launches two parallel branches to retrieve physical and semantic context:
* **Schema Retrieval (`schema_retrieval_agent`)**: Performs a semantic search against the `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings` table using BigQuery's `VECTOR_SEARCH` and regional `get_text_embedding` Remote Function via the `execute_sql_readonly` tool.
* **Semantic SQL Search (`sql_retrieval_agent`)**: Performs a semantic search against the `eikon-dev-ai-team.healthcare_forecasting_jakarta_v2.query_examples_embeddings` table using BigQuery's `VECTOR_SEARCH` and regional `get_text_embedding` Remote Function via the `execute_sql_readonly` tool.

#### 3. Context Merging & SQL Synthesis
* **Joining (`retrieval_join`)**: A specialized `JoinNode` blocks until both parallel retrieval agents complete, gathering their outputs into a single context.
* **Generation (`sql_generation_agent`)**: Fuses the table column structures and matching few-shot examples together. The agent writes a standard BigQuery SQL query matching the exact requirements.

#### 4. Compile-Time Validation & Refinement Loop
Rather than running queries blindly, the system validates the SQL on BigQuery prior to full execution:
* **Dry Run (`sql_validation_agent`)**: Runs a `LIMIT 0` or `LIMIT 1` dry-run check via the BigQuery MCP tool `execute_sql_readonly`. This forces the BigQuery compiler to validate syntax and table structures.
* **Routing Decision (`validation_router`)**:
  * **Success Path**: If the SQL is syntactically correct, the router directs the query to execution (`EXECUTION` route).
  * **Self-Correction Path**: If compilation errors are caught (e.g., column mismatches or missing keywords) and the loop counter is **under 3 attempts**, the router increments the counter and sends the query and compiler logs to the **SQL Refiner Agent** (`REFINEMENT` route).
* **Syntax Refinement (`sql_refiner_agent`)**: Resolves compile-time complaints, updates SQL definitions, and routes the fixed query back to the validation agent for re-compilation.

#### 5. Data Execution & Rendering
* **Execution (`sql_executor_agent`)**: Executes the finalized query against BigQuery.
* **Safety Constraint**: The Executor has strict instructions restricting operations solely to BigQuery read-only calls.
* **Formatting**: Translates raw database rows into a clean, markdown-formatted tables/results representation, which cascades back through the authentication gateway and renders directly in the user's Gemini Enterprise interface.

## Example Prompts & Indexed Questions

The workspace includes a set of 11 curated example prompts (stored in `sql_examples.json` and ingested into the vector database) to teach the SQL agent how to answer queries about the Jakarta healthcare dataset.