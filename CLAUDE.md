# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Slack RAG (Retrieval-Augmented Generation) Bot that acts as middleware between Slack and an external RAG API service. The bot listens for mentions and direct messages in Slack, forwards queries to a RAG API endpoint, and returns responses in threaded conversations.

**Technology Stack:**
- **FastAPI** + **slack-bolt** - Web framework and Slack integration
- **httpx** - Async HTTP client for RAG API calls
- **Uvicorn** - ASGI server
- Python 3.x with virtual environment

## Development Commands

### Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# FastAPI mode (current implementation, requires public HTTPS URL)
python3 app.py

# Or use uvicorn directly
uvicorn app:api --host 0.0.0.0 --port 8080

# Socket mode (legacy reference in app_socket_example.py)
python3 app_socket_example.py
```

### Docker Deployment

**Build Docker Image:**
```bash
# Build locally
docker build -t slack-rag-bot:latest .

# Run locally with environment file
docker run -p 8080:8080 --env-file .env slack-rag-bot:latest

# Run with individual environment variables
docker run -p 8080:8080 \
  -e SLACK_BOT_USER_OAUTH_TOKEN=xoxb-... \
  -e SLACK_SIGNING_SECRET=... \
  -e RAG_API_ENDPOINT=https://... \
  -e RAG_API_HEALTH=https://... \
  slack-rag-bot:latest
```

**Deploy to AWS ECR:**
```bash
# Deploy with defaults (us-east-1, slack-rag-bot, latest)
./deploy_aws.sh

# Deploy with custom parameters
./deploy_aws.sh <AWS_REGION> <ECR_REPO_NAME> <IMAGE_TAG>

# Example: Deploy to us-west-2 with version tag
./deploy_aws.sh us-west-2 slack-rag-bot v2.0.0
```

The `deploy_aws.sh` script will:
1. Authenticate Docker with AWS ECR
2. Create ECR repository if it doesn't exist
3. Build the Docker image
4. Tag and push to ECR (both specified tag and 'latest')

**Prerequisites for AWS ECR deployment:**
- AWS CLI installed and configured (`aws configure`)
- Docker installed and running
- AWS credentials with ECR permissions

### Required Environment Variables
```bash
SLACK_BOT_USER_OAUTH_TOKEN=xoxb-...   # Bot user OAuth token
SLACK_SIGNING_SECRET=...               # For webhook signature verification
RAG_API_ENDPOINT=...                   # RAG query endpoint URL
RAG_API_HEALTH=...                     # RAG health check endpoint
PORT=8080                              # Server port (optional, defaults to 3000)
```

Note: `SLACK_APP_LEVEL_TOKEN` only needed for Socket Mode (app_socket_example.py).

## Architecture

### Application Flow
```
User Message → Slack Event → FastAPI Webhook
    ↓
Bot adds emoji reaction (acknowledgment)
    ↓
Bot posts "Processing..." message
    ↓
Bot calls RAG API (POST with {"query": "..."})
    ↓
Bot updates message with RAG response (or error)
```

### Key Components

**app.py (Main Application):**
- FastAPI server with SlackRequestHandler adapter
- Slack Bolt app for event handling
- HTTPX client with 60-second timeout for RAG API calls

**Event Handlers:**
- `@slack_app.event("app_mention")` - Handles @mentions in channels
- `@slack_app.event("message")` - Handles direct messages and channel messages
- Both handlers filter out bot messages to prevent infinite loops

**FastAPI Endpoints:**
- `GET /` - Health check
- `GET /health` - Detailed health status (Slack + RAG API)
- `POST /slack/events` - Slack webhook endpoint (routed to SlackRequestHandler)

### Important Implementation Details

1. **Threaded Responses:** All bot replies use Slack threads (`thread_ts`) to maintain conversation context

2. **RAG API Contract:**
   - Request: `POST` with JSON `{"query": "user message"}`
   - Response: JSON `{"response": "answer text"}`
   - Timeout: 60 seconds

3. **Error Handling:**
   - Graceful degradation with user-friendly error messages in Slack
   - Logging at INFO level for debugging

4. **Deployment Mode:** FastAPI implementation requires a public HTTPS URL for Slack webhooks (webhook must be configured in Slack app settings)

5. **Legacy Code:** `app_socket_example.py` shows Socket Mode implementation (WebSocket-based, no public URL needed) - kept as reference

### Slack Permissions (manifest.json)
- `channels:history` - Read channel messages
- `chat:write` - Send messages
- `im:history` - Read direct messages
- Events: `message.channels`, `message.im`

## Code Modifications

### Adding New Event Handlers
Use the `@slack_app.event()` decorator pattern. Always filter bot messages:
```python
@slack_app.event("event_type")
def handler(event, say, client):
    if event.get("bot_id"):
        return  # Prevent infinite loops
    # handler logic
```

### Modifying RAG API Integration
RAG API client is at app.py:38-38. Key variables:
- `RAG_API_ENDPOINT` - Query endpoint
- `http_client` - HTTPX client with 60s timeout
- API call logic in app.py:85-88

### Adding FastAPI Endpoints
Add routes after line 134. The SlackRequestHandler must remain at `/slack/events` for Slack webhooks.

## Project Structure
```
/
├── app.py                    # Main FastAPI application
├── app_socket_example.py     # Legacy Socket Mode reference
├── requirements.txt          # Dependencies
├── manifest.json             # Slack app configuration
├── Dockerfile                # Docker container configuration
├── .dockerignore             # Docker build exclusions
├── deploy_aws.sh             # AWS ECR deployment script
├── .env                      # Environment variables (not in git)
└── .venv/                    # Virtual environment
```

## Migration Notes

Recent migration (commit 18ccbbc) from Socket Mode to FastAPI implementation:
- **Old:** WebSocket-based, no public URL needed, simpler but less scalable
- **New:** HTTP webhooks, requires public HTTPS URL, production-ready

When deploying, ensure:
1. Public HTTPS URL is accessible to Slack
2. `/slack/events` endpoint is configured in Slack app settings
3. All required environment variables are set
4. Firewall/security groups allow Slack IP ranges

## Known Limitations

- No database or state management (stateless design)
- No response caching
- No rate limiting
- No formal test suite
- No CI/CD pipeline (manual deployment using deploy_aws.sh script)
