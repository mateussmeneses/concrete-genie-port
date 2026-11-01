---
name: wb-pr-release
description: Preparar PR e checklist de release sem merge automático
version: 1.0.0
---
# wb-pr-release

**Papel sugerido:** `release-auditor`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Planejar entrega, consolidar PR, release candidate ou regressão de versão.
 ## Procedimento
 1. Verifique `git status`, branch de origem, changelog, matriz de compatibilidade e testes.
 2. Garanta alterações rastreáveis, pequenas e reversíveis; identifique migrações e flags.
 3. Prepare resumo do PR, evidências, limitações, rollback, aceite e testes manuais pendentes.
 4. Não executar merge na branch principal sem autorização explícita.
 ## Saída
 Go/No-Go condicionado às evidências; pendências por severidade.
