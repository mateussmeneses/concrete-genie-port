---
name: wb-gameplay-acceptance
description: Homologar port por cenas e regressões
version: 1.0.0
---
# wb-gameplay-acceptance

**Papel sugerido:** `release-auditor`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Testes após PR, mudanças em input, launcher, renderer, áudio ou recursos gráficos.
 ## Procedimento
 1. Prepare matriz de cenas, hardware/driver, input mouse-teclado/controle, cold/warm launch.
 2. Verifique menu, resolução, DLSS/FSR quando implementados, save/load, sombras, partículas, áudio e crashes.
 3. Capture vídeo/log, baseline, versão, FPS/frametime e evidência de efeito colateral.
 4. Separe defeito anterior do novo, anote bloqueadores e status de aceite por build.
 ## Saída
 Checklist de regressão, resultados conhecidos e riscos para release.
