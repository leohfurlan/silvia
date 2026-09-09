"""Human intervention adapter for recoverable workflow failures."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import TextIO

from .session import InterventionRequest


def suggested_action(error: str) -> str:
    normalized = error.lower()
    if "outside this agent's ownership" in normalized:
        return "Corrija o ownership ou a ferramenta de listagem e autorize uma nova tentativa."
    if "source-of-truth conflict" in normalized:
        return "Reconcilie contract.md, spec.md e plan.md antes de autorizar a retomada."
    if "403" in normalized or "permission" in normalized or "deposit required" in normalized:
        return "Troque o modelo/credencial disponível e autorize uma nova tentativa."
    if "file does not exist" in normalized:
        return "Crie ou corrija o caminho esperado e autorize uma nova tentativa."
    return "Corrija a causa indicada e autorize uma nova tentativa."


class ConsoleInterventionHandler:
    """Ask for an explicit retry authorization without exposing hidden reasoning."""

    def __init__(self, output: TextIO | None = None, input_stream: TextIO | None = None):
        self.output = output or sys.stderr
        self.input_stream = input_stream or sys.stdin

    async def __call__(self, request: InterventionRequest) -> str:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.output.write(
            f"\n[{stamp}] [INTERVENCAO NECESSARIA] "
            f"sessao={request.session_id} task={request.task_id or '-'}\n"
        )
        self.output.write(f"Erro: {request.error}\n")
        self.output.write(f"Acao sugerida: {request.suggested_action}\n")
        self.output.write("Digite [r]etry para autorizar nova tentativa ou [a]bort para encerrar: ")
        self.output.flush()
        if not self.input_stream.isatty():
            self.output.write("\nSessao pausada: entrada interativa indisponivel.\n")
            self.output.flush()
            return "pause"
        while True:
            choice = (await asyncio.to_thread(self.input_stream.readline)).strip().lower()
            if choice in {"r", "retry", "retentar"}:
                return "retry"
            if choice in {"a", "abort", "abortar", "x"}:
                return "abort"
            self.output.write("Opcao invalida. Use retry ou abort: ")
            self.output.flush()
