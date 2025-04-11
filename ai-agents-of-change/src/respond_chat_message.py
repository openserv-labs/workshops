from api import api_client
from typing import Dict, Any

async def respond_chat_message(action: Dict[str, Any]):
    try:
        # Extract necessary details from the action object
        workspace_id = action['workspace']['id']  # ID of the workspace where the chat is taking place
        agent_id = action['me']['id']  # ID of the agent responding to the chat
        agent_name = action['me']['name']  # Name of the agent responding to the chat
        latest_message = action['messages'][-1]['message'] if action['messages'] else None  # Latest message in the chat

        # The latest message can be used to determine the appropriate response, or you can analyze all messages in action.messages

        # Prepare the body of the response to be sent to the platform
        body = {
            "message": "This is the message I want to send to the platform"  # Replace this with the actual response message
        }

        # Send the response message to the OpenServ platform
        await api_client.post(
            f"/workspaces/{workspace_id}/agent-chat/{agent_id}/message",
            body
        )
    except Exception as e:
        # Log an error message if the response fails
        print("Failed to respond to chat message:", str(e)) 