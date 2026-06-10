import os

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.runnables import RunnableConfig

from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.backends.context_hub import ContextHubBackend
from pydantic import BaseModel, Field

from agent.tools import TOOLS
from context import CONTEXT_HUB_REPO, get_prompt
from utils.streaming import iter_text

_WRITE_FILE_MISSING_CONTENT_ERROR = (
    "Error: write_file requires a non-empty 'content' argument; nothing was written."
)


class _RelaxedWriteFileSchema(BaseModel):
    """write_file schema with optional content so missing values reach our validator."""

    file_path: str = Field(description="Absolute path where the file should be created. Must be absolute, not relative.")
    content: str = Field(default="", description="The text content to write to the file. This parameter is required.")


class _ValidatingFilesystemMiddleware(FilesystemMiddleware):
    """FilesystemMiddleware that rejects write_file calls missing content."""

    def _create_write_file_tool(self):
        tool = super()._create_write_file_tool()
        original_func = tool.func
        original_coroutine = tool.coroutine

        def _validated_sync(*args, **kwargs):
            if not isinstance(kwargs.get("content"), str) or not kwargs.get("content"):
                return _WRITE_FILE_MISSING_CONTENT_ERROR
            return original_func(*args, **kwargs)

        async def _validated_async(*args, **kwargs):
            if not isinstance(kwargs.get("content"), str) or not kwargs.get("content"):
                return _WRITE_FILE_MISSING_CONTENT_ERROR
            return await original_coroutine(*args, **kwargs)

        tool.func = _validated_sync
        tool.coroutine = _validated_async
        tool.args_schema = _RelaxedWriteFileSchema
        return tool

# AGENTS.md is the agent's system prompt — pulled fresh from LangSmith
# Context Hub at module import. The content lives in Context Hub, not in
# this repo. Edit the prompt in the Context Hub UI.
SYSTEM_PROMPT = get_prompt()

# Override with CHAT_LANGCHAIN_LITE_MODEL env var — used by setup.py to seed
# baseline experiments against a more expensive model (Sonnet) for the
# demo's cost/latency comparison.
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _model_id() -> str:
    return os.getenv("CHAT_LANGCHAIN_LITE_MODEL") or _DEFAULT_MODEL


def build_agent():
    return create_agent(
        model=ChatAnthropic(model=_model_id(), max_tokens=300),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        # FilesystemMiddleware exposes ls/read_file/etc. backed by Context Hub.
        middleware=[_ValidatingFilesystemMiddleware(backend=ContextHubBackend(CONTEXT_HUB_REPO))],
    )


def _config(thread_id: str | None = None) -> RunnableConfig:
    metadata = {"demo": "true", "demo_type": "chat-lc-lite", "model": _model_id()}
    if thread_id:
        metadata["thread_id"] = thread_id
    return RunnableConfig(
        run_name="chat-lc-lite-demo",
        metadata=metadata,
        tags=["engine-demo", CONTEXT_HUB_REPO],
    )


def _user_msg(question: str) -> dict:
    return {"messages": [{"role": "user", "content": question}]}


def invoke_agent(question: str, thread_id: str | None = None) -> dict:
    """Run the agent once. Returns {output, tools_called, messages}."""
    result = build_agent().invoke(_user_msg(question), _config(thread_id))
    output = next(
        (m.content for m in reversed(result["messages"])
         if isinstance(getattr(m, "content", None), str) and m.content),
        "",
    )
    tools_called = [m.name for m in result["messages"] if isinstance(m, ToolMessage)]
    return {"output": output, "tools_called": tools_called, "messages": result["messages"]}


def stream_agent(question: str, thread_id: str | None = None):
    """Stream the agent's response text as it's generated."""
    for chunk, _meta in build_agent().stream(
        _user_msg(question), _config(thread_id), stream_mode="messages"
    ):
        if isinstance(chunk, AIMessageChunk):
            yield from iter_text(chunk)
