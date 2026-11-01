# Matriz de testes

Atualizado: 2026-11-01 UTC. Dump `CUSA11875`. **Nenhum frame foi renderizado.**
Evidências em `docs/evidence/`.

## Ambiente medido

Windows 11 Home Single Language 10.0.26300; Intel Core i7-14650HX; 33.937.809.408 bytes de
RAM (31,61 GiB). NVIDIA GeForce RTX 5060 Laptop GPU (Vulkan driverInfo 621.01, API 1.4.357,
refresh 165 Hz); Intel RaptorLake-S (driverInfo 101.7088, API 1.4.323).
MSYS2 CLANG64 clang 22.1.7, Vulkan 1.4.350, SDL3 3.4.10, libavcodec 62.28.101, Python 3.14.

## Build e testes do projeto

| Verificação | Comando | Resultado | Evidência |
|---|---|---|---|
| Build nativo | `bash build.sh` | PASS, exit 0 | `prompt04/build.txt` |
| Testes nativos | `bash build.sh --test` | PASS, exit 0 | `prompt04/build-test.txt` |
| Suíte Python | `python -m unittest discover -s tests` | PASS, **53 testes**, exit 0 | `prompt04/python-tests.txt` |
| Smoke sem dump | `--help`, `--check-config`, `--audit-runtime`, `--vulkan-smoke` | PASS, exit 0 | `bootstrap/` |
| Falta de jogo | `python run.py` | PASS (exit 1), mensagem acionável | `bootstrap/missing-game.txt` |
| Rejeição da build | `python run.py --game-dir <dump>` | PASS (exit 1), fail-closed | `bootstrap/dump-unvalidated.txt` |
| Suíte herdada | `runtime/tests` | **FAIL**, exit 1 (GoW/MediEvil) | `bootstrap/upstream-tests.txt` |

## Pipeline de boot — estágios realmente atingidos

| Etapa | Exit | Observado | Evidência |
|---|---|---|---|
| SELF → ELF (`prepare`) | 0 | 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos | `prompt03/manifest.json` |
| Link de módulos | 0 | 209 native bindings; libc@0x62a0000, Fios2@0x63b0000 | `prompt04/boot-12-*.txt` |
| Cobertura de imports | 1 | 811/988 resolvidos com shim GPU (679 sem) | `prompt03/imports-gpu.txt` |
| Vulkan/window | — | RTX 5060, Vulkan 1.4.357, swapchain Fifo, 327 HLE symbols | `prompt04/boot-12-*.txt` |
| Imagem mapeada | — | 106.136.876 bytes, 9 segmentos, **465.785 relocations aplicadas** | idem |
| Pools de memória guest | — | 6 MiB + 128 MiB + 5.161.025.536 bytes | idem |
| **Reserva do pool 8 GiB** | — | **concedida** (3 reservas: 8 GiB ×2 + 1 GiB) | `prompt04/boot-16-*.txt` |
| Threads guest / IO | — | **22 threads**, `TaskGraphThreadNP 0..N`; 174 leituras (10.107.208 bytes) | idem |
| AppContent | — | inicializado, perfil offline base-game | idem |
| Boot | **20** | `STOP`: import `NpToolkit2 InitParams` não implementado | idem |

Reprodutibilidade: **2 execuções independentes** com a correção, mesmo resultado (exit 20, mesmo
import). O bloqueio anterior era determinístico em 3 execuções.

## Bugs observados

### P0 — bloqueia o boot (nenhum frame)

**P0-1: reserva do pool de 8 GiB recusada — RESOLVIDO**

- Sintoma: `pool_reserve(0x1000000000, 8 GiB, flags=0x90) -> 0x8002000c`.
- Causa medida: `reserve_range` recusava porque um mapeamento `KIND_DIRECT` de 6 MiB
  escolhido pelo runtime já ocupava `0x1000000000`.
- Correção: `find_free_unhinted()` — colocação sem hint começa em `USER_MIN + 8 GiB`.
- Verificação: 3 reservas concedidas, mapeamento movido para `0x1200000000`, 2 execuções.

**P0-2: `--content-profile` ausente no pipeline — RESOLVIDO**

- Sintoma: `STOP: AppContent needs --content-profile`.
- Correção: gerar `content.bin` com `content_profile.prepare` e passar `--content-profile`.
- Verificação: `AppContent initialized; offline base-game profile`, referências=1.

**P0-3: construtor `NpToolkit2::Request::InitParams` — RESOLVIDO**

- Sintoma: `STOP: ... vbh-MWtjMh4#libSceNpToolkit2 (index 659)`, exit 20.
- Tamanho medido no frame do guest: `rbp-0x398` até `rbp-0x260` = **312 bytes**, 560 bytes
  abaixo do canário. `runtime/src/runtime_np.c` implementa só construtores.
