from langchain_core.prompts import ChatPromptTemplate
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_openai import ChatOpenAI
from prompts import questionary_agent_prefix

def define_questionary_agent(questionary_agent_suffix, tools):
    prompt_questionary= ChatPromptTemplate.from_messages(
            [
                ("system", questionary_agent_prefix),
                MessagesPlaceholder(variable_name="messages"),
                ("system", questionary_agent_suffix),
                ("system","el id del paciente es {user_id}")
            ]
        )

    llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=None, timeout=None, max_retries=2,)
    if tools:
        questionary_agent = prompt_questionary | llm.bind_tools(tools)
    else:
        questionary_agent = prompt_questionary | llm
    return questionary_agent

def define_questionary_agent_with_slots(questionary_agent_suffix, tools):
    prompt_questionary= ChatPromptTemplate.from_messages(
            [
                ("system", questionary_agent_prefix),
                MessagesPlaceholder(variable_name="messages"),
                ("system", questionary_agent_suffix),
                ("system","el id del paciente es {user_id}"),
                ("system", "el estado actual del paciente es: {slots}"),

            ]
        )

    llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=None, timeout=None, max_retries=2,)
    if tools:
        questionary_agent = prompt_questionary | llm.bind_tools(tools)
    else:
        questionary_agent = prompt_questionary | llm
    return questionary_agent