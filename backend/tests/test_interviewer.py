"""
Interviewer tool-use loop.

Uses a stub client, so the loop (tool call, run it, feed back the result,
answer) is tested without an API key or network. The tool itself runs real
code in the sandbox.
"""

import json
import types

import pytest

import interviewer
from interviewer import MAX_TOOL_ROUNDS, RUN_CODE_TOOL, interview_turn, run_code_tool


def _tool_call(cid, code, language="python"):
    return types.SimpleNamespace(
        id=cid,
        function=types.SimpleNamespace(
            name="run_code",
            arguments=json.dumps({"code": code, "language": language}),
        ),
    )


def _msg(content=None, tool_calls=None):
    return types.SimpleNamespace(content=content, tool_calls=tool_calls)


class StubClient:
    """Returns a scripted sequence of completions and records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.seen.append(kwargs)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=self.script.pop(0))])


@pytest.fixture()
def stub(monkeypatch):
    def install(script):
        client = StubClient(script)
        monkeypatch.setattr(interviewer, "get_client", lambda: client)
        return client
    return install


class TestToolDefinition:
    def test_the_tool_is_strict_about_its_arguments(self):
        params = RUN_CODE_TOOL["function"]["parameters"]
        assert params["additionalProperties"] is False
        assert set(params["required"]) == {"code", "language"}
        assert params["properties"]["language"]["enum"] == ["python", "cpp", "java"]


class TestToolBody:
    def test_it_runs_code_and_returns_output(self):
        assert json.loads(run_code_tool("print(6*7)", "python"))["stdout"].strip() == "42"

    def test_a_crash_is_reported_rather_than_raised(self):
        """The model has to be able to see the failure and respond to it."""
        out = json.loads(run_code_tool("raise ValueError('boom')", "python"))
        assert out["exit_code"] != 0
        assert "boom" in out["stderr"]

    def test_a_compile_error_is_flagged_distinctly(self):
        out = json.loads(run_code_tool("int main() { not valid }", "cpp"))
        assert out["compile_error"]


class TestLoop:
    def test_a_plain_answer_returns_without_running_anything(self, stub):
        client = stub([_msg(content="What's your approach?")])
        out = interview_turn([], "I'd use a hash map.")
        assert out["reply"] == "What's your approach?"
        assert out["tool_runs"] == []
        assert len(client.seen) == 1

    def test_a_tool_call_is_executed_and_fed_back(self, stub):
        """The interviewer runs the candidate's code and sees the real output
        before replying."""
        client = stub([
            _msg(tool_calls=[_tool_call("call_1", "print(6*7)")]),
            _msg(content="That prints 42, so it works."),
        ])
        out = interview_turn([], "Does this work?")

        assert out["reply"] == "That prints 42, so it works."
        assert len(out["tool_runs"]) == 1
        assert out["tool_runs"][0]["result"]["stdout"].strip() == "42"

        # The tool result has to reach the model, not just the caller.
        second_request = client.seen[1]["messages"]
        tool_msg = [m for m in second_request if m.get("role") == "tool"]
        assert tool_msg and "42" in tool_msg[0]["content"]
        assert tool_msg[0]["tool_call_id"] == "call_1"

    def test_history_grows_by_the_exchange_only(self, stub):
        """Tool calls stay out of the returned history. The client only needs
        the conversation."""
        stub([_msg(tool_calls=[_tool_call("c", "print(1)")]),
              _msg(content="ok")])
        out = interview_turn([], "check this")
        assert out["history"] == [
            {"role": "user", "content": "check this"},
            {"role": "assistant", "content": "ok"},
        ]

    def test_a_model_that_never_stops_calling_tools_is_cut_off(self, stub):
        """Otherwise a model stuck in a loop keeps costing money."""
        stub([_msg(tool_calls=[_tool_call(f"c{i}", "print(1)")])
              for i in range(MAX_TOOL_ROUNDS + 2)])
        out = interview_turn([], "go")
        assert out["error"] == "tool round limit reached"
        assert len(out["tool_runs"]) == MAX_TOOL_ROUNDS
