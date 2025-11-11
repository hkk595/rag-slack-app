import os
import httpx
import logging
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. SET UP YOUR TOKENS ---
# It's best practice to set these as environment variables
# export SLACK_BOT_TOKEN="xoxb-..."
# export SLACK_APP_TOKEN="xapp-..."

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_USER_OAUTH_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_LEVEL_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# --- 2. INITIALIZE THE APPS ---
# Initialize FastAPI
api = FastAPI(title="Slack RAG Bot")

# Initialize Slack Bolt app
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Initialize Slack request handler
handler = SlackRequestHandler(slack_app)

# HTTPX client
RAG_API_ENDPOINT = os.environ.get("RAG_API_ENDPOINT", "")
RAG_API_HEALTH = os.environ.get("RAG_API_ENDPOINT", "")
http_client = httpx.Client(timeout=60.0)


# ============================================================================
# Slack Event Handlers
# ============================================================================

# --- 3. DEFINE THE EVENT HANDLER ---
# This decorator listens for any message that @mentions the bot
@slack_app.event("app_mention")
def handle_app_mention(event, say, client):
    """
    This function is triggered when the bot is @mentioned.
    """
    # Get the text from the user's message
    user_message = event["text"]
    user_id = event["user"]

    # Get the channel ID and thread timestamp (if it's in a thread)
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])

    logger.info(f"Received mention from user {user_id}: {user_message}")

    # Acknowledge the request immediately with an emoji
    try:
        slack_app.client.reactions_add(
            channel=channel,
            timestamp=event["ts"],
            name="face_with_monocle"  # Or any emoji you like
        )

        # Send processing message
        slack_response = client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="🔄 Finding the information for you..."
        )
        processing_msg_ts = slack_response["ts"]
    except Exception as e:
        logger.error(f"Error responding: {e}")
        return

    # Process the query
    try:
        # --- 4. CALL THE RAG API ---
        # Send the user's message to the RAG API
        http_response = http_client.post(RAG_API_ENDPOINT, json={"query": user_message})

        # Get the text response from the API
        rag_response = http_response.json().get("response", "").strip()
        if not rag_response:
            rag_response = "I can't find related information."

        # --- 5. POST THE RESPONSE TO SLACK ---
        # Post the RAG response back to the original channel in a thread
        client.chat_update(
            channel=channel,
            ts=processing_msg_ts,
            text=rag_response
        )

        logger.info("Successfully processed query")
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        error_msg = "Sorry, I encountered an error"
        # say(
        #     text=f"{error_msg}: {e}",
        #     channel=channel,
        #     thread_ts=thread_ts
        # )
        client.chat_update(
            channel=channel,
            ts=processing_msg_ts,
            text=f"❌ {error_msg}: {e}"
        )


# Handle direct messages
@slack_app.event("message")
def handle_message(event, say, client):
    # Ignore bot messages to prevent infinite loops
    if event.get("bot_id"):
        return

    # Ignore messages in channels (only handle DMs)
    # if event.get("channel_type") != "im":
    #     return

    # Same logic as above
    handle_app_mention(event, say, client)


# ============================================================================
# FastAPI Endpoints
# ============================================================================
@api.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Slack RAG Bot is running",
        "version": "1.0.0"
    }


@api.get("/health")
async def health():
    """Detailed health check"""
    health_status = {
        "Slack": "unknown",
        "RAG API": "unknown"
    }

    # Check Slack connection
    try:
        slack_app.client.auth_test()
        health_status["slack"] = "ok"
    except Exception as e:
        health_status["slack"] = f"error: {e}"

    # Check RAG API status
    try:
        http_response = http_client.get(RAG_API_HEALTH)
        if http_response.status_code == httpx.codes.OK:
            health_status["RAG API"] = "ok"
    except Exception as e:
        health_status["RAG API"] = f"error: {e}"

    return health_status


@api.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)


# --- 6. START THE APP ---
if __name__ == "__main__":
    import uvicorn

    # Verify required environment variables
    required_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET",
        "RAG_API_ENDPOINT"
    ]

    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        exit(1)

    logger.info("🤖 Starting Slack RAG Bot...")
    uvicorn.run(
        api,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000)),
        log_level="info"
    )
