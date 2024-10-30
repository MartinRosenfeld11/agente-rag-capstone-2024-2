import asyncio
from contextlib import asynccontextmanager
import json
import os
from typing import AsyncGenerator, Dict, Any, Tuple
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.graph import CompiledGraph
from psycopg_pool import AsyncConnectionPool
from async_agent import graph
from schemas import ChatMessage, UserInput, StreamInput
import psycopg
import logging

def check_environment_variables():
    required_vars = ["DB_HOST", "DB_NAME", "DB_PORT"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")
    else:
        print("All required environment variables are set:")
        for var in required_vars:
            print(f"{var}: {os.getenv(var)}")

check_environment_variables()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
DB_MAX_CONNECTIONS = 20

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}

class TokenQueueStreamingHandler(AsyncCallbackHandler):
    """LangChain callback handler for streaming LLM tokens to an asyncio queue."""

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if token:
            await self.queue.put(token)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the AsyncConnectionPool (using connection details without user and password)
    async with AsyncConnectionPool(
        conninfo=DB_URI,
        max_size=DB_MAX_CONNECTIONS,
        kwargs=connection_kwargs,
    ) as pool:
        # Create the AsyncPostgresSaver
        checkpointer = AsyncPostgresSaver(pool)
        
        # Set up the checkpointer (uncomment this line the first time you run the app)
        await checkpointer.setup()
        
        # Check if the checkpoints table exists
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE  table_schema = 'public'
                            AND    table_name   = 'checkpoints'
                        );
                    """)
                    table_exists = (await cur.fetchone())[0]
                    
                    if not table_exists:
                        print("Checkpoints table does not exist. Running setup...")
                        await checkpointer.setup()
                    else:
                        print("Checkpoints table already exists. Skipping setup.")
                except psycopg.Error as e:
                    print(f"Error checking for checkpoints table: {e}")

        checkpointer = checkpointer
        app.state.agent = graph.compile(checkpointer=checkpointer)
        yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def read_health():
    return {"status": "ok"}

@app.middleware("http")
async def check_auth_header(request: Request, call_next):
    # Excluir el endpoint /health de la autenticación
    if request.url.path == "/health":
        return await call_next(request)
    
    auth_secret = os.getenv("AUTH_SECRET")
    if auth_secret:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(status_code=401, content="Missing or invalid token")
        token = auth_header[7:]  # Eliminar "Bearer " del inicio
        if token != auth_secret:
            return Response(status_code=401, content="Invalid token")
    return await call_next(request)

def _parse_input(user_input: UserInput) -> Tuple[Dict[str, Any], str]:
    run_id = uuid4()
    thread_id = user_input.thread_id or str(uuid4())
    user_id = str(user_input.user_id)
    # Prepare the initial message
    input_message = ChatMessage(type="human", content=user_input.message)

    kwargs = dict(
        input={"messages": [input_message.to_langchain()],"user_id": user_id},
        config=RunnableConfig(
            configurable={"thread_id": thread_id, "model": user_input.model},
            run_id=run_id,
        ),
    )
    return kwargs, run_id

@app.post("/invoke")
async def invoke(user_input: UserInput) -> ChatMessage:
    agent: CompiledGraph = app.state.agent
    kwargs, run_id = _parse_input(user_input)
    try:
        response_state = await agent.ainvoke(**kwargs)
        latest_message = response_state["messages"][-1]
        output = ChatMessage.from_langchain(latest_message)
        output.run_id = str(run_id)
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def message_generator(user_input: StreamInput) -> AsyncGenerator[str, None]:
    agent: CompiledGraph = app.state.agent
    kwargs, run_id = _parse_input(user_input)
    output_queue = asyncio.Queue(maxsize=10)
    if user_input.stream_tokens:
        kwargs["config"]["callbacks"] = [TokenQueueStreamingHandler(queue=output_queue)]
    async def run_agent_stream():
        try:
            async for state_update in agent.astream(**kwargs, stream_mode="updates"):
                print(state_update, flush = True)
                await output_queue.put(state_update)
        except Exception as e:
            await output_queue.put({'error': str(e)})
        finally:
            await output_queue.put(None)
    stream_task = asyncio.create_task(run_agent_stream())

    while state_update := await output_queue.get():
        if isinstance(state_update, str):
            yield f"data: {json.dumps({'type': 'token', 'content': state_update})}\n\n"
            continue
        new_messages = []
        for _, state in state_update.items():
            if 'messages' in state:
                new_messages.extend(state['messages'])
        for message in new_messages:
                try:
                    chat_message = ChatMessage.from_langchain(message)
                    chat_message.run_id = str(run_id)
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'Error parsing message: {e}'})}\n\n"
                    continue
                if chat_message.type == "human" and chat_message.content == user_input.message:
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.dict()})}\n\n"

    await stream_task
    yield "data: [DONE]\n\n"


@app.post("/stream")
async def stream_agent(user_input: StreamInput):
    """
    Stream the agent's response to a user input, including intermediate messages and tokens.

    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.
    """
    return StreamingResponse(message_generator(user_input), media_type="text/event-stream")
