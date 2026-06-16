import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_manager_web_research(manager_name):
    if not manager_name or str(manager_name).strip() == "":
        return "No manager name provided."

    prompt = f"""
Research the private equity / venture capital manager: {manager_name}.

Find useful allocator-relevant background if available:
- official website
- founding year
- headquarters
- AUM
- strategy focus
- senior team / key partners
- notable funds
- notable portfolio companies
- recent fundraising
- recent news
- risks or controversies

Return a concise but useful research brief.
If you are not sure about something, say that clearly.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        tools=[
            {
                "type": "web_search_preview"
            }
        ],
        input=prompt
    )

    return response.output_text