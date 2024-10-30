import os
from typing import Annotated, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, BaseMessage, ToolMessage
from langchain.tools.render import format_tool_to_openai_function
from utils import define_questionary_agent, define_questionary_agent_with_slots
import operator
import json
from prompts import *
from schemas import *
from tools import *
from dotenv import load_dotenv

def check_api_keys():
    load_dotenv()
    required_keys = ["OPENAI_API_KEY"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        raise EnvironmentError(
            f"Faltan las siguientes variables de entorno: {', '.join(missing_keys)}"
        )

check_api_keys()

# Definición de agentes y herramientas
questionary_agent_emotions = define_questionary_agent(
    questionary_agent_suffix_emotions, [parse_estado_general, get_patient_last_report]
)
questionary_agent_medications = define_questionary_agent(
    questionary_agent_suffix_medications, [parse_medicamentos]
)
questionary_agent_pain = define_questionary_agent(
    questionary_agent_suffix_pain, [parse_dolor, send_alert]
)
questionary_agent_exercise = define_questionary_agent(
    questionary_agent_suffix_exercise, [parse_ejercicio]
)
questionary_agent_sleep = define_questionary_agent_with_slots(
    questionary_agent_suffix_sleep, [save_patient_report]
)

tools = [get_patient_last_report, send_alert, save_patient_report, parse_estado_general, get_patient_last_report]
tool_executor = ToolNode(tools)

class HealthAssistant(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    slots: Dict[str, Any]
    agent: int
    user_id: int
    stage: int

def is_tool_call(msg):
    return hasattr(msg, "additional_kwargs") and 'function' in msg.additional_kwargs

def create_ai_message(questionary_response):
    return AIMessage(
        **questionary_response.dict(
            exclude={"type", "name", "response_metadata", "id"}
        )
    )

async def process_questionary_agent(
    state, agent, next_stage, special_cases=None
):
    while True:
        local_messages = state.get("messages", [])
        questionary_response = await agent.ainvoke(
            {**state, "messages": local_messages}
        )
        if not questionary_response.tool_calls and not questionary_response.content:
            local_messages += [("user", "Por favor responde con un output real")]
        else:
            break
    if not questionary_response.tool_calls:
        # Actualizar messages en el estado
        new_state = {
            "messages":[create_ai_message(questionary_response)],
            "slots": state.get("slots", {}),
            "stage": state.get("stage", 1)
        }
        return new_state
    else:
        function_name = questionary_response.additional_kwargs['tool_calls'][0]['function']['name']
        if special_cases and function_name in special_cases:
            return special_cases[function_name](state, questionary_response, next_stage)
        else:
            tool_call_id = questionary_response.additional_kwargs['tool_calls'][0]['id']
            messages = [create_ai_message(questionary_response)]
            slots_loads = json.loads(
                questionary_response.additional_kwargs['tool_calls'][0]['function']['arguments']
            )
            slots = state.get("slots", {})
            slots.update(slots_loads)
            messages.append(ToolMessage(slots_loads, tool_call_id=tool_call_id))
            new_state = {
                "stage": next_stage,
                "slots": slots,
                "messages": messages
            }
            return new_state

# Definición de funciones para cada etapa del cuestionario
async def questionary_agent_func_emotions(state):
    if 'stage' not in state:
        state['stage'] = 1
    if 'slots' not in state:
        state['slots'] = {}
    if 'messages' not in state:
        state['messages'] = []

    def handle_verify_selfreport(state, questionary_response, next_stage):
        messages = [
            AIMessage(
                content='Genial, primero verificaré que no hayas respondido tu autoreporte hoy',
                additional_kwargs=questionary_response.additional_kwargs
            )
        ]
        new_state = {
            "messages": messages,
            "slots": state.get("slots", {}),
            "stage": state.get("stage", 1)
        }
        return new_state
    special_cases = {'verify_selfreport': handle_verify_selfreport}
    return await process_questionary_agent(
        state, questionary_agent_emotions, next_stage=2, special_cases=special_cases
    )

async def questionary_agent_func_medications(state):
    return await process_questionary_agent(
        state, questionary_agent_medications, next_stage=3
    )

async def questionary_agent_func_pain(state):
    def handle_send_alert(state, questionary_response, next_stage):
        messages = [
            AIMessage(
                content='Perfecto, emitiré una alerta al equipo médico para advertirles lo que me cuentas',
                additional_kwargs=questionary_response.additional_kwargs
            )
        ]
        new_state = {
            "messages": messages,
            "slots": state.get("slots", {}),
            "stage": state.get("stage", 3)
        }
        return new_state
    special_cases = {'send_alert': handle_send_alert}
    return await process_questionary_agent(
        state, questionary_agent_pain, next_stage=4, special_cases=special_cases
    )

async def questionary_agent_func_exercise(state):
    return await process_questionary_agent(
        state, questionary_agent_exercise, next_stage=5
    )

async def questionary_agent_func_sleep(state):
    def handle_atributos_pacientes(state, questionary_response, next_stage):
        messages = [create_ai_message(questionary_response)]
        new_state = {
            "messages": messages,
            "slots": state.get("slots", {}),
            "stage": state.get("stage", 5)
        }
        return new_state
    
    special_cases = {'AtributosPacientes': handle_atributos_pacientes}
    return await process_questionary_agent(
        state, questionary_agent_sleep, next_stage=6, special_cases=special_cases
    )

def state_analyzer_questionary(state):
    stage = int(state.get("stage", 1))
    stage_mapping = {
        1: "emotions",
        2: "medications",
        3: "pain",
        4: "exercise",
        5: "sleep"
    }
    return stage_mapping.get(stage, END)

def sandbox(state):
    return state

def route_chatbot_tools_emotions(state):
    return route_chatbot_tools(state, current_stage=1, next_stage_name="medications", end_stage=2)

def route_chatbot_tools_medications(state):
    return route_chatbot_tools(state, current_stage=2, next_stage_name="pain", end_stage=3)

def route_chatbot_tools_pain(state):
    return route_chatbot_tools(state, current_stage=3, next_stage_name="exercise", end_stage=4)

def route_chatbot_tools_exercise(state):
    return route_chatbot_tools(state, current_stage=4, next_stage_name="sleep", end_stage=5)

def route_chatbot_tools_sleep(state):
    return route_chatbot_tools(state, current_stage=5, next_stage_name=END, end_stage=6)

def route_tools_chatbot(state):
    messages = state.get("messages", [])
    last_m = messages[-1] if messages else None
    name_to_route = {
        "verify_selfreport": "emotions",
        "send_alert": "pain",
        "AtributosPacientes": "sleep",
    }
    if isinstance(last_m, ToolMessage):
        tool_name = last_m.name
        return name_to_route.get(tool_name, END)
    else:
        return END

workflow = StateGraph(HealthAssistant)
workflow.add_node("emotions", questionary_agent_func_emotions)
workflow.add_node("medications", questionary_agent_func_medications)
workflow.add_node("pain", questionary_agent_func_pain)
workflow.add_node("exercise", questionary_agent_func_exercise)
workflow.add_node("sleep", questionary_agent_func_sleep)
workflow.add_node("tools", tool_executor)
workflow.add_node("cuestionario", sandbox)
workflow.add_conditional_edges("cuestionario", state_analyzer_questionary, {"emotions":"emotions", "medications":"medications", "sleep":"sleep", "exercise":"exercise", "pain":"pain", END:END})

# Establecer el punto de entrada del flujo de trabajo de manera dinámica
workflow.set_entry_point("cuestionario")

# Añadir transiciones condicionales entre nodos
workflow.add_conditional_edges(
    "emotions",
    route_chatbot_tools_emotions,
    {"medications": "medications", "tools": "tools", END: END}
)
workflow.add_conditional_edges(
    "medications",
    route_chatbot_tools_medications,
    {"pain": "pain", "tools": "tools", END: END}
)
workflow.add_conditional_edges(
    "pain",
    route_chatbot_tools_pain,
    {"exercise": "exercise", "tools": "tools", END: END}
)
workflow.add_conditional_edges(
    "exercise",
    route_chatbot_tools_exercise,
    {"sleep": "sleep", "tools": "tools", END: END}
)
workflow.add_conditional_edges(
    "sleep",
    route_chatbot_tools_sleep,
    {"tools": "tools", END: END}
)
workflow.add_conditional_edges(
    "tools",
    route_tools_chatbot,
    {"emotions": "emotions", "medications": "medications", "pain": "pain", "exercise": "exercise", "sleep": "sleep", END: END}
)

def route_chatbot_tools(state, current_stage, next_stage_name, end_stage):
    messages = state.get("messages", [])
    stage = int(state.get("stage", 1))
    last_message = messages[-1] if messages else None
    if isinstance(last_message, AIMessage):
        if not last_message.tool_calls and stage == current_stage:
            return END
        else:
            if stage == end_stage:
                return next_stage_name
            else:
                return "tools"
    if isinstance(last_message, ToolMessage):
        if stage == end_stage:
            return next_stage_name
        else:
            return "tools"
    return END

graph = workflow

if __name__ == "__main__":
    import asyncio
    from uuid import uuid4
    from dotenv import load_dotenv

    load_dotenv()
    
    async def main():
        inputs = {"messages": [HumanMessage(content="bien, mucha alegria")], 'user_id': "1"}
        async for output in graph.astream(inputs, stream_mode="updates", 
                                              config=RunnableConfig(configurable={"thread_id": uuid4()}),):
            # stream_mode="updates" yields dictionaries with output keyed by node name
            for key, value in output.items():
                print(f"Output from node '{key}':")
                print("---")
                print(value["messages"][-1].pretty_print())
            print("\n---\n")

    asyncio.run(main())