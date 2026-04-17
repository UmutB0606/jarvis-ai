from google import genai
client = genai.Client(api_key="AIzaSyDr408AxxjZXeJFgacFda9XEzsc027DfYg")
for model in client.models.list():
    print(model.name)