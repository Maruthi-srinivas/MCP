"""OpenAI chat model. Constructed only when a key is configured."""

import json

from agent_app.config import Settings
from agent_app.policy import SYSTEM_PROMPT


class OpenAIModel:
    """Ask the model for the next tool batch or a final answer."""

    def __init__(self, settings: Settings) -> None:
        from langchain_openai import ChatOpenAI

        self._llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)

    async def decide(self, question: str, repository_id: str, observations: list[dict], tool_names: list[str]) -> dict:
        payload = {
            "question": question,
            "repository_id": repository_id,
            "tools": tool_names,
            "observations": observations,
        }
        message = await self._llm.ainvoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", json.dumps(payload)),
            ]
        )
        return _parse(message.content)


def _parse(content) -> dict:
    text = content if isinstance(content, str) else str(content)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {"answer": text.strip(), "claims": []}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"answer": text.strip(), "claims": []}
    if not isinstance(parsed, dict):
        return {"answer": text.strip(), "claims": []}
    return parsed
