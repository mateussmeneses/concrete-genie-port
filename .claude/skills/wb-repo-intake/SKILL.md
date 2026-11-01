---
name: wb-repo-intake
description: Inspecionar repositório antes de qualquer alteração
version: 1.0.0
---
# wb-repo-intake

**Papel sugerido:** `triage-orchestrator`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Ao entrar num repositório, retomar trabalho interrompido ou receber pedido de análise geral.
 ## Procedimento
 1. Verifique `git status --short`, branch, remotes, linguagem, arquivos de build e instruções do projeto.
 2. Identifique módulos, entradas, dependências, testes, CI e pontos de falha; leia arquivos antes de propor mudanças.
 3. Busque histórico e issues relevantes; registre quais observações vêm do código, logs ou suposições.
 4. Entregue mapa de arquitetura, caminhos críticos, riscos por severidade e backlog pequeno com evidências.
 ## Critérios de saída
 Não afirmar execução de testes, causa-raiz ou compatibilidade sem evidência. Não alterar arquivos nesta etapa sem pedido explícito.
