from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from backend.models.claim import SpecialistOutput

llm = ChatOpenAI(model="gpt-4o-mini")

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