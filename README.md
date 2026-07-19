# MediaX Agent Bank

MediaX Agent Bank is a multi-agent AI MVP for loan-processing workflows. It
combines a bundled web UI, a FastAPI backend, an Orchestrator, three banking
specialist agents, a shared FastMCP tool server, and a user-scoped RAG
knowledge base.

The current MVP supports:

- A bundled demo UI with 10 pre-seeded accounts, JWT-based account selection,
  user-scoped browser chat state, grounded answers, and document sources.
  User-facing agent answers are always in Vietnamese.
- Real PDF listing, search, and ingestion for the Credit, Compliance, and
  Operations policy knowledge bases.
- Credit, Compliance, and Operations specialist agents.
- A fixed Credit → Compliance → Operations assessment workflow.
- RAG chunk retrieval with full-page fallback when a chunk lacks context.
- Read and controlled write tools for demo loan-case data.

## Architecture

```text
Web UI (10 selectable demo accounts + JWT)
        |
        | POST /api/v1/orchestrator/chat
        v
FastAPI
  - seeds public demo accounts at startup
  - creates or reopens SQLiteSession
  - writes chat audit records to MongoDB
  - returns answer + domain + sources
        |
        v
Orchestrator Agent
  - reads conversation context
  - selects exactly one specialist for Q&A
        |
        +--> Credit Agent
        +--> Compliance Agent
        +--> Operations Agent
                   |
                   v
          FastMCP :8766/mcp
            - RAG policy tools
            - loan-case tools
                   |
        +----------+----------+
        |                     |
Chroma + BM25           MongoDB
policy knowledge        users, indexed-file registry,
                        chat audit, and loan data
```

There are two Orchestrator flows:

1. **Knowledge chat:** the Orchestrator uses conversation history and delegates
   each question to one specialist agent. The specialist may only answer from
   evidence returned by MCP.
2. **Loan assessment:** the Orchestrator runs Credit → Compliance → Operations
   in order and passes validated upstream results to the next specialist.

## Components

| Component | Responsibility |
|-----------|----------------|
| `agents/credit_agent.py` | Customer intake, legal scoring, duplicate checks, and loan-profile readiness. |
| `agents/compliance_agent.py` | Financial capacity, repayment, collateral, policy ratios, and compliance risk. |
| `agents/operations_agent.py` | Checklist completion, workflow status, SLA, priority, limit, and next actions. |
| `agents/orchestrator_agent.py` | Specialist routing for chat and ordered execution for full assessments. |
| `app/rag_mcp_server.py` | Shared FastMCP adapter for RAG and persisted loan-case tools. |
| `app/api/v1/orchestrator.py` | Chat API, SQLite conversation-session lifecycle, and user-aware history logging. |
| `app/services/auth_service.py` | Registration, login, JWT resolution, and startup seeding of the 10 demo accounts. |
| `app/services/chat_history_service.py` | MongoDB chat-session and message audit records. |
| `app/services/knowledge_base_service.py` | PDF ingestion, indexing, hybrid retrieval, and full-page lookup. |

The local `agents/` directory deliberately has no `__init__.py` because
`agents` is also the installed OpenAI Agents SDK package.

## Web UI

The FastAPI application serves the bundled Agent Bank demo UI at:

- `/` redirects to `/qa`.
- `/qa` and `/documents` serve the same single-page shell.

Use the sidebar to switch between the Orchestrator chat and the
policy knowledge-base screen; the selected view is tracked in the URL hash.

On startup, FastAPI creates 10 public demo accounts if they do not already
exist. The UI asks the user to select one account, obtains its JWT through
`POST /api/v1/auth/demo-login/{account_number}`, and then unlocks the app. The
demo selector intentionally does not ask for a password.

The `/qa` screen sends the selected account's Bearer token to
`POST /api/v1/orchestrator/chat`. It stores local chat sessions, messages,
source metadata, and the backend `session_id` in browser `localStorage`. The
storage key includes the authenticated user ID, so each demo account restores
only its own browser transcript and backend conversation IDs.

The `/documents` screen calls the authenticated knowledge-base APIs to list,
search, and upload text-based PDFs. Its three Agent scopes map to the Credit,
Compliance, and Operations policy-owner IDs configured in
`DOCUMENT_AGENT_SCOPES` in `static/js/app.js`.

## Quick start

### 1. Prerequisites

- Python 3.11
- MongoDB
- An OpenAI API key
- Text-based policy PDFs for Credit, Compliance, and Operations

### 2. Install dependencies

PowerShell:

```powershell
python -m venv .venv
& '.\.venv\Scripts\Activate.ps1'
python -m pip install -r requirements.txt
```

