from langchain_core.tools import tool
from schemas import IDusuario, AtributosPacientes

@tool("verify_selfreport", args_schema=IDusuario, return_direct=True)
def get_patient_last_report(user_id: int):
    return f"autoreporte no respondido"

@tool("send_alert", args_schema=IDusuario, return_direct=True)
def send_alert(user_id: int):
    return f"Alerta emitida exitosamente para el id de usuario {user_id}"

@tool("save_patient_report", args_schema=AtributosPacientes, return_direct=True)
def save_patient_report(data: AtributosPacientes):
    return f"autoreporte guardado exitosamente"