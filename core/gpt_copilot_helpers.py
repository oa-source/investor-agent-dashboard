import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

DB_FILE = "institutional_funds.db"

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).lower()

def row_matches_text(value, words):
    text = safe_text(value)
    return any(word in text for word in words if len(word) > 2)

def load_copilot_data():
    conn = sqlite3.connect(DB_FILE)

    managers = pd.read_sql("SELECT * FROM manager_profiles", conn)
    funds = pd.read_sql("SELECT * FROM institutional_fund_timeseries_summary", conn)
    matches = pd.read_sql("SELECT * FROM unified_fund_matches", conn)
    timeseries = pd.read_sql("SELECT * FROM institutional_fund_timeseries", conn)

    conn.close()

    return managers, funds, matches, timeseries

def search_relevant_data(question, managers, funds, matches, timeseries):
    q = question.lower()

    stopwords = {
        "what", "think", "about", "the", "for", "and", "with",
        "give", "me", "a", "an", "full", "in", "depth", "of",
        "manager", "company", "fund", "do", "you", "is", "are",
        "compare", "to", "versus", "vs"
    }

    words = [
        w.strip().lower()
        for w in q.replace("?", "").replace(",", " ").split()
        if w.strip().lower() not in stopwords and len(w.strip()) > 2
    ]

    if not words:
        words = q.split()

    manager_hits = managers[
        managers["manager_name"].apply(lambda x: row_matches_text(x, words))
    ].head(20)

    fund_hits = funds[
        funds["fund_name"].apply(lambda x: row_matches_text(x, words))
    ].head(30)

    match_hits = matches[
        matches["lp_manager_name"].apply(lambda x: row_matches_text(x, words)) |
        matches["lp_fund_name"].apply(lambda x: row_matches_text(x, words)) |
        matches["institutional_fund_name"].apply(lambda x: row_matches_text(x, words))
    ].head(30)

    time_hits = timeseries[
        timeseries["fund_name"].apply(lambda x: row_matches_text(x, words))
    ].head(50)

    if manager_hits.empty:
        manager_hits = managers.sort_values("manager_quality_score", ascending=False).head(10)

    if fund_hits.empty:
        fund_hits = funds.sort_values("trend_score", ascending=False).head(10)

    return manager_hits, fund_hits, match_hits, time_hits

def ask_gpt_allocator(question, chat_history=None):
    managers, funds, matches, timeseries = load_copilot_data()

    manager_hits, fund_hits, match_hits, time_hits = search_relevant_data(
        question,
        managers,
        funds,
        matches,
        timeseries
    )

    prior_context = ""

    if chat_history:
        for msg in chat_history[-6:]:
            prior_context += f"{msg['role'].upper()}: {msg['content']}\n"

    context = f"""
CURRENT USER QUESTION:
{question}

RECENT CHAT CONTEXT:
{prior_context}

RELEVANT MANAGER DATA:
{manager_hits.to_string(index=False)}

RELEVANT FUND SUMMARY DATA:
{fund_hits.to_string(index=False)}

RELEVANT LP DATA / INSTITUTIONAL MATCHES:
{match_hits.to_string(index=False)}

RELEVANT QUARTERLY TIME-SERIES DATA:
{time_hits.to_string(index=False)}
"""

    prompt = f"""
You are an institutional private markets allocator analyst.

Use ONLY the data provided below. Do not invent facts that are not in the data.
If the data is incomplete, say so clearly.

Answer the user's question in a detailed allocator-style memo.

Include:
1. Direct answer
2. Manager/fund overview
3. Performance evidence
4. Institutional-report evidence
5. Strengths
6. Risks and diligence questions
7. Final allocator view

Use numbers where available. Be specific, practical, and investment-oriented.

DATA:
{context}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a private equity and venture capital allocator analyst."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content