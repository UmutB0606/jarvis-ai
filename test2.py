import asyncio
from google import genai
from google.genai import types

async def test():
    c = genai.Client(api_key="AIzaSyCHp7ubu7gW9TyXpgC_oEUCvdmgWUBGw14", http_options={"api_version": "v1beta"})
    async with c.aio.live.connect(
        model="gemini-2.5-flash-native-audio-latest",
        config=types.LiveConnectConfig(response_modalities=["AUDIO"])
    ) as session:
        print("✅ Live API çalışıyor!")

asyncio.run(test())