"""LangChain workflow runtime for the B.AI-backed agent harness."""

from .config import WorkflowConfig

__all__ = ["WorkflowConfig", "WorkflowRunner"]


def __getattr__(name: str):
    if name == "WorkflowRunner":
        from .engine import WorkflowRunner

        return WorkflowRunner
    raise AttributeError(name)
