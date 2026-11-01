---
name: wb-shader-cache-triage
description: Diagnosticar cache de shaders e recompilação
version: 1.0.0
---
# wb-shader-cache-triage

**Papel sugerido:** `graphics-performance`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Micro-stutter, flicker, cache inválido, PSO e pré-compilação de shaders.
 ## Procedimento
 1. Identifique pipeline, hashes de shader, driver, cache key, invalidação, artefatos e mapeamento de jogo.
 2. Capture miss/hit, compilação por cena e tempo; diferencie descoberta em runtime de falha de persistência.
 3. Compare cold start vs warm start e versão estável vs atual, com a mesma cena.
 4. Valide reflexos, sombras, partículas, transparência e recursos de fallback após mudanças.
 ## Saída
 Métricas comparáveis, risco visual, recomendação e plano de rollback.
