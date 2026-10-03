"""Load a named MCP prompt. The prompt text becomes the question, not the answer."""


async def load_prompt(hub, name: str, arguments: dict | None) -> str | None:
    """Return the prompt text, or None when no server lists that name."""
    prompts = await hub.list_prompts()
    if not any(item.get("name") == name for item in prompts):
        return None
    return await hub.get_prompt(name, arguments or {})
