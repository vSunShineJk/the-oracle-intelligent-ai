import os

from pydantic_ai import Agent
from openai import AsyncAzureOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from dotenv import load_dotenv

load_dotenv()

def azure_agent(system_prompt: str = "") -> Agent:
    azure_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )

    provider = OpenAIProvider(openai_client=azure_client)
    model = OpenAIChatModel(os.getenv("AZURE_OPENAI_DEPLOYMENT"), provider=provider)

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        instrument=True,  # Enable tool use
    )
    return agent