import requests

def call_ai(prompt):
    response = requests.post(
        "https://your-api-endpoint",
        json={"message": prompt}
    )
    return response.json().get("response", "")

print(call_ai("Hello"))