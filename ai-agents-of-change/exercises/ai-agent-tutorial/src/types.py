from enum import Enum
from typing import Optional, List, Dict, Any, Union, Literal, Callable
from pydantic import BaseModel, Field, root_validator
from datetime import datetime

class AgentKind(str, Enum):
    EXTERNAL = 'external'
    ELIZA = 'eliza'
    OPENSERV = 'openserv'

class TaskStatus(str, Enum):
    TODO = 'to-do'
    IN_PROGRESS = 'in-progress'
    HUMAN_ASSISTANCE_REQUIRED = 'human-assistance-required'
    ERROR = 'error'
    DONE = 'done'
    CANCELLED = 'cancelled'

class AgentBase(BaseModel):
    id: int
    name: str
    kind: AgentKind
    isBuiltByAgentBuilder: bool = False
    systemPrompt: Optional[str] = None
    capabilities_description: Optional[str] = None

class Agent(BaseModel):
    id: int
    name: str
    kind: Optional[AgentKind] = None
    capabilities_description: Optional[str] = None

class TaskAttachment(BaseModel):
    id: int
    path: str
    fullUrl: str
    summary: Optional[str] = None

class TaskDependency(BaseModel):
    id: int
    description: str
    output: Optional[str] = None
    status: TaskStatus
    attachments: List[TaskAttachment] = []

class HumanAssistanceRequest(BaseModel):
    id: int
    agentDump: Optional[Any] = None
    humanResponse: Optional[str] = None
    question: Any
    status: Literal['pending', 'responded']
    type: Literal['text', 'json', 'project-manager-plan-review', 'insufficient-balance']

class Task(BaseModel):
    id: int
    description: str
    body: Optional[str] = None
    expectedOutput: Optional[str] = None
    input: Optional[str] = None
    dependencies: List[TaskDependency] = []
    humanAssistanceRequests: List[HumanAssistanceRequest] = []

class Workspace(BaseModel):
    id: int
    goal: str
    bucket_folder: str
    agents: List[Agent]

class Integration(BaseModel):
    id: int
    connection_id: str
    provider_config_key: str
    provider: str
    created: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    scopes: Optional[List[str]] = None
    openAPI: Dict[str, str]

class Memory(BaseModel):
    id: int
    memory: str
    createdAt: datetime = Field(default_factory=datetime.now)

class AgentAction(BaseModel):
    type: Literal['do-task', 'respond-chat-message']
    me: AgentBase
    task: Optional[Task] = None
    workspace: Workspace
    integrations: List[Integration] = []
    memories: List[Memory] = []

class DoTaskAction(AgentAction):
    type: Literal['do-task']
    task: Task

class ChatMessage(BaseModel):
    author: Literal['user', 'agent']
    message: str
    id: int
    createdAt: datetime

class RespondChatMessageAction(AgentAction):
    type: Literal['respond-chat-message']
    messages: List[ChatMessage]

class MessageDict(BaseModel):
    """
    A message dict with flexible ID type to match TypeScript SDK.
    Handles both string and integer IDs.
    """
    role: str
    content: Optional[str] = ''
    id: Optional[Union[str, int]] = None
    createdAt: Optional[Union[str, datetime]] = None
    tool_calls: Optional[Any] = None
    tool_call_id: Optional[str] = None
    
    class Config:
        extra = "allow"

class ProcessParams(BaseModel):
    """
    Parameters for the process method.
    
    This model handles messages from various sources, including the OpenAI API
    and the OpenServ runtime, ensuring compatibility with the TypeScript SDK.
    """
    messages: List[Union[Dict[str, Any], MessageDict]]
    
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
    
    @root_validator(pre=True)
    def ensure_message_format(cls, values):
        """
        Ensures that messages are in the correct format, handling both dictionary
        and MessageDict instances, and converting IDs as needed.
        """
        if 'messages' in values:
            # Convert all messages to properly handle ID types
            formatted_messages = []
            
            for msg in values['messages']:
                # If already a dict, ensure IDs are properly handled
                if isinstance(msg, dict):
                    # If the message has an ID, ensure it's kept as is (no string conversion)
                    formatted_msg = dict(msg)
                    formatted_messages.append(formatted_msg)
                else:
                    # If it's not a dict (e.g., MessageDict), convert to dict
                    formatted_messages.append(msg.dict())
            
            values['messages'] = formatted_messages
        
        return values

class AgentOptions(BaseModel):
    system_prompt: str
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    port: Optional[int] = None
    model: Optional[str] = None
    on_error: Optional[Callable[[Exception, Dict[str, Any]], None]] = None

class GetFilesParams(BaseModel):
    workspace_id: int

class GetSecretsParams(BaseModel):
    workspace_id: int

class GetSecretValueParams(BaseModel):
    workspace_id: int
    secret_id: str

class UploadFileParams(BaseModel):
    workspace_id: int
    path: str
    task_ids: Optional[Union[List[int], int, None]] = None
    skip_summarizer: Optional[bool] = None
    file: Union[bytes, str]

class MarkTaskAsErroredParams(BaseModel):
    workspace_id: int
    task_id: int
    error: str

class CompleteTaskParams(BaseModel):
    workspace_id: int
    task_id: int
    output: str

class SendChatMessageParams(BaseModel):
    workspace_id: int
    agent_id: int
    message: str

class GetTaskDetailParams(BaseModel):
    workspace_id: int
    task_id: int

class GetAgentsParams(BaseModel):
    workspace_id: int

class GetTasksParams(BaseModel):
    workspace_id: int

class CreateTaskParams(BaseModel):
    workspace_id: int
    assignee: int
    description: str
    body: str
    input: str
    expected_output: str
    dependencies: List[int]

class AddLogToTaskParams(BaseModel):
    workspace_id: int
    task_id: int
    severity: Literal['info', 'warning', 'error']
    type: Literal['text', 'openai-message']
    body: Union[str, dict]

class RequestHumanAssistanceParams(BaseModel):
    workspace_id: int
    task_id: int
    type: Literal['text', 'project-manager-plan-review']
    question: Union[str, dict]
    agent_dump: Optional[dict] = None

class UpdateTaskStatusParams(BaseModel):
    workspace_id: int
    task_id: int
    status: TaskStatus

class ProxyConfiguration(BaseModel):
    endpoint: str
    provider_config_key: Optional[str] = None
    connection_id: Optional[str] = None
    method: Optional[Literal['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'get', 'post', 'patch', 'put', 'delete']] = None
    headers: Optional[Dict[str, str]] = None
    params: Optional[Union[str, Dict[str, Union[str, int]]]] = None
    data: Optional[Any] = None
    retries: Optional[int] = None
    base_url_override: Optional[str] = None
    decompress: Optional[bool] = None
    response_type: Optional[Literal['arraybuffer', 'blob', 'document', 'json', 'text', 'stream']] = None
    retry_on: Optional[List[int]] = None

class IntegrationCallRequest(BaseModel):
    workspace_id: int
    integration_id: str
    details: ProxyConfiguration 
