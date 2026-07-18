# rag brain 

`rag brain` is a FastAPI service for document ingestion, retrieval, and
retrieval-augmented question answering. It ingests documents into a searchable
knowledge base with LlamaIndex + Chroma and exposes a small API for downstream
apps and workflows.

## Core features

- FastAPI endpoints under `/api/v1` for document ingestion and question answering.
- JWT-based auth endpoints under `/api/v1/auth` for local register/login/me flows.
- Text-based PDF ingestion that can chunk documents into sentence windows, build
  embeddings, and index content into Chroma.
- Hybrid retrieval for Q&A, combining vector search with BM25 before generating
  final answers with OpenAI.
- Persistent storage for Chroma, BM25, and the LlamaIndex document store so
  retrievers can be reused across runs.
- Loan-agent MVP APIs under `/api/v1/loan` for customer intake, loan profiles,
  compliance checks, operations tasks, limit calculation, and case reports.

## Service architecture

```text
FastAPI routes
  /api/v1/auth/register
  /api/v1/auth/login
  /api/v1/auth/me
  /api/v1/knowledge-base/process-document
  /api/v1/loan/...
  /api/v1/qna/question_and_answer
            |
            v
KnowledgeBaseService
  - loads documents
  - parses and indexes content
  - retrieves relevant context
  - tracks user indexed files
            |
            v
LlamaIndex + Chroma + BM25
MongoDB user_indexed_files registry
LoanAgentService
  - tracks customers and loan profiles
  - stores uploaded loan documents
  - runs MVP rule checks and limit calculations
  - creates tasks, checklists, compliance results, and reports
```

## API surface

### `POST /api/v1/auth/register`

Create a local account with an email and password.

| Field | Type | Description |
|-------|------|-------------|
| `email` | string | User email address. Stored in lowercase and must be unique. |
| `password` | string | Plain-text password. Minimum length is 8 characters. |
| `full_name` | string or null | Optional display name. |

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "user@example.com",
        "password": "secret123",
        "full_name": "Test User"
      }'
```

Returns `201 Created` on success and `409 Conflict` when the email already exists.

### `POST /api/v1/auth/login`

Authenticate with email and password to get a Bearer access token.

| Field | Type | Description |
|-------|------|-------------|
| `email` | string | User email address. |
| `password` | string | Plain-text password. |

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "user@example.com",
        "password": "secret123"
      }'
```

Returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Returns `401 Unauthorized` when credentials are invalid.

### `GET /api/v1/auth/me`

Resolve the currently authenticated user from the Bearer token.

Example:

```bash
curl "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <jwt>"
```

Returns `200 OK` with the user profile when the token is valid.

### `POST /api/v1/knowledge-base/process-document`

Upload and ingest a single text-based PDF into the knowledge base. This endpoint
requires a Bearer access token and accepts `multipart/form-data`.

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | Text-based PDF file to ingest. PDFs without extractable text are rejected. |

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-base/process-document" \
  -H "Authorization: Bearer <jwt>" \
  -F "file=@./documents/report.pdf;type=application/pdf"
```

### `POST /api/v1/qna/question_and_answer`

Ask a question against the latest ingested knowledge base. This endpoint requires
a Bearer access token.

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | Natural-language question to answer from retrieved context. |
| `conversation_history` | array | Optional prior chat messages used to interpret follow-up questions. |

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/qna/question_and_answer" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{
        "question": "What about the deadline?",
        "conversation_history": [
          {"role": "user", "content": "Tell me about the project timeline."},
          {"role": "assistant", "content": "The project has multiple milestones."}
        ]
      }'
```

### Loan Agent MVP APIs

Loan-agent APIs are protected by the same Bearer auth as the knowledge-base
routes. Uploaded legal, financial, and collateral documents use
`multipart/form-data`.