For local HuggingFace embeddings, also install:

```powershell
python -m pip install -r requirements-local-embeddings.txt
```

### 3. Configure the backend

Copy `.env.example` to `.env` and provide at least:

```env
MONGO_URI=mongodb://localhost:27017/rag_brain
MONGO_DB_NAME=rag_brain
OPENAI_API_KEY=<openai-api-key>
```

Choose one embedding provider before ingesting documents:

```env
# Local embeddings
LLAMA_EMBED_PROVIDER=huggingface
LLAMA_EMBED_MODEL=VoVanPhuc/sup-SimCSE-VietNamese-phobert-base
```

or:

```env
# OpenAI embeddings
LLAMA_EMBED_PROVIDER=openai
OPENAI_EMBED_MODEL=text-embedding-3-small
```

Do not change the embedding provider or model for an existing Chroma collection.
Re-ingest the documents when the embedding dimensions change.

### 4. Start FastAPI

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
```

Swagger UI is available at <http://localhost:8000/docs> unless
`ENVIRONMENT=production`, which disables Swagger, ReDoc, and OpenAPI routes.

### 5. Select a demo account and prepare policy knowledge

Open <http://localhost:8000/qa> and select any of the 10 demo accounts. FastAPI
creates missing demo accounts during startup, so no registration or password is
needed for the bundled UI.

RAG storage is scoped by internal user ID. Create three accounts through Swagger
for the Credit, Compliance, and Operations policy collections:

1. Call `POST /api/v1/auth/register`.
2. Call `POST /api/v1/auth/login`.
3. Use the returned Bearer token with `GET /api/v1/auth/me` and record its
   `id`.
4. Upload the matching text-based PDFs through
   `POST /api/v1/knowledge-base/process-document`.

These accounts isolate the three specialist policy collections. They are
separate from the 10 public accounts used to enter the demo UI.

By default, uploads and file listing use the user ID from the Bearer token. For
internal data preparation, set `ALLOW_KB_TARGET_USER_UPLOAD=true` to allow
`POST /api/v1/knowledge-base/process-document` to accept a form `user_id` and
`GET /api/v1/knowledge-base/files` to accept a `user_id` query parameter. When
the flag is disabled, requests that target another user ID return `403`.

The bundled `/documents` screen targets the three IDs in
`DOCUMENT_AGENT_SCOPES`. For a new database, replace those values with the three
recorded policy-owner IDs and enable `ALLOW_KB_TARGET_USER_UPLOAD=true` so a
selected demo account can manage those shared policy collections.

### 6. Start FastMCP

Open a second terminal and set the three recorded IDs:

```powershell
$env:RAG_MCP_CREDIT_USER_ID="<credit-policy-user-id>"
$env:RAG_MCP_COMPLIANCE_USER_ID="<compliance-policy-user-id>"
$env:RAG_MCP_OPERATIONS_USER_ID="<operations-policy-user-id>"
& '.\.venv\Scripts\python.exe' -m app.rag_mcp_server
```

The default MCP endpoint is <http://127.0.0.1:8766/mcp>.

`RAG_MCP_USER_ID` is only a legacy fallback for the Credit policy scope.
Compliance and Operations require their dedicated variables.

For full loan assessments that read or mutate persisted demo loan data, also set:

```powershell
$env:LOAN_DATA_MCP_USER_ID="<loan-data-user-id>"
```

This variable is not required for read-only policy Q&A.

FastAPI and FastMCP are separate long-running processes and must both remain
running for agent chat. The repository's `Dockerfile` and `Procfile` start only
FastAPI. In a hosted environment, start `python -m app.rag_mcp_server` as a
second process, point the FastAPI process at it with `RAG_MCP_URL`, and ensure
the MCP process can read the same persisted RAG directories used during
document ingestion. Set `RAG_MCP_HOST=0.0.0.0` when the MCP process must accept
connections outside localhost.

The committed `Dockerfile` installs `requirements.txt` only. A container using
`LLAMA_EMBED_PROVIDER=huggingface` must also install
`requirements-local-embeddings.txt`; otherwise configure the OpenAI embedding
provider before startup.

### 7. Ask a question

Authenticate as the first demo account, then omit `session_id` from the first
request:

```powershell
$auth = Invoke-RestMethod -Method Post `
  -Uri 'http://localhost:8000/api/v1/auth/demo-login/1'
$headers = @{ Authorization = "Bearer $($auth.access_token)" }

$first = Invoke-RestMethod -Method Post `
  -Uri 'http://localhost:8000/api/v1/orchestrator/chat' `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body (@{
    message = 'Tỷ lệ cho vay tối đa đối với tài sản bảo đảm là nhà đất là bao nhiêu?'
  } | ConvertTo-Json)

$first
```

