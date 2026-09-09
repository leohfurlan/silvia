# 02: Criar e consultar uma sessão durável

**What to build:** Permitir que o operador registre um projeto, crie uma sessão
com objetivo e revisão inicial e volte a consultá-la depois de reiniciar o
processo, com estado e evento confirmados atomicamente.

**Blocked by:** 01/Inicializar o pacote e o comando silvia.

**Status:** ready-for-agent

- [ ] Projeto e sessão recebem identidades estáveis e objetivo não vazio.
- [ ] Criação grava sessão, revisão 1 e evento durável na mesma transação.
- [ ] Consulta posterior retorna a mesma revisão e o cursor de evento.
- [ ] Falha entre estado e evento não deixa registro parcial.
- [ ] Adapters in-process e SQLite passam pelos mesmos testes de contrato.

