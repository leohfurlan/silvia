"""LangChain agent construction for the four workflow roles."""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from .config import WorkflowConfig
from .observability import NullObserver, Observer, WorkflowEvent, _safe_tool_output
from .tools import workspace_tools


def _model(config: WorkflowConfig, model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        base_url=config.base_url,
        api_key=config.api_key,
        temperature=0,
        timeout=900,
        max_retries=2,
    )


def _content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def _text(result: Any) -> str:
    if isinstance(result, dict) and "output" in result:
        return _content(result["output"]) or str(result["output"])
    if isinstance(result, dict) and "messages" in result and result["messages"]:
        return _content(result["messages"][-1].content)
    if hasattr(result, "content"):
        return _content(result.content)
    return str(result) if isinstance(result, str) else ""


async def _stream_agent(agent: Any, payload: dict[str, Any], observer: Observer, role: str, model: str, task_id: str) -> str:
    final_text = ""
    async for event in agent.astream_events(payload, version="v2"):
        event_name = event.get("event", "")
        data = event.get("data", {})
        if event_name == "on_chat_model_stream":
            chunk = data.get("chunk")
            token = _content(getattr(chunk, "content", ""))
            if token:
                await observer.emit(WorkflowEvent("token", role, model, task_id, token))
        elif event_name == "on_tool_start":
            await observer.emit(WorkflowEvent("tool_started", role, model, task_id, str(event.get("name", "tool"))))
        elif event_name == "on_tool_end":
            tool_name = str(event.get("name", "tool"))
            output = data.get("output", "")
            await observer.emit(WorkflowEvent("tool_finished", role, model, task_id, tool_name, payload={"return": _safe_tool_output(output)}))
        elif event_name in {"on_chat_model_end", "on_chain_end"}:
            candidate = _text(data.get("output"))
            if candidate:
                final_text = candidate
    return final_text


async def invoke_agent(
    config: WorkflowConfig,
    *,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[Any],
    observer: Observer | None = None,
    role: str = "agent",
    task_id: str = "",
) -> str:
    observer = observer or NullObserver()
    await observer.emit(WorkflowEvent("agent_started", role, model_name, task_id, "iniciado"))
    model = _model(config, model_name)
    try:
        try:
            from langchain.agents import create_agent

            agent = create_agent(model=model, tools=tools, system_prompt=system_prompt)
            result = await _stream_agent(agent, {"messages": [("user", user_prompt)]}, observer, role, model_name, task_id)
        except ImportError:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

            prompt = ChatPromptTemplate.from_messages(
                [("system", system_prompt), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")]
            )
            agent = create_tool_calling_agent(model, tools, prompt)
            executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
            result = await _stream_agent(executor, {"input": user_prompt}, observer, role, model_name, task_id)
        await observer.emit(WorkflowEvent("agent_finished", role, model_name, task_id))
        return result
    except Exception as exc:
        await observer.emit(WorkflowEvent("agent_failed", role, model_name, task_id, str(exc)))
        raise


def orchestrator_prompt() -> str:
    return """You are the workflow orchestrator. Plan only; do not edit files.
Return JSON with exactly: summary, acceptance_criteria, work_items.
Each work item has id, purpose, owned_paths, dependencies, verification, model.
Every implementation item must use qwen3.8-flash, glm-5.3-flash, or deepseek-v4-flash. Add context_class to every item: use standard for ordinary work and large only for work that requires unusually broad repository/document context. Large items must use deepseek-v4-flash because it consumes paid Credits; standard items must use Qwen or GLM. Prefer Qwen or GLM unless large context is genuinely required. Split independent work into
disjoint owned_paths so the controller can run items in parallel. Respect the
SDD sequence: approved requirements/spec/contract/plan, implementation,
verification evidence, review, and separately authorised PR. If required
source-of-truth artifacts are missing, mark that in acceptance_criteria and
create no speculative implementation work."""


def coder_prompt() -> str:
    return """You are the implementation agent. Work only inside the assigned
owned_paths. Read the relevant existing files, implement the bounded work item,
and use your write_file tool for edits. Preserve unrelated changes. Do not
commit, push, open a PR, alter migrations/deployments, or edit outside scope.
Finish with a short summary; correctness is judged by the later reviewer."""


def reviewer_prompt() -> str:
    return """You are an independent code reviewer. You are read-only. Inspect
the requested changes and their evidence against the task, acceptance criteria,
contract, and repository conventions. Return JSON exactly with status (pass,
changes_requested, or blocked), findings, and required_changes. A pass requires
no unresolved correctness, security, scope, or verification issue."""


def pr_prompt() -> str:
    return """You are the PR agent. Prepare a concise, evidence-based PR draft
only after every review passes and checks have passed. Return JSON with title,
body, and labels. Mention the SDD artifacts, implementation, review findings,
and verification evidence. Never claim a test ran if it did not. The controller
will decide whether an explicitly authorised PR may be opened."""


def tools_for(config: WorkflowConfig, owned_paths: tuple[str, ...], *, writable: bool):
    return workspace_tools(config.repo, owned_paths, writable=writable)
