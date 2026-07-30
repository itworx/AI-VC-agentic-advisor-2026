from dotenv import load_dotenv
import os

load_dotenv()

from langchain_openai import ChatOpenAI
from backend.models.claim import SpecialistOutput

llm = ChatOpenAI(model="anthropic/claude-sonnet-4.6",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),)

structured_llm = llm.with_structured_output(SpecialistOutput)

result = structured_llm.invoke(
    """
    Return one claim.

    Company: Instabug

    Claim:
    Instabug sells mobile app observability software.

    Source:
    https://instabug.com

    Quote:
    Mobile app observability platform.

    Specialist:
    company_intel

    Confidence:
    verified

    Category:
    what_company_does
    """
)

print(result)
print(type(result))