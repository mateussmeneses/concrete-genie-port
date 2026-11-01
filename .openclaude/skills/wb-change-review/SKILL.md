---
name: wb-change-review
description: Revisar diffs e riscos antes de aprovação
version: 1.0.0
---
# wb-change-review

**Papel sugerido:** `code-reviewer`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Revisar PR, comparar código antigo/novo, auditar refatoração ou verificar regressões.
 ## Procedimento
 1. Identifique base, head, commits e arquivos alterados; examine o diff real e o contexto dos chamadores.
 2. Classifique mudanças: comportamento, API, banco, UI, segurança, desempenho e compatibilidade.
 3. Priorize achados P0 a P3 com caminho/linha, cenário que falha e prova reproduzível.
 4. Sugira testes unitários, integração, E2E e homologação; informe se alguma verificação não pôde ser executada.
 ## Saída
 Resumo de mudanças, melhorias/pioras, riscos, testes indispensáveis e decisão fundamentada.