| Agent | API | Endpoint |
|-------|-----|----------|
| Credit | `create_customer` | `POST /api/v1/loan/customers` |
| Credit | `get_customer` | `GET /api/v1/loan/customers/{customer_id}` |
| Credit | `update_customer` | `PATCH /api/v1/loan/customers/{customer_id}` |
| Credit | `create_loan_profile` | `POST /api/v1/loan/loan-profiles` |
| Credit | `upload_legal_doc` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/legal-docs` |
| Credit | `check_legal_docs` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/check-legal-docs` |
| Compliance | `get_loan_profile` | `GET /api/v1/loan/loan-profiles/{loan_profile_id}` |
| Compliance | `upload_financial_report` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/financial-reports` |
| Compliance | `upload_collateral` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/collaterals` |
| Compliance | `check_financials` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/check-financials` |
| Compliance | `check_collateral` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/check-collateral` |
| Compliance | `check_credit_rule` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/check-credit-rule` |
| Compliance | `save_compliance_result` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/compliance-result` |
| Operations | `update_case_status` | `PATCH /api/v1/loan/loan-profiles/{loan_profile_id}/status` |
| Operations | `create_checklist` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/checklist` |
| Operations | `calculate_loan_limit` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/calculate-limit` |
| Operations | `create_task` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/tasks` |
| Operations | `create_report` | `POST /api/v1/loan/loan-profiles/{loan_profile_id}/reports` |
| Operations | `list_reports` | `GET /api/v1/loan/loan-profiles/{loan_profile_id}/reports` |

Minimal demo flow:

```text
create_customer -> create_loan_profile -> upload_legal_doc ->
upload_financial_report -> upload_collateral -> check_* ->
calculate_loan_limit -> create_task -> create_report
```

### OpenClaw tool access

`POST /api/v1/qna/retrieve-chunks` and
`POST /api/v1/knowledge-base/document-text` still support the normal
`Authorization: Bearer <jwt>` user auth. For OpenClaw tool calls, they also
accept a short shared key while keeping the same user-scoped collection lookup:

```bash
curl -X POST "http://localhost:8000/api/v1/qna/retrieve-chunks" \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Api-Key: <openclaw-key>" \
  -H "X-OpenClaw-User-Id: <user-id>" \
  -d '{
        "question": "What about the deadline?",
        "conversation_history": []
      }'
```

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-base/document-text" \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Api-Key: <openclaw-key>" \
  -H "X-OpenClaw-User-Id: <user-id>" \
  -d '{
        "document_path": "report.pdf",
        "page_label": "2"
      }'
```

Configure the shared key with `RAG_BRAIN_OPENCLAW_API_KEY`.

## Specialist Agents

MediaX Agent Bank currently provides three specialist agents:

- `agents/credit_agent.py` handles customer intake, legal scoring, duplicate
  matching, and loan-profile readiness.
- `agents/compliance_agent.py` scores financial, repayment, collateral, and
  compliance risk.
- `agents/operations_agent.py` calculates the completion checklist and final
  limit, selects S01-S11 status, SLA, priority, and ordered actions.
- `agents/orchestrator_agent.py` runs the fixed Credit → Compliance → Operations
  workflow and passes only validated upstream results to the next agent.

All three accept normalized JSON, return structured results, and fail closed when
data or trusted policy evidence is missing. `execution_mode="assess"` is the
default and never writes data. `execution_mode="execute"` allows only that
agent's user-scoped tools. Approval and disbursement remain human decisions.

### Shared FastMCP adapter

The shared MCP server exposes five common read tools plus domain tools:

```text
search_knowledge(domain: "credit" | "compliance" | "operations", query: str, top_k: int = 5)
get_document_page(domain: "credit" | "compliance" | "operations", source_id: str)
get_loan_profile(loan_profile_id: str)
get_customer(customer_id: str)
list_reports(loan_profile_id: str)

Credit: search_customer, create_customer, update_customer, create_loan_profile, check_legal_docs
Compliance: check_financials, check_collateral, check_credit_rule, save_compliance_result
Operations: update_case_status, create_checklist, calculate_loan_limit, create_task, create_report
```

Each agent searches its own domain first. When a chunk lacks enough context, it
may read the full page only by reusing a `source_id` from that search. When input
includes `loan_profile_id`, it may also read the persisted profile, the customer
referenced by that profile, and existing reports. Loan case data is treated as
case facts, not policy evidence.

Start the adapter with separate server-side scopes for the three policy
collections and persisted loan cases:

```powershell
$env:RAG_MCP_CREDIT_USER_ID="<credit-policy-user-id>"
$env:RAG_MCP_COMPLIANCE_USER_ID="<compliance-policy-user-id>"
$env:RAG_MCP_OPERATIONS_USER_ID="<operations-policy-user-id>"
$env:LOAN_DATA_MCP_USER_ID="<loan-data-user-id>"
& '.\.venv\Scripts\python.exe' -m app.rag_mcp_server
```