Reuse the returned ID for a follow-up:

```powershell
$second = Invoke-RestMethod -Method Post `
  -Uri 'http://localhost:8000/api/v1/orchestrator/chat' `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body (@{
    session_id = $first.session_id
    message = 'Còn nếu tài sản bảo đảm là ô tô thì sao?'
  } | ConvertTo-Json)

$second
```

## Chat API

### `POST /api/v1/orchestrator/chat`

The endpoint accepts an optional Bearer token. The bundled UI always supplies
the selected demo account's token; authenticated exchanges are associated with
that user in the MongoDB chat audit. Direct API callers may omit the token, in
which case the chat still runs but the audit record has no `user_id`.

Request:

```json
{
  "message": "Tỷ lệ cho vay tối đa đối với nhà đất là bao nhiêu?",
  "session_id": null
}
```

Response:

```json
{
  "session_id": "13ba1bdb-1447-4204-902f-178ff457b767",
  "trace_id": "trace_<openai-trace-id>",
  "answer": "Tỷ lệ cho vay tối đa đối với tài sản bảo đảm là nhà đất là 80%.",
  "domain": "compliance",
  "insufficient_information": false,
  "sources": [
    {
      "source_id": "<rag-chunk-id>",
      "file_name": "04_ho_so_tai_san_bao_dam_v2.pdf",
      "page": "2",
      "excerpt": "..."
    }
  ]
}
```

If the Orchestrator cannot confidently route a user turn to one specialist, the
API returns a clarification response instead of failing the request:

```json
{
  "session_id": "13ba1bdb-1447-4204-902f-178ff457b767",
  "trace_id": "trace_<openai-trace-id>",
  "answer": "Câu hỏi hiện chưa thuộc phạm vi hỗ trợ của MediaX Agent Bank. Vui lòng nhập câu hỏi liên quan đến hồ sơ vay, tín dụng, pháp lý, chính sách hoặc quy trình ngân hàng.",
  "domain": "general",
  "insufficient_information": true,
  "sources": []
}
```

The backend generates a UUID when `session_id` is absent. The bundled UI stores
this value in user-scoped browser `localStorage` and sends it with later
messages.

Conversation context is persisted by OpenAI Agents SDK `SQLiteSession`. In a
deployment it uses `STORAGE_ROOT` (or `RAILWAY_VOLUME_MOUNT_PATH`), for example:

```text
/app/data/orchestrator_sessions.db
```

Without a storage root it falls back to the local, gitignored
`.local_storage/orchestrator_sessions.db`. SQLite remains intended for the
single-instance MVP.

MongoDB also receives audit copies of the user and assistant messages, source
metadata, domain, and trace ID. There is currently no backend endpoint for
listing those records or loading a transcript. The transcript shown by the
bundled UI still comes from that account's browser `localStorage`; SQLite stores
the model conversation context.

### Agent tracing

