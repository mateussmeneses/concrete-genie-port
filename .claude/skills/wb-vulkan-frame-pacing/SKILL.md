---
name: wb-vulkan-frame-pacing
description: Investigar frame pacing e gargalos Vulkan
version: 1.0.0
---
# wb-vulkan-frame-pacing

**Papel sugerido:** `graphics-performance`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Stuttering, FPS irregular, spikes GPU/CPU, VRAM elevada ou sincronização Vulkan.
 ## Procedimento
 1. Identifique build, driver, GPU, cena, resolução, renderer, captura e versão de referência.
 2. Meça frametime p50/p95/p99, 1% lows, uso de VRAM/RAM, CPU/GPU, loading e tempo de compilação de shaders.
 3. Separe GPU-bound, CPU-bound, IO-bound, shader compilation, PSO/cache e sincronização; formule testes A/B.
 4. Evite otimização por intuição; compare uma variável por vez e registre instrumentos e configurações.
 ## Saída
 Hipóteses, coleta reproduzível, experimento e decisão de manter/reverter alteração.
