import os, asyncio
import anthropic

_client = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.AsyncAnthropic(api_key=key)
    return _client


async def _run_code_async(code: str) -> str:
    """
    Run the interviewer's probe script in the sandbox, off the event loop.

    The interviewer writes this code itself, but it is built from the
    candidate's submission and gets no more trust than any other submission.
    """
    from runner import run_python
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_python, code)
    if result["stderr"]:
        return f"Error: {result['stderr'][:400]}"
    return result["stdout"].strip() or "OK"


async def _run_agent(
    model: str,
    max_tokens: int,
    system: str,
    messages: list,
    tools: list,
    tool_handler,
    max_iterations: int = 10,
) -> str:
    """Agent loop: send messages, execute tool_use blocks, repeat until text response."""
    client = _get_client()
    for _ in range(max_iterations):
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        tool_blocks = [b for b in resp.content if b.type == "tool_use"]
        text_blocks = [b for b in resp.content if b.type == "text"]

        if not tool_blocks:
            return text_blocks[0].text.strip() if text_blocks else ""

        messages = messages + [{"role": "assistant", "content": resp.content}]

        results = []
        for block in tool_blocks:
            output = await tool_handler(block.name, block.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(output),
            })

        messages = messages + [{"role": "user", "content": results}]

    raise RuntimeError("Agent exceeded max iterations without finishing")


# ── Interview Simulator Agent ──────────────────────────────────────────────────

_INTERVIEW_TOOLS = [
    {
        "name": "run_code",
        "description": (
            "Execute a Python test script to observe the candidate's solution behavior. "
            "Write a complete script: define the function (copy it from the solution above), "
            "then print what you want to observe. Use this to probe edge cases or verify claims."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "test_code": {
                    "type": "string",
                    "description": "Complete runnable Python script with function definition and print statements",
                }
            },
            "required": ["test_code"],
        },
    },
    {
        "name": "analyze_approach",
        "description": "Detect the algorithmic approach used in the candidate's code (Hash Map, Two Pointer, Sorting, Brute Force, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"}
            },
            "required": ["code"],
        },
    },
]

_INTERVIEW_SYSTEM = """\
You are a senior software engineer at a top tech company conducting a technical phone screen.

The candidate just solved this problem:
Title: {title}
Description: {description}

Their solution:
```python
{code}
```

You have tools available:
- run_code: Execute test scripts to observe exactly how the solution behaves
- analyze_approach: Detect the algorithmic approach used

Conduct the interview:
- On your first turn, use run_code or analyze_approach to ground your questions in what you actually observe
- Ask exactly ONE focused question per response, 2-3 sentences max
- Probe: time/space complexity, edge cases, alternative approaches, scalability, trade-offs
- Push back on vague answers with a specific follow-up
- Never give away answers — guide the candidate to the insight themselves
- After 6-8 exchanges, wrap up with a 2-sentence performance assessment
- Be direct and professional"""


async def _interview_tool_handler(tool_name: str, tool_input: dict) -> str:
    if tool_name == "run_code":
        return await _run_code_async(tool_input["test_code"])

    if tool_name == "analyze_approach":
        from ml import label_approach
        return label_approach(tool_input["code"])

    return f"Unknown tool: {tool_name}"


async def interview_turn(
    problem_title: str,
    problem_desc: str,
    code: str,
    complexity: str,
    approach: str,
    history: list[dict],
    user_message: str,
) -> dict:
    system = _INTERVIEW_SYSTEM.format(
        title=problem_title,
        description=problem_desc,
        code=code[:2000],
    )
    messages = list(history) + [{"role": "user", "content": user_message}]

    ai_text = await _run_agent(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=system,
        messages=messages,
        tools=_INTERVIEW_TOOLS,
        tool_handler=_interview_tool_handler,
    )

    done = len(history) >= 12
    return {"response": ai_text, "done": done}