Each chat request creates one OpenAI Agents SDK trace. `session_id` is used as
the trace group ID, while `trace_id` is returned to the caller and can be opened
in the [OpenAI Traces dashboard](https://platform.openai.com/traces).

Railway logs contain JSON events for request, agent, routing, tool, validation,
duration, and token usage. They do not contain questions, RAG queries, chunks,
or loan data. Sensitive trace payloads are disabled by default; enable them only
for local testing with synthetic data.

## RAG and MCP contract

Question mode exposes only two read-only tools to a specialist:

```text
search_knowledge(
  domain: "credit" | "compliance" | "operations",
  query: str,
  top_k: 5
)

get_document_page(
  domain: "credit" | "compliance" | "operations",
  source_id: str
)
```

Every question starts with `search_knowledge`. If a chunk is insufficient, the
agent may call `get_document_page` only with a `source_id` returned by that
search. Answers cannot cite unknown evidence IDs or use policy facts from model
memory.

The shared MCP server also contains loan-case tools:

```text
Common reads:
  get_loan_profile, get_customer, list_reports

Credit:
  search_customer, create_customer, update_customer,
  create_loan_profile, check_legal_docs

Compliance:
  check_financials, check_collateral, check_credit_rule,
  save_compliance_result

Operations:
  update_case_status, create_checklist, calculate_loan_limit,
  create_task, create_report
```

`execution_mode="assess"` blocks mutating tools.
`execution_mode="execute"` permits only the tools assigned to that specialist.
Approval and disbursement remain human decisions.

## Running agents from the CLI

CLI assessment commands require FastMCP and the matching policy documents:

```powershell
& '.\.venv\Scripts\python.exe' agents/credit_agent.py --input examples/credit_sme.json
& '.\.venv\Scripts\python.exe' agents/compliance_agent.py --input examples/compliance_sme.json
& '.\.venv\Scripts\python.exe' agents/operations_agent.py --input examples/operations_sme.json
```

Run the full SME workflow:

```powershell
& '.\.venv\Scripts\python.exe' agents/orchestrator_agent.py `
  --credit-input examples/credit_sme.json `
  --compliance-input examples/compliance_sme.json `
  --operations-input examples/operations_sme.json
```

Ask one stateless CLI question:

```powershell
& '.\.venv\Scripts\python.exe' agents/orchestrator_agent.py `
  --ask 'Tỷ lệ cho vay tối đa đối với tài sản bảo đảm là nhà đất là bao nhiêu?'
```

The CLI `--ask` command handles one turn and does not create a persistent chat
session. Use the FastAPI chat endpoint for multi-turn conversation.

## Environment variables

| Variable | Required for | Default |
|----------|--------------|---------|
| `ENVIRONMENT` | FastAPI docs and development CORS behavior | `development` |
| `MONGO_URI` | FastAPI, RAG, and loan data | none |
| `MONGO_DB_NAME` | MongoDB database fallback | `rag_brain` |
| `JWT_SECRET_KEY` | Signing access tokens; replace outside local development | insecure development placeholder |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime | `10080` |
| `OPENAI_API_KEY` | Agents, hosted traces, legacy Q&A, and optional OpenAI embeddings | none |
| `LLAMA_EMBED_PROVIDER` | Document ingestion and retrieval | `huggingface` |
| `LLAMA_EMBED_MODEL` | Local embeddings | `VoVanPhuc/sup-SimCSE-VietNamese-phobert-base` |
| `OPENAI_EMBED_MODEL` | OpenAI embeddings | `text-embedding-3-small` |
| `STORAGE_ROOT` / `RAILWAY_VOLUME_MOUNT_PATH` | Chroma, BM25, docstore, loan uploads, and SQLite sessions | local project directories |
| `ALLOW_KB_TARGET_USER_UPLOAD` | Allow an authenticated user to prepare another user's RAG collection | `false` |
| `RAG_MCP_USER_ID` | Legacy fallback for Credit policy knowledge only | none |
| `RAG_MCP_CREDIT_USER_ID` | Credit policy knowledge | none |
| `RAG_MCP_COMPLIANCE_USER_ID` | Compliance policy knowledge | none |
| `RAG_MCP_OPERATIONS_USER_ID` | Operations policy knowledge | none |
| `LOAN_DATA_MCP_USER_ID` | Persisted loan-case tools | none |
| `RAG_MCP_HOST` / `RAG_MCP_PORT` | FastMCP bind address | `127.0.0.1` / `8766` |
| `RAG_MCP_URL` | Agent MCP client | `http://127.0.0.1:8766/mcp` |
| `OPENAI_AGENT_MODEL` | Orchestrator and specialists | `gpt-5.4-mini` |
| `OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA` | Include model/tool payloads in OpenAI traces | `false` |

See `.env.example` for JWT, legacy Q&A, individual storage paths, and the
remaining supporting-API settings.

## Supporting APIs

The repository still exposes supporting RAG and demo loan-data APIs:

- `/api/v1/auth/*`
- `/api/v1/knowledge-base/*`
- `/api/v1/qna/*`
- `/api/v1/loan/*`

Use Swagger at <http://localhost:8000/docs> for their current schemas. These
routes support data preparation and agent tools; the main demo entry point is
the bundled UI at `/qa`, backed by `POST /api/v1/orchestrator/chat`.

## Tests

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

## MVP limitations

- The 10 public demo accounts are intentionally selectable without passwords;
  this convenience flow is not production authentication.
- The document screen maps its three Agent scopes to fixed internal user IDs;
  a fresh deployment must align those IDs and enable authorized target-user
  knowledge-base access.
- No OCR; scanned PDFs without an extractable text layer are unsupported.
- Each chat turn delegates to exactly one specialist; cross-domain aggregation
  in a single answer is not implemented.
- Chat sessions use local SQLite and are not shared across backend instances.
- UI chat transcripts are browser-local per demo account. MongoDB audit records
  exist, but there is no chat-history listing, session cleanup, or deletion API.
- Final approval and disbursement remain human responsibilities.

## License

This project is distributed under the [Business Source License 1.1](LICENSE).
