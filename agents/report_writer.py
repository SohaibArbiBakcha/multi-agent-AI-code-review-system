"""Agent 5 — ReportWriterAgent.

Aggregates the outputs of agents 1-4 and asks Mistral to write a
pedagogical Markdown report.
"""
from loguru import logger

from llm.ollama_client import OllamaUnavailableError, generate_text

SYSTEM_PROMPT = """You are a software engineering instructor writing a
pedagogical report for a student, based on the results of an automated
analysis of their code. Write a Markdown report in English, with the
following sections: "Summary", "Bugs and Security", "Code Quality",
"Complexity", "Generated Tests", and "Advice to Improve". Be concrete,
supportive, and pedagogical. Do not invent any information absent from
the provided data."""


def run(filename: str, agent1, agent2, agent3, agent4, score: dict, language: str = "python") -> dict:
    prompt = (
        f"File analyzed: {filename} (language: {language})\n"
        f"Global score: {score.get('value')}/100 (grade {score.get('grade')})\n\n"
        f"Bugs and security (agent 1): {agent1}\n\n"
        f"Code smells (agent 2): {agent2}\n\n"
        f"Complexity (agent 3): {agent3}\n\n"
        f"Generated tests (agent 4, excerpt): {str(agent4)[:800]}"
    )

    try:
        markdown = generate_text(prompt, SYSTEM_PROMPT)
    except OllamaUnavailableError as exc:
        logger.warning(f"ReportWriter: LLM unavailable, emitting raw summary ({exc})")
        markdown = (
            f"# CodeSentinel Report — {filename}\n\n"
            f"**Global score: {score.get('value')}/100 (grade {score.get('grade')})**\n\n"
            f"## Bugs and Security\n{agent1}\n\n"
            f"## Code Smells\n{agent2}\n\n"
            f"## Complexity\n{agent3}\n\n"
            "_LLM unavailable: report generated without pedagogical formatting._"
        )

    return {"markdown": markdown}
