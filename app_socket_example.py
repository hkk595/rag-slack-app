import os
import httpx
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

# --- 1. SET UP YOUR TOKENS ---
# It's best practice to set these as environment variables
# export SLACK_BOT_TOKEN="xoxb-..."
# export SLACK_APP_TOKEN="xapp-..."

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_USER_OAUTH_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_LEVEL_TOKEN", "")

# --- 2. INITIALIZE THE APPS ---
# Initialize Slack Bolt app
app = App(token=SLACK_BOT_TOKEN)

# HTTPX client
RAG_API_ENDPOINT = os.environ.get("RAG_API_ENDPOINT", "")
http_client = httpx.Client(timeout=60.0)


# --- 3. DEFINE THE EVENT HANDLER ---
# This decorator listens for any message that @mentions the bot
@app.event("app_mention")
def handle_app_mention(event, say, client):
    """
    This function is triggered when the bot is @mentioned.
    """
    # Get the text from the user's message
    user_message = event["text"]

    # Get the channel ID and thread timestamp (if it's in a thread)
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event.get("ts"))

    # Acknowledge the request immediately with an emoji
    try:
        app.client.reactions_add(
            channel=channel_id,
            timestamp=event["ts"],
            name="face_with_monocle"  # Or any emoji you like
        )
    except Exception as e:
        print(f"Error adding reaction: {e}")

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
        say(
            text=rag_response,
            channel=channel_id,
            thread_ts=thread_ts  # This replies in a thread
        )

    except Exception as e:
        print(f"Error calling RAG API or posting to Slack: {e}")
        say(
            text=f"Sorry, I ran into an error: {e}",
            channel=channel_id,
            thread_ts=thread_ts
        )


# Handle direct messages
@app.event("message")
def handle_message(event, say):
    # Ignore bot messages
    if event.get("bot_id"):
        return

    # Same logic as above
    handle_app_mention(event, say, None)


# --- 6. START THE APP ---
if __name__ == "__main__":
    print("🤖 Bot is starting in Socket Mode...")
    # SocketModeHandler listens for events from Slack via WebSocket
    # SocketModeHandler(app, SLACK_APP_TOKEN).start()
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
