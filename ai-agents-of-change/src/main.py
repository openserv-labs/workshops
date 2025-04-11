import os
import uvicorn
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from api import api_client
from ethical_contrast_agent import EthicalContrastAgent

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI()

# Initialize the ethical contrast agent
agent = EthicalContrastAgent()

@app.post("/chat-message")
async def handle_chat_message(request: Request, background_tasks: BackgroundTasks):
    """Handle chat message webhook from OpenServ platform"""
    try:
        action = await request.json()
        # Process chat message in the background
        background_tasks.add_task(agent.respond_chat_message, action)
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling chat message: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/task")
async def handle_task(request: Request, background_tasks: BackgroundTasks):
    """Handle task webhook from OpenServ platform"""
    try:
        action = await request.json()
        # For simplicity, we'll just send a message in chat for tasks
        workspace_id = action['workspace']['id']
        agent_id = action['me']['id']
        task_id = action['task']['id']
        task_desc = action['task'].get('description', 'No description provided')
        
        # Send a message acknowledging the task
        message = f"I've received a task: {task_desc}\n\nI'm designed to show ethical contrast, not to perform tasks. Try chatting with me instead!"
        
        background_tasks.add_task(
            agent.send_to_openserv, 
            workspace_id, 
            agent_id, 
            message
        )
        
        # Mark task as complete
        await api_client.put(
            f"/workspaces/{workspace_id}/tasks/{task_id}/complete",
            {'output': "This agent doesn't process tasks, but it can chat!"}
        )
        
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling task: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    print("Ethical Contrast Agent starting...")

@app.on_event("shutdown")
async def shutdown_event():
    # Close the API client session
    await api_client.close()
    print("Ethical Contrast Agent shutting down...")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7378))
    # Run uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=port) 