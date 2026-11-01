---
name: wb-reverse-engineering
description: Documentar engenharia reversa sem offsets inventados
version: 1.0.0
---
# wb-reverse-engineering

**Papel sugerido:** `reverse-engineer`. Este arquivo é portátil e não depende desse agente existir.

## Acionamento
 Investigar formatos, símbolos, instruções, assets, executáveis e traduções de APIs em port.
 ## Procedimento
 1. Registre origem e hash do binário, build tag, plataforma, versão e ferramentas usadas.
 2. Diferencie endereços absolutos, RVA e file offsets; anexe prova do dump/desassemblagem.
 3. Trace fluxo de controle, entradas/saídas, dependências e condições de erro; vincule descobertas ao build.
 4. Mantenha hipótese e fato separados; documente testes que refutariam a interpretação.
 ## Saída
 Registro de evidências com paths, hashes, offsets verificados e testes mínimos.