`RAG_MCP_USER_ID` remains an optional legacy fallback for the credit scope only.
Compliance and Operations never fall back to it.

The default MCP endpoint is `http://127.0.0.1:8766/mcp`. Override its bind
address with `RAG_MCP_HOST` and `RAG_MCP_PORT` when needed.

The RAG corpus contains text documents or PDFs with a text layer. OCR is outside
this project scope.

### Run the agents

Set the shared runtime variables:

```powershell
$env:OPENAI_API_KEY="..."
$env:RAG_MCP_URL="http://127.0.0.1:8766/mcp"
```

Run Credit Agent examples:

```powershell
& '.\.venv\Scripts\python.exe' agents/credit_agent.py --input examples/credit_personal.json
& '.\.venv\Scripts\python.exe' agents/credit_agent.py --input examples/credit_sme.json
```

Run Compliance Agent examples:

```powershell
& '.\.venv\Scripts\python.exe' agents/compliance_agent.py --input examples/compliance_personal.json
& '.\.venv\Scripts\python.exe' agents/compliance_agent.py --input examples/compliance_sme.json
```

Run Operations Agent examples:

```powershell
& '.\.venv\Scripts\python.exe' agents/operations_agent.py --input examples/operations_personal.json
& '.\.venv\Scripts\python.exe' agents/operations_agent.py --input examples/operations_sme.json
```

Run the full SME workflow through the Orchestrator:

```powershell
& '.\.venv\Scripts\python.exe' agents/orchestrator_agent.py `
  --credit-input examples/credit_sme.json `
  --compliance-input examples/compliance_sme.json `
  --operations-input examples/operations_sme.json
```

Ask a natural-language question through the Orchestrator and the routed
specialist knowledge agent:

```powershell
& '.\.venv\Scripts\python.exe' agents/orchestrator_agent.py `
  --ask "Tỷ lệ cho vay tối đa đối với tài sản bảo đảm là nhà đất là bao nhiêu?"
```

Question mode is read-only. It routes one question to Credit, Compliance, or
Operations, retrieves policy evidence through MCP, and prints the grounded
answer with cited sources.

## Getting started

### Prerequisites

- Python 3.11
- An OpenAI API key for answer generation

### Installation

Install the core application dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you want to use local HuggingFace embeddings, install the extra local
embedding dependencies as well:

```bash
pip install -r requirements.txt -r requirements-local-embeddings.txt
```

### Environment configuration

