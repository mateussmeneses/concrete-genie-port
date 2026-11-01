---
name: wb-test-planning
description: Planejar testes a partir de riscos e requisitos
version: 1.0.0
---
# wb-test-planning

**Papel sugerido:** `qa-strategist`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Nova feature, bugfix, mudança de requisito ou plano de homologação.
 ## Procedimento
 1. Extrair regras de negócio observáveis e critérios de aceite; separar lacunas de fatos.
 2. Cobrir positivo, negativo, bordas, permissões, estados, persistência, falhas e concorrência.
 3. Relacionar cada cenário à camada ideal: unitário, contrato/API, integração, UI, exploratório.
 4. Definir dados de teste, pré-condições, pós-condições, prioridade e evidência de execução.
 ## Saída
 Matriz requisito × cenário × prioridade × automação × resultado, sem inventar evidências.
