# Plano — Fxx

**Revisão:** r1
**Estado:** proposed

## Pré-condições

| Condição | Se ausente |
| --- | --- |
| Requisito e contrato alinhados | Permanecer em descoberta |
| Checkout e runtime isolado | Bloquear execução |
| Gates e baseline identificados | Registrar lacuna |

## Sequência

| # | Resultado | Depende de | Checkpoint |
| --- | --- | --- | --- |
| 1 | Preflight | Pré-condições | Base e recursos |
| 2 | Teste red | 1 | Falha pelo motivo certo |
| 3 | Menor implementação | 2 | Gates rápidos |
| 4 | Revisão e integração | 3 | Achados resolvidos |
| 5 | Revalidação | 4 | Evidência recuperável |

Listar ações que exigem autorização separada.