- Verificação: o `STOP` do construtor desapareceu; boot avançou para `Core::init`.

**P0-4: `NpToolkit2::Core::init` recusado com código real — RESOLVIDO**

- Sintoma: `STOP: ... LLdnqVnnNBQ#libSceNpToolkit2 (index 657)`, exit 20.
- Resposta: `0x80550003` (NpToolkit2 "não inicializado"), não 0. O guest trata como falha e
  segue; devolver 0 faria as 79 funções acreditarem num subsistema inexistente.
- Verificação: `NpToolkit2: Core::init refused`; boot avançou por 3 imports.

**P0-5: bloco NpToolkit2 — RESOLVIDO**

- `InitParams` ctor/dtor (352 bytes medidos) e `TermParams` ctor/dtor (8 bytes, limitados pelo
  canário em `rbp-0x28`), mais `Core::init`/`Core::term` recusando com `0x80550003`.
- Verificação: 27 threads, 1.657 leituras (12,1 MB); boot saiu do bloco PSN.

**P0-6: `libSceMove` (PS Move) — ABERTO**

- Sintoma: `STOP: ... j1ITE-EoJmE#libSceMove (index 855)`.
- O Prompt 04 mantém PS Move/PSVR/câmera fora do primeiro gate jogável, mas exige registrar os
  imports. Falta decidir se a recusa explícita basta para o jogo seguir.
- Detalhe: `docs/MEMORY_AUDIT.md`.

### P1 — não alcançados

Nenhum bug P1 registrado: a execução não chega a estágios onde haveria comportamento visual,
de áudio ou de input para avaliar.

### P2 — não alcançados

Idem.

## Hipóteses testadas e refutadas

| Hipótese | Teste | Resultado |
|---|---|---|
| Canário de pilha corrompido | comparação no frame do chamador | **Refutada** — valor idêntico ao guard |
| Pool de memória esgotado | `GOW3_DMEM_MB=8192` | **Refutada** — mesmo bloqueio, zero falhas de alocação |
| `MAP_NO_OVERWRITE` sobre reserva | log em `place()` | **Refutada** — a decisão ocorre antes, em `reserve_range` |
| Mapeamento indireto (sem `MAP_FIXED`) | log em `place()` | **Refutada** — mesma razão |
| Conflito `MAP_FIXED` × memória direta | log em `reserve_range` | **Confirmada** |
| "O runtime escolheu `0x1000000000`" | log `guest hint` + disassembly do call site | **Meia-verdade**: o mapeamento de 6 MiB foi escolha do runtime, mas o pool é exigência do guest (`movabsq`) |

## Não executado — não inferir aprovação

| Item | Estado |
|---|---|
| **Primeiro frame renderizado** | **NÃO EXECUTADO** |
| Intro, menu principal, primeira cena | NÃO EXECUTADO |
| Movimentação, pintura, pausa | NÃO EXECUTADO |
| Áudio (reprodução, pausas, dispositivos) | **NÃO AUDITADO** — sem cena |
| Save/load | NÃO EXECUTADO — formato ainda desconhecido |
| Controles SDL3 gamepad / teclado+mouse | **NÃO VALIDADO** — sem gameplay |
| Mouse → eixo direito (fallback de pintura) | NÃO IMPLEMENTADO nem validado |
| Câmera, gyro, PS Move, PSVR | NÃO EXECUTADO — apenas imports presentes |
| Shader cache, frame pacing, p50/p95/p99 | **NÃO MEDIDO** — sem frames |
| Flicker, iluminação, VRAM, readback | NÃO AUDITADO |
| Outras GPUs | NÃO EXECUTADO |
| Pacote Windows em máquina limpa | NÃO EXECUTADO |

## Como repetir

```bash
bash build.sh && bash build.sh --test
python -m unittest discover -s tests -v

# até o bloqueio atual (esperado: exit 3)
runtime/out/gpu/cg-runtime.exe .cg/audit/prepared/boot-linked.bin \
  --app0 "$PWD/gamedump/CUSA11875" --user .cg/audit/run/user --timeout 40
```

O `boot-linked.bin` é produzido por `prepare` + `link` sobre o dump, documentado em
`docs/MEMORY_AUDIT.md`.

## Classificação da suíte herdada vermelha

`runtime/tests` mantém falhas escritas para GoW III/MediEvil (FPS 120 vs 60, versão 2.1.3 vs
1.3.8, XML GoW ausente, perfil GoW inexistente, symlinks sem privilégio, driver Linux).
Não foram corrigidas: reescrever as expectativas transformaria regressões herdadas em falso
positivo.