Create a `.env` file in the project root and configure the values you need.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Disables interactive docs in production. |
| `MONGO_URI` | — | Required MongoDB connection string used for startup client initialization. |
| `MONGO_DB_NAME` | `rag_brain` | Fallback database name used when `MONGO_URI` omits the database path. |
| `JWT_SECRET_KEY` | `change-me-to-a-long-random-secret-key` | Secret used to sign and verify JWT access tokens. |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm for access tokens. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Access-token lifetime in minutes. |
| `OPENAI_API_KEY` | — | Required for question answering. |
| `LLAMA_COLLECTION_NAME` | `qa_collection` | Default Chroma collection name. |
| `LLAMA_EMBED_PROVIDER` | `huggingface` | Embedding backend. Supported values: `huggingface` and `openai`. |
| `LLAMA_EMBED_MODEL` | `VoVanPhuc/sup-SimCSE-VietNamese-phobert-base` | Local embedding model used when `LLAMA_EMBED_PROVIDER=huggingface`. |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | OpenAI embedding model used when `LLAMA_EMBED_PROVIDER=openai`. |
| `OPENAI_QNA_MODEL` | `gpt-5.4-mini` | OpenAI chat model used for QnA answer generation. |
| `STORAGE_ROOT` | unset | Shared persistent storage root. When set, Chroma/BM25/docstore default under this path. |
| `RAILWAY_VOLUME_MOUNT_PATH` | unset | Optional fallback mount path if you prefer Railway-specific naming over `STORAGE_ROOT`. |
| `LLAMA_CHROMA_PERSIST_DIR` | derived | Explicit Chroma persistence path. Overrides `STORAGE_ROOT` when set. |
| `HF_HOME` / `TRANSFORMERS_CACHE` / `HF_HUB_CACHE` | `./hf_cache` | Local cache directories for HuggingFace assets. |
| `BM25_PERSIST_DIR` | derived | Explicit BM25 persistence path. Overrides `STORAGE_ROOT` when set. |
| `DOCSTORE_PERSIST_DIR` | derived | Explicit path used to persist the LlamaIndex document store. Overrides `STORAGE_ROOT` when set. |
| `RAG_BRAIN_OPENCLAW_API_KEY` | unset | Short shared secret accepted with `X-OpenClaw-Api-Key` for OpenClaw access to `retrieve-chunks` and `document-text`; callers must also send `X-OpenClaw-User-Id`. |
| `RAG_MCP_CREDIT_USER_ID` | — | User scope containing credit policy knowledge. |
| `RAG_MCP_COMPLIANCE_USER_ID` | — | User scope containing compliance policy knowledge. |
| `RAG_MCP_OPERATIONS_USER_ID` | — | User scope containing operations policy knowledge. |
| `RAG_MCP_USER_ID` | unset | Legacy fallback for the credit policy scope only. |
| `LOAN_DATA_MCP_USER_ID` | — | Server-side user scope for persisted loan case reads and authorized writes. |
| `RAG_MCP_HOST` / `RAG_MCP_PORT` | `127.0.0.1` / `8766` | Bind address for the shared FastMCP server. |
| `RAG_MCP_URL` | `http://127.0.0.1:8766/mcp` | FastMCP endpoint used by the specialist agents. |
| `OPENAI_AGENT_MODEL` | `gpt-5.4-mini` | Model used by the specialist agents. |
| `TEMP_KB_DIR` | `tmp/knowledge_base` | Ephemeral working directory for uploaded PDF files during ingestion. |
| `LOAN_UPLOAD_DIR` | derived | Explicit loan-case upload storage path. Defaults to `STORAGE_ROOT/loan_uploads` when `STORAGE_ROOT` is set, otherwise `./loan_uploads`. |

Persistence resolution rules:

- If `LLAMA_CHROMA_PERSIST_DIR`, `BM25_PERSIST_DIR`, or `DOCSTORE_PERSIST_DIR` are set, the app uses them as-is.
- Otherwise, if `STORAGE_ROOT` is set, the app derives `chroma_db`, `bm25_storage`, `docstore`, and `loan_uploads` under that root.
- Otherwise, if `RAILWAY_VOLUME_MOUNT_PATH` is set, the app derives the same subdirectories under that mount path.
- Otherwise, local development falls back to `./chroma_db`, `./bm25_storage`, `./docstore`, and `./loan_uploads`.

### Embedding providers

- `LLAMA_EMBED_PROVIDER=huggingface` uses the local model configured in
  `LLAMA_EMBED_MODEL`.
- `LLAMA_EMBED_PROVIDER=openai` uses OpenAI embeddings and requires
  `OPENAI_API_KEY`.

Installation guidance:

- `LLAMA_EMBED_PROVIDER=openai` only needs `requirements.txt`.
- `LLAMA_EMBED_PROVIDER=huggingface` should install both
  `requirements.txt` and `requirements-local-embeddings.txt`.

When switching embedding providers or models, do not reuse the same persisted
Chroma collection without re-ingesting documents, because vector dimensions may
change.

### Running the service

```bash
uvicorn app.main:app --reload
```

Interactive API docs are available at `http://localhost:8000/docs` in
non-production environments.

### Running tests

```bash
pytest -q
```

## Railway persistence

For Railway, attach a Volume and mount it at `/app/data`, then set either:

```env
STORAGE_ROOT=/app/data
```

or the three explicit paths:

```env
LLAMA_CHROMA_PERSIST_DIR=/app/data/chroma_db
BM25_PERSIST_DIR=/app/data/bm25_storage
DOCSTORE_PERSIST_DIR=/app/data/docstore
```

`TEMP_KB_DIR` can stay ephemeral because uploaded PDF files are only kept while
the ingestion request is running.

## Development notes

- The root endpoint `/` returns a simple readiness message.
- Static files are mounted at `/static`.
- Phase 2 now protects knowledge-base ingestion and question answering with Bearer auth.
- Knowledge-base storage is now scoped per authenticated user namespace.
- Shared legacy knowledge-base data is not migrated automatically; users should re-ingest documents into their own namespace.

## License

This project is distributed under the [Business Source License 1.1](LICENSE).
.
