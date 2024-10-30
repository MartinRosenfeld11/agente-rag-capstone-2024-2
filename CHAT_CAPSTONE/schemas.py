from typing import Dict, Any, List, Literal
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    ToolCall,
    message_to_dict,
    messages_from_dict,
)

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

class UserInput(BaseModel):
    """Basic user input for the agent."""
    
    message: str = Field(
        description="User input to the agent.",
        examples=["What is the weather in Tokyo?"],
    )
    model: str = Field(
        description="LLM Model to use for the agent.",
        default="gpt-4o-mini",
        examples=["gpt-4o-mini", "llama-3.1-70b"],
    )
    thread_id: Optional[str] = Field(
        description="Thread ID to persist and continue a multi-turn conversation.",
        default=None,
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    user_id: str = Field(
        description="User ID to track the user in the conversation.",
        examples=["7"],
    )
    


class StreamInput(UserInput):
    """User input for streaming the agent's response."""

    stream_tokens: bool = Field(
        description="Whether to stream LLM tokens to the client.",
        default=True,
    )


class AgentResponse(BaseModel):
    """Response from the agent when called via /invoke."""

    message: Dict[str, Any] = Field(
        description="Final response from the agent, as a serialized LangChain message.",
        examples=[
            {
                "message": {
                    "type": "ai",
                    "data": {"content": "The weather in Tokyo is 70 degrees.", "type": "ai"},
                }
            }
        ],
    )


class ChatMessage(BaseModel):
    """Message in a chat."""

    type: Literal["human", "ai", "tool"] = Field(
        description="Role of the message.",
        examples=["human", "ai", "tool"],
    )
    content: str = Field(
        description="Content of the message.",
        examples=["Hello, world!"],
    )
    tool_calls: List[Any] = Field(  # Reemplacé ToolCall por Any si no se tiene el tipo ToolCall
        description="Tool calls in the message.",
        default=[],
    )
    tool_call_id: Optional[str] = Field(
        description="Tool call that this message is responding to.",
        default=None,
        examples=["call_Jja7J89XsjrOLA5r!MEOW!SL"],
    )
    run_id: Optional[str] = Field(
        description="Run ID of the message.",
        default=None,
        examples=["847c6285-8fc9-4560-a83f-4e6285809254"],
    )
    original: Dict[str, Any] = Field(
        description="Original LangChain message in serialized form.",
        default={},
    )

    @classmethod
    def from_langchain(cls, message: BaseMessage) -> "ChatMessage":
        """Create a ChatMessage from a LangChain message."""
        original = message_to_dict(message)
        if isinstance(message, HumanMessage):
            return cls(type="human", content=message.content, original=original)
        elif isinstance(message, AIMessage):
            ai_message = cls(type="ai", content=message.content, original=original)
            if hasattr(message, 'tool_calls'):
                ai_message.tool_calls = message.tool_calls
            return ai_message
        elif isinstance(message, ToolMessage):
            return cls(
                type="tool",
                content=message.content,
                tool_call_id=message.tool_call_id,
                original=original,
            )
        else:
            raise ValueError(f"Unsupported message type: {message.__class__.__name__}")

    def to_langchain(self) -> BaseMessage:
        """Convert the ChatMessage to a LangChain message."""
        if self.original:
            return messages_from_dict([self.original])[0]
        if self.type == "human":
            return HumanMessage(content=self.content)
        else:
            raise NotImplementedError(f"Unsupported message type: {self.type}")

    def pretty_print(self) -> None:
        """Pretty print the ChatMessage."""
        lc_msg = self.to_langchain()
        lc_msg.pretty_print()


class IDusuario(BaseModel):
    """id del usuario"""
    user_id: int = Field(description="Id del paciente")

class AtributosPacientes(BaseModel):
    """Estado general del paciente"""
    estado: str = Field(description="Interpretación del estado general del paciente identificado de la conversación.Puede ser solo uno de los siguientes valores: muy mal, mal, regular, bien, muy bien")
    emociones: str = Field(description="Interpretación de la emoción general del paciente identificada en la conversación. Puede ser solo uno de los siguientes valores: alegría, miedo, tristeza, frustración, rabia")
    medicamentos: str = Field(description="Interpretación de si el paciente tomó medicamentos. Puede ser solo uno de los siguientes valores: si, no")
    efectos_adversos: str = Field(description="Interpretación de si el paciente sufrió efectos adversos por los medicamentos, si no aplica como el valor: no aplica")
    razon_no_medicamentos: str = Field(description="Razón por la cual el paciente no tomó sus medicamentos, si no aplica toma el valor: no aplica")
    intensidad_dolor: str = Field(description="Interpretacion de la intensidad del dolor sufrida por el paciente. valor valido: 1 a 10")
    realiza_ejercicios: str = Field(description="Interpretacion de si el paciente realizó los ejercicios recomendados. valor valido: si, no")
    efecto_ejercicios: str = Field(description="Interpretacion de como se ha sentido el paciente despues de los ejercicios. Puede ser solo uno de los siguientes valores: muy mal, mal, regular, bien, muy bien")
    razon_no_ejercicio: str = Field(description="Motivos por los cuales el paciente no realizó sus ejercicios, si no aplica, toma el valor: no aplica")
    calidad_sueño: str = Field(description="Cual fue la calidad de sueño del paciente la noche anterior. valor valido: muy mala, mala, buena, muy buena, excenlente")
    user_id: str = Field(description="Id del paciente")

class parse_estado_general(BaseModel):
    """Transferir datos a asistente encargado de preguntas de medicamentos"""
    estado: str = Field(description="Interpretación del estado general del paciente identificado de la conversación.Puede ser solo uno de los siguientes valores: muy mal, mal, regular, bien, muy bien")
    emociones: str = Field(description="Interpretación de la emoción general del paciente identificada en la conversación. Puede ser solo uno de los siguientes valores: alegría, miedo, tristeza, frustración, rabia")

    class Config:
        json_schema_extra = {
            "example": {
                "estado": "muy bien",
                "emociones": "alegria"
            }
        }

class parse_medicamentos(BaseModel):
    """Transferir datos a asistente encargado de preguntas del dolor"""
    medicamentos: str = Field(description="Interpretación de si el paciente tomó medicamentos. Puede ser solo uno de los siguientes valores: si, no")
    efectos_adversos: str = Field(description="Interpretación de si el paciente sufrió efectos adversos por los medicamentos, si no aplica como el valor: no aplica")
    razon_no_medicamentos: str = Field(description="Razón por la cual el paciente no tomó sus medicamentos, si no aplica toma el valor: no aplica")

    class Config:
        json_schema_extra = {
            "example": {
                "medicamentos": "si",
                "efectos_adversos": "nauseas",
                "razon_no_medicamentos": "no aplica",
            },
            "example 2": {
                "medicamentos": "no",
                "efectos_adversos": "no aplica",
                "razon_no_medicamentos": "no tiene tiempo",
            }
        }

class parse_dolor(BaseModel):
    """Transferir datos a asistente encargado de preguntas de ejercicio"""
    intensidad_dolor: str = Field(description="Interpretacion de la intensidad del dolor sufrida por el paciente. valor valido: 1 a 10")
    medicamento_sos: str = Field(description="Interpretación de si el paciente ha tomado su medicamento S.O.S,los valores validos son: si, no, no aplica")
    alerta_sos: str = Field(description="Interpretacion si se emitió una alerta o no, los valores validos son: si, no, no aplica")

    class Config:
        json_schema_extra = {
            "example": {
                "intensidad_dolor": "2",
                "medicamento_sos": "no aplica",
                "alerta_sos": "no aplica",
            },
            "example 2": {
                "intensidad_dolor": "7",
                "medicamento_sos": "si",
                "alerta_sos": "no",
            },
            "example 3": {
                "intensidad_dolor": "9",
                "medicamento_sos": "si",
                "alerta_sos": "si",
            }
        }

class parse_ejercicio(BaseModel):
    """Transferir datos a asistente encargado de preguntas del sueño"""
    realiza_ejercicios: str = Field(description="Interpretacion de si el paciente realizó los ejercicios recomendados. valor valido: si, no")
    efecto_ejercicios: str = Field(description="Interpretacion de como se ha sentido el paciente despues de los ejercicios. Puede ser solo uno de los siguientes valores: muy mal, mal, regular, bien, muy bien")
    razon_no_ejercicio: str = Field(description="Motivos por los cuales el paciente no realizó sus ejercicios, si no aplica, toma el valor: no aplica")

    class Config:
        json_schema_extra = {
            "example": {
                "realiza_ejercicios": "si",
                "efecto_ejercicios": "muy bien",
                "razon_no_ejercicio": "no aplica",
            },
            "example 2": {
                "realiza_ejercicios": "no",
                "efecto_ejercicios": "no aplica",
                "razon_no_ejercicio": "no tiene tiempo",
            }
        }

class parse_sueno(BaseModel):
    """Transferir datos a asistente encargado de preguntas del sueño"""
    calidad_sueno: str = Field(description="Cual fue la calidad de sueño del paciente la noche anterior. valor valido: muy mala, mala, buena, muy buena, excelente")
    horas_sueño: str = Field(description="Cantidad de horas de sueño del paciente la noche anterior. valor valido: numero de 1 a 24")

    class Config:
        json_schema_extra = {
            "example": {
                "calidad_sueño": "excelente",
                "horas_sueño": "8",
            }
        }