# 17: Exportar e verificar sessões portáveis

**What to build:** Exportar uma sessão como pacote verificável e avaliar um
pacote recebido como entrada não confiável antes de qualquer importação.

**Blocked by:** 13/Aplicar retenção, exportação e exclusão de memória; 16/Gerar relatórios determinísticos da sessão.

**Status:** ready-for-agent

- [ ] Pacote contém manifesto, versões, eventos redigidos, artefatos, evidências e digests.
- [ ] Credenciais, segredos e caminhos locais executáveis não são exportados.
- [ ] Verificação detecta digest divergente, schema incompatível e referência ausente.
- [ ] Path traversal, conteúdo executável e evento causal inválido são rejeitados.
- [ ] Verificação não muta o banco nem executa conteúdo do pacote.
- [ ] Sessão válida pode ser reproduzida com integridade observável.

