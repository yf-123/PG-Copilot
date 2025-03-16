#!/usr/bin/env python3
# Letta/memgpt model to Open-Webui OpenAI API server
"""
Put this file where you installed letta container / env- change (last line) port to your needs - run it 
In Open-Webui  admin/settings connections:
add LETTA_MEMGPT as an OpenAI API connection
ie: http://localhost:8088/v1

"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json
from agent import lettaClient

app = FastAPI()
agent_client = lettaClient()

# Add your open-webui user : memgpt corresponding agents / Add {{USER_NAME}} in your Model System Prompt
# agents = {
#     "admin": "agent-bce9c276-64d7-4337-be57-aadae77d641c",
#     "user1": "agent-68e9ff22-4e94-4f0c-a838-f626fa8a6d82"
# }

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = 100
    stream: Optional[bool] = False


@app.post("/v1/chat/completions-ns")
# non-streaming version
async def chat_completion_ns(request: ChatCompletionRequest):
    messages = request.messages
    agent_id = agent_client.get_agent(messages[0].content)
    if not agent_id:
        return {"choices": [{"delta": {"role": "assistant", "content": "Agent not found"}}], "finish_reason": "stop"}
    try:
        response = agent_client.send_message(
            agent_name="recruiter_agent",
            message=messages[-1].content,
            role="user",
        )
        print("++++++++++++++++++++++++++++++")
        print(f"{response.model_dump_json()}")
        return response
    except Exception as e:
        return {"choices": [{"delta": {"role": "assistant", "content": str(e)}}], "finish_reason": "stop"}



@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")

async def stream_response(request: ChatCompletionRequest):
    artifacts ="""
    Artifacts
"""
    print(request.messages[0].content)
    agent_id = agent_client.get_agent(request.messages[0].content)

    if not agent_id:
        yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': f'Agent not found'}}]})}\n\n"
        yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n"
        yield "data: [DONE]\n\n"
        return
				
    #agent_id = "agent-3ee94ac8-265e-47a3-b58e-a06c67f7f777"
    print(f'Agent ID: {agent_id}')
    response = agent_client.send_message(
        # agent_id=agent_id,
        agent_name="recruiter_agent",
        message=request.messages[-1].content,
        role="user",
    )
	#LETTA OBJ PARSE
    for message_group in response.messages:
        internal_monologue = None
        function_call_message = None
        function_return = None

        if hasattr(message_group, 'internal_monologue'):
            internal_monologue = f"""
<details>
<summary>Internal Monologue:</summary>
{str(message_group.internal_monologue)} 
</details>\n\n"""

            yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': f'{internal_monologue}'}}]})}\n\n"
            await asyncio.sleep(0.01)

        if hasattr(message_group, 'function_call'):
            function_call = message_group.function_call
            if function_call.name == 'send_message':
                function_call_message = json.loads(function_call.arguments)['message']
                yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': f'{function_call_message}'}}]})}\n\n"
                await asyncio.sleep(0.01)

        # Yield function return if present
        #if function_return:
        #    yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant', 'content': f'[Function Return] {function_return}'}}]})}\n\n"
        #    await asyncio.sleep(0.01)
			 
    yield f"data: {json.dumps({'choices': [{'delta': {'content': f'{artifacts}'}}]})}\n\n"
    yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"
    artifacts =""

@app.get("/v1/init")
async def init():
    agent_client.create_agent('eval_agent')
    agent_client.create_agent('outreach_agent')
    agent_client.create_agent('recruiter_agent')
    return {"message": "Initialization successful"}

@app.get("/v1/agents")
async def get_agent_by_name(agent_name: str):
    agent_id = agent_client.get_agent_id(agent_name=agent_name)
    if not agent_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent_id": agent_id}

@app.get("/v1/models")
async def models():
    agent_list = []
    agent_list.append({'eval_agent': agent_client.get_agent_id('eval_agent')})
    agent_list.append({'outreach_agent': agent_client.get_agent_id('outreach_agent')})
    agent_list.append({'recruiter_agent': agent_client.get_agent_id('recruiter_agent')})
    return {"data": agent_list, "object": "list"}

@app.get("/v1/cleanup")
async def cleanup():
    # agent_client.delete_agent(agent_client.get_agent_id('eval_agent'))
    # agent_client.delete_agent(agent_client.get_agent_id('outreach_agent'))
    # agent_client.delete_agent(agent_client.get_agent_id('recruiter_agent'))

    for agent in agent_client.list_agents(): 
        agent_client.delete_agent(agent.id)
    return {"message": "Cleanup successful"}

@app.get("/v1")
async def root():
    return {"message": "Welcome to the Project"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)