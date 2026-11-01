---
name: wb-debug-rigorous
description: Depurar falhas com reprodução e evidências
version: 1.0.0
---
# wb-debug-rigorous

**Papel sugerido:** `root-cause-debugger`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Bug, falha intermitente, crash, exceção, regressão ou resultado inesperado.
 ## Procedimento
 1. Colete síntoma, versão/build, ambiente, passos, esperado/obtido, logs e commit conhecido estável.
 2. Crie hipótese falsificável e repro mínimo; estabeleça medição antes da correção.
 3. Isole uma variável por experimento. Compare regressões com `git diff` e `git bisect` quando viável.
 4. Corrija a causa demonstrada e adicione teste de regressão; execute testes relevantes e registre comando + saída.
 ## Critérios de saída
 Entregue causa confirmada ou hipóteses classificadas, evidências, mudança e validação realizada/não realizada.
