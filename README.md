# AI Customer Support Agent

This project is a production-style starter for an AI customer support system built with FastAPI, a lightweight MCP-compatible tool server, and an OpenAI-compatible LLM client.

## Features

- Answers customer questions with a knowledge base connector
- Retrieves order status from a database
- Creates support tickets for unresolved issues
- Summarizes conversations for human agents
- Detects likely escalation scenarios
- Exposes required tools through an MCP-style JSON-RPC endpoint

## Project Structure

```text
ai-support-agent/
├── backend/
│   ├── agent.py
│   ├── main.py
│   ├── mcp_server.py
│   ├── database/
│   │   └── models.py
│   └── tools/
│       ├── crm_tool.py
│       ├── kb_tool.py
│       ├── order_tool.py
│       └── ticket_tool.py
├── frontend/
│   └── simple_chat_ui.html
├── requirements.txt
└── README.md
```

## Architecture

- `FastAPI backend`: serves the `/chat` API, health endpoint, and the simple browser UI.
- `SupportAgent`: orchestrates LLM responses and decides when to call tools.
- `MCP server`: exposes `get_order_status`, `search_knowledge_base`, `create_support_ticket`, and `get_customer_details` over JSON-RPC at `/mcp`.
- `Connectors`: isolated tool classes for orders, CRM, knowledge base, and ticketing.
- `Database`: SQLAlchemy models for `customers`, `orders`, and `support_tickets`.

## Tech Choices

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite by default, with a clear upgrade path to PostgreSQL
- OpenAI-compatible SDK via the `openai` Python package

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optional: configure an OpenAI-compatible provider.

```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

If `OPENAI_API_KEY` is not set, the app still runs in a rules-based fallback mode so you can test the flows locally.

## Run

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## API Usage

### `POST /chat`

Request:

```json
{
  "customer_id": 1,
  "message": "Where is my order #45231?",
  "conversation_history": []
}
```

Response:

```json
{
  "response": "Order #45231 for Noise-Cancelling Headphones is currently shipped. Carrier: FedEx. Tracking: ZX991245US. Estimated delivery: 2026-03-15.",
  "used_tools": [
    {
      "name": "get_order_status",
      "arguments": {
        "order_id": "45231"
      },
      "result": {
        "order_id": 45231,
        "customer_id": 1,
        "item_name": "Noise-Cancelling Headphones",
        "status": "shipped",
        "tracking_number": "ZX991245US",
        "shipping_carrier": "FedEx",
        "estimated_delivery": "2026-03-15",
        "total_amount": 199.99
      }
    }
  ],
  "escalated": false,
  "conversation_summary": "Customer 1 asked: Where is my order #45231?. Agent responded: ...",
  "llm_mode": false
}
```

### `POST /mcp`

Example initialization request:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "initialize",
  "params": {}
}
```

Example tool list request:

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "tools/list",
  "params": {}
}
```

Example tool call request:

```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "tools/call",
  "params": {
    "name": "get_order_status",
    "arguments": {
      "order_id": "45231"
    }
  }
}
```

## Database

The app creates and seeds a local SQLite database file named `support_agent.db` on startup with example customers, orders, and support tickets.

To migrate to PostgreSQL:

- replace `DATABASE_URL` in `backend/database/models.py`
- update the engine configuration
- add migrations with Alembic for production deployments

## Example Agent Flow

User message:

```text
Where is my order #45231?
```

Expected flow:

1. Agent detects an order-tracking request.
2. Agent calls `get_order_status(order_id)`.
3. Tool returns shipping carrier, tracking number, and estimated delivery.
4. Agent responds with a concise customer-facing answer.

## Error Handling

- Invalid order IDs return `400`
- Unknown customers return `400`
- Unexpected backend failures return `500`
- Tool errors are surfaced in structured JSON-RPC format on the MCP endpoint

## Notes

- The knowledge base is intentionally simple and in-memory for easy extension.
- The ticketing and CRM connectors are implemented as modular service classes so they can be swapped with real APIs later.
- For a production deployment, add authentication, persistent conversation storage, rate limiting, and observability.
