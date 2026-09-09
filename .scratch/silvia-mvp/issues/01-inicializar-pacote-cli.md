# 01: Inicializar o pacote e o comando silvia

**What to build:** Disponibilizar uma instalação local que execute o comando
silvia, preserve bai-workflow como alias depreciado e ofereça diagnóstico das
capacidades locais mesmo quando nenhum provider estiver disponível.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Instalação por pipx expõe silvia e mantém bai-workflow funcional.
- [ ] Uso do alias legado mostra aviso de depreciação sem inventar data de remoção.
- [ ] Diagnóstico local distingue configuração válida, provider ausente e credencial não disponível sem revelar segredo.
- [ ] Windows/PowerShell e terminal não interativo possuem saída e exit codes verificáveis.
- [ ] Gates existentes passam sem exigir chamada de modelo.

