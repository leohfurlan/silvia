# Autorizações

| Ação | Regra | Evidência / responsável |
| --- | --- | --- |
| Editar no escopo | Permitido no checkout autorizado | Diff |
| Commit | PENDING | PENDING |
| Push | Autorização explícita | Pedido do usuário |
| PR/issue | Autorização explícita | Destino confirmado |
| Merge | Autorização explícita | Revisão e gates |
| Deploy | Autorização explícita | Preflight e rollback |
| Migration fora de banco descartável | Autorização explícita | Backup e reversão |
| Efeito externo | Autorização específica | Reconciliação |

Uma autorização não concede automaticamente as seguintes.
