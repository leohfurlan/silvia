"""LangChain workflow runtime for the B.AI-backed agent harness."""

from .config import WorkflowConfig
from .harness import HarnessConflict, HarnessInitializationReport, initialize_standard_harness

__all__ = [
    "HarnessConflict",
    "HarnessInitializationReport",
    "WorkflowConfig",
    "WorkflowRunner",
    "initialize_standard_harness",
]


def __getattr__(name: str):
    if name == "WorkflowRunner":
        from .engine import WorkflowRunner

        return WorkflowRunner
    raise AttributeError(name)
