import os
import json

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def analyze_investor_text(text):

    text = text[:15000]

    prompt = f"""

You are an institutional LP analyst.

Extract ONLY meaningful PE/VC investment data.

Ignore:
- navigation
- marketing language
- cookie banners
- generic bios

Focus on:
- fund managers
- fund names
- investment strategy
- sectors
- geography
- exits
- portfolio companies
- performance metrics
- IRR
- TVPI
- DPI
- assets under management
- fund size
- vintage year

Return ONLY valid JSON.

Return a JSON array.

Example:

[
  {{
    "manager_name": "",
    "firm_name": "",
    "strategy": "",
    "sector_focus": "",
    "fund_name": "",
    "fund_size": "",
    "irr": "",
    "tvpi": "",
    "dpi": "",
    "vintage_year": "",
    "aum": "",
    "notable_investments": "",
    "hq": ""
  }}
]

TEXT:
{text}

"""

    try:

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0
        )

        content = response.choices[0].message.content

        print("\nAI RAW RESPONSE:\n")
        print(content)

        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

        parsed = json.loads(content)

        return parsed

    except Exception as e:

        print("\nAI ERROR:")
        print(e)

        return []