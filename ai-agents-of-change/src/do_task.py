import os
import aiohttp
from openai import OpenAI
from typing import Dict, Any
from dotenv import load_dotenv
from api import api_client

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def do_task(action: Dict[str, Any]):
    try:
        workspace_id = action['workspace']['id']
        task_id = action['task']['id']
        task_input = action['task'].get('input', '')
        task_objective = action['task'].get('description', '')
        task_expected_output = action['task'].get('expectedOutput', '')

        messages = [
            {"role": "system", "content": "Summarize the given text in exactly three sentences. Capture the main points and key insights. Ensure clarity and coherence. Use concise and straightforward language."},
            {"role": "user", "content": f"Objective: {task_objective}\nInput: {task_input}\nExpected Output: {task_expected_output}"}
        ]

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        # Extract and validate result
        if not completion.choices or not completion.choices[0].message:
            raise ValueError("Invalid response from OpenAI")
        
        result = completion.choices[0].message.content.strip()

        # Upload file using API client's upload_file method
        await api_client.upload_file(
            workspace_id=workspace_id,
            file_content=result,
            filename=f'task-{task_id}-output.txt',
            path='text-summary.txt',
            task_ids=[task_id],
            skip_summarizer=True
        )

        # Mark task as complete with the same message as TypeScript
        try:
            # First verify task exists and is in valid state
            session = await api_client.ensure_session()
            async with session.get(
                f"{api_client.base_url}/workspaces/{workspace_id}/tasks/{task_id}/detail"
            ) as task_response:
                if task_response.status != 200:
                    error_text = await task_response.text()
                    raise Exception(f"Task not found or invalid state. Status: {task_response.status}, Response: {error_text}")

            # Complete the task with proper payload
            await api_client.put(
                f"/workspaces/{workspace_id}/tasks/{task_id}/complete",
                {'output': "The summary has been uploaded"}
            )

        except Exception as complete_error:
            raise Exception(f"Failed to complete task: {str(complete_error)}")

    except Exception as e:
        try:
            # Report error using API client with more detailed error message
            error_message = f"Task processing failed: {str(e)}"
            await api_client.post(
                f"/workspaces/{workspace_id}/tasks/{task_id}/error",
                {'error': error_message}
            )
        except Exception as report_error:
            print(f"Failed to report error: {str(report_error)}") 