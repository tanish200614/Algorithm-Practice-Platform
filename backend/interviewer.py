"""
Mock technical interviewer.

The model gets one tool: running the candidate's code in the sandbox. Without
it, the interviewer would just have to trust that the code works.

Standard tool-use loop: send the conversation, run any tool calls, append the
results, repeat until the model replies with text.
"""

import json

from llm import MODEL, get_client
from sandbox import run_sandboxed
from runner import prepare_java_source
from sandbox import cpp_compile_and_run, java_compile_and_run

# Cap the tool loop so a model that keeps calling tools can't run up the bill.
# Three is enough to run code, see it fail, and run a fix.
MAX_TOOL_ROUNDS = 5

SYSTEM = """\
You are conducting a technical interview about algorithms.

You have a tool that runs the candidate's code. Use it before commenting on
whether a solution works — do not assume it does because the candidate says so,
and do not claim it fails without running it.

Ask one question at a time. Probe complexity and edge cases rather than syntax.
Be direct and brief. If the candidate is stuck, give the smallest hint that
unblocks them rather than the answer."""

RUN_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": "Execute the candidate's code in an isolated sandbox and "
                       "return its output. Use this to check whether a solution "
                       "actually works before commenting on it.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code", "language"],
            "properties": {
                "code": {"type": "string",
                         "description": "A complete, runnable program that prints its result."},
                "language": {"type": "string", "enum": ["python", "cpp", "java"]},
            },
        },
    },
}


def run_code_tool(code: str, language: str) -> str:
    """Runs the candidate's code. Untrusted either way: the candidate wrote
    it and the model decided when to run it."""
    if language == "cpp":
        res = run_sandboxed("cpp", {"solution.cpp": code}, cpp_compile_and_run())
    elif language == "java":
        source, class_name = prepare_java_source(code)
        res = run_sandboxed("java", {f"{class_name}.java": source},
                            java_compile_and_run(class_name))
    else:
        res = run_sandboxed("python", {"solution.py": code}, ["solution.py"])

    return json.dumps({
        "stdout": res.stdout[:2000],
        "stderr": res.stderr[:1000],
        "exit_code": res.exit_code,
        "timed_out": res.timed_out,
        "compile_error": res.compile_failed,
    })


def interview_turn(history: list, message: str, model: str = None) -> dict:
    """
    Advance the interview by one candidate message.

    Returns the reply and the updated history. The client holds the
    conversation, so nothing is lost if the server restarts.
    """
    client = get_client()
    messages = [{"role": "system", "content": SYSTEM}] + list(history)
    messages.append({"role": "user", "content": message})

    tool_runs = []
    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=model or MODEL,
            messages=messages,
            tools=[RUN_CODE_TOOL],
        )
        choice = completion.choices[0].message

        if not getattr(choice, "tool_calls", None):
            reply = choice.content or ""
            return {
                "reply": reply,
                "history": history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                ],
                "tool_runs": tool_runs,
            }

        messages.append({
            "role": "assistant",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
                for tc in choice.tool_calls
            ],
        })

        for tc in choice.tool_calls:
            args = json.loads(tc.function.arguments)
            result = run_code_tool(args["code"], args.get("language", "python"))
            tool_runs.append({"language": args.get("language", "python"),
                              "result": json.loads(result)})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # Out of rounds: say so instead of returning the last tool output.
    return {
        "reply": "The interviewer got stuck running code. Try rephrasing.",
        "history": history,
        "tool_runs": tool_runs,
        "error": "tool round limit reached",
    }
