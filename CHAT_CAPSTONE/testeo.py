import requests
import json

# URL a la que se enviará la solicitud POST
url = 'http://a02e0d0c2dbb0472ab0c68ff9e62c7e2-120707356.us-east-1.elb.amazonaws.com/stream'

# Encabezados de la solicitud
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer UkbbZ8ca87A8SYTZjHTknIoc+VsdFaJu9aDwC/AGF4U='  # Asegúrate de que este token es correcto
}

# Datos que se enviarán en el cuerpo de la solicitud
payload = {
    "message":"alegria",
    "model": "gpt-4",  # Verifica que este es el nombre correcto del modelo
    "thread_id": "123",
    "user_id": "1",
    "stream_tokens": True
}

try:
    # Realiza la solicitud POST
    response = requests.post(url, headers=headers, json=payload, timeout=10)  # Añadido timeout de 10 segundos

    # Imprime el código de estado y el contenido de la respuesta
    print(f"Código de estado: {response.status_code}")
    print(f"Contenido de la respuesta: {response.text}")

    # Intenta parsear la respuesta como JSON solo si el código de estado es 200
    if response.status_code == 200:
        try:
            response_data = response.json()
            print("Respuesta exitosa:", json.dumps(response_data, indent=4))
        except json.JSONDecodeError:
            print("La respuesta no es un JSON válido.")
    else:
        print(f"Error: {response.status_code} - {response.text}")

except requests.exceptions.Timeout:
    print("Error: La solicitud ha excedido el tiempo de espera.")
except requests.exceptions.ConnectionError:
    print("Error: No se pudo conectar al servidor.")
except requests.exceptions.RequestException as e:
    print(f"Ocurrió un error al realizar la solicitud: {e}")
