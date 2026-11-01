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
| Suíte Python | `python -m unittest discover -s tests` | PASS, **73 testes**, exit 0 | `prompt04/python-tests.txt` |
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

**P0-6: subsistemas de sensor — RESOLVIDO**

- PS Move (7), PSVR (22), áudio 3D (14), câmera (7), VR tracker/social screen/VR (24): todos
  registrados com semântica "biblioteca carregada, dispositivo ausente".
- Verificação: boot atravessou todos e saiu da camada de imports.

**P0-7: fault em `RHIThread` na inicialização de RHI — ABERTO**

- Sintoma: `Fault: execute access to 0000000000000000`, `thread name: RHIThread`,
  `#0 guest offset 0x14d6aec` (após `callq *0x8(%rsi)` com `rsi` nulo em `0x14d6ae9`).
- Determinístico em duas execuções. Reprodução: `docs/evidence/prompt04/boot-27-vr-tracker.txt`
  e `boot-28-rhi-determinism.txt`.
- Contexto: antes de falhar, GPU Vulkan 1.4.357 (RTX 5060), 1920x1080, DualSense conectado,
  12 sondagens `CollectImageFormatInfo`.
- **Causa raiz encontrada:** o jogo resolve 8 funções do plugin Bink via `sceKernelDlsym` para
  slots em `.bss` (zero escritores estáticos) e as chama sem verificar nulo. O módulo
  `prx/binkpluginps4.prx` **existe no dump**, mas `sceKernelLoadStartModule` o recusa.
- Correção parcial: `sceKernelDlsym` tinha assinatura errada (`not_found(void)`) e não escrevia o
  parâmetro de saída. Agora zera `*out` e tenta resolver. O crash persiste, com null definido.
- Hipótese descartada: `sceVrTrackerQueryMemory` devolvendo 0 — mudar para erro produziu o mesmo
  crash (`exp-01-vrtracker-refused.txt`).
- **Progresso:** `prx/binkpluginps4.prx` é SELF decriptável e foi **ligado** pelo linker
  (`@0x6540000`); seu `module_start` executou (log: `Starting linked module 2`). Imports faltando
  caíram de 105 para 100.
- **Bloqueio atual:** `sceKernelDlsym` recebe nomes (`BinkPluginGoto`), mas os 32 exports do
  módulo são NIDs. O algoritmo nome→NID não foi reproduzido (4 variantes testadas, 0/4).
- **RESOLVIDO.** Os 23 nomes resolvem (`resolved: 23 / 23`). Dois defeitos: `sceKernelDlsym`
  estava ligado a `not_found(void)` (parâmetro de saída nunca escrito) e `runtime_lookup()`
  resolve NID antes de comparar, então nome puro nunca casava.
- O `RHIThread` **não falha mais**. Boot roda até o timeout (exit 124), sem fault.

**P0-8: buffer de SRT esgotado (shaders) — RESOLVIDO**

- Sintoma: 208 de 208 submissões falhavam com `capture failed: code is too big`.
- Causa medida: um único bloco de 32 MB recebe ~1 MB por shader e esgota no ~32º shader
  (`Srt: 1049098 of 33554432 bytes used (3.1%)` por shader).
- Correção: cadeia de blocos (`SrtBlockWithRoom`) em vez de `AutoGrow`, porque crescer moveria a
  memória e invalidaria ponteiros já entregues a shaders compilados. O handler de sinal passou a
  testar todos os blocos.
- Verificação: **0** erros `code is too big` (antes 208), 4 blocos abertos, nenhum fault.
  Evidência: `docs/evidence/prompt04/boot-45-srt-blocks.txt`.

**P0-9: cadeia de apresentação — VERIFICADA**

- Guest: 1700 `submit-and-flip` por execução, alternando `buf=0/1`.
- `PatchFlipRequest`: 0 falhas (o patch da flip nunca falha).
- `Presenter::PrepareFrame`: alcançado, 1920x1080, endereços reais do guest.
- `vkQueuePresentKHR`: `Success`, 1500+ apresentações.
- Evidência: `docs/evidence/prompt04/boot-59-present.txt`.

**P0-10: captura de frame — FUNCIONA; há conteúdo, e ele anima**

- Três tentativas anteriores produziram zero arquivos por causa do **ambiente**, não do
  renderizador: neste shell MSYS o prefixo inline `VAR=valor ./prog` não propaga; `env VAR=valor
  ./prog` propaga. Medido com `Dump: config at=0 ... dump_at=0`.
- Correções necessárias: `presented_frames` separado (usar `frame_dump_index` era circular),
  `GOW3_DUMP_SYNC=1` (a escrita diferida não roda quando o processo é morto por `timeout`) e o
  bloco de dump no ramo `upscaled`, que não tinha nenhum.
- Resultado: `1920x1080`, 1,96% de pixels não-pretos, caixa `(512, 432, 1412, 584)`, cores
  `#75622e` e `#024d76`; **5,65% dos pixels diferem** entre os frames 300 e 1200 — é renderização
  viva, não artefato estático.
- Ferramenta: `scripts/frame_stats.py <frame.raw> [--diff <outro>]`.
- Evidência: `docs/evidence/prompt04/boot-65-capture.txt`, `boot-67-frame1200.txt`.

**P0-11: primeira cena jogável — ABERTO**

- O conteúdo é uma faixa central de glifos em ~2% da tela, compatível com tela de título/logo.
- Não há movimento de câmera, personagem, pintura, menu navegável nem áudio verificado.
- O critério do Prompt 04 continua **não cumprido**.

**P0-12: paks — CONCLUSÃO ANTERIOR ERRADA, CORRIGIDA**

- Eu afirmei que o runtime "nunca abre os paks" com base num log **sem file tracing**. Estava
  errado, e isso foi commitado em `07e569d`.
- Com `GOW3_FILE_TRACE=1`: o diretório de paks é **enumerado** e os dois paks são **abertos**, com
  `-pak` na linha de comando do motor. Nenhum erro de versão ou corrupção.
- Evidência: `docs/evidence/prompt04/boot-68-file-trace.txt`.

**P0-13: `usrdt53l.dat` — não é bug do runtime**

- 49 pedidos de `/app0/engine/content/internationalization/usrdt53l.dat` falham.
- Medido no índice do pak: `icudt53l` está **presente**, `usrdt53l` e `internationalization`
  estão **ausentes**; nenhum deles consta no `Manifest_NonUFSFiles_PS4.txt`.
- Conclusão: o arquivo não existe no dump. Não é algo que o runtime possa servir.

**P0-14: MENU PRINCIPAL alcançado — medido**

- Draws por frame: 4 (frame 60) → 3,6 (300) → 3,3 (900) → **~950.000** (1800); 2.169.079 draws
  entre 1500 e 1800.
- Frame 1800: **100,00%** de pixels não-pretos, fundo branco, duas faixas de conteúdo em
  y 583..911 e 942..1031, paleta dourada (`#e7b344`, `#de9b0b`, `#b96c13`).
- Estrutura compatível com menu principal (título + lista de entradas).
- Evidência: `docs/evidence/prompt04/boot-70-draws.txt`, `boot-71-scene.txt`.
- **Não é gameplay:** sem input, áudio ou movimentação testados.

**P0-15: `sceSaveDataGetParam` — RESOLVIDO**

- Sintoma: `exit 20`, `STOP: ... XgvSuIdnMlw#libSceSaveData (index 139)`.
- Duas causas: a função não existia, e o NID `XgvSuIdnMlw` não estava em `import_names.inc`
  (sem isso o resolver não liga nada, mesmo com a função presente).
- Correção: `save_get_param` (5 tipos, simétrico ao setter) + entrada na tabela de nomes.
- Verificação: `exit 20` → `exit 124`, frame 1200 → 1800. Evidência:
  `docs/evidence/prompt04/boot-77-past-savedata.txt`.

**P0-19: passes de cor vazias na transição — ABERTO (instrumentado)**

- `GOW3_TRACE_CLEAR=1` loga `BeginRendering` (anexos + clears) e `EndRendering` (draws no passe).
- 43.935 passes de cor fechados: 36.964 (84%) com **0 draws**; o resto entre 1 e dezenas.
- **Mas a geometria chega à tela**: frame 1200 = 3,71%, frame 1500 = 6,50%, frame 1900 = 100%.
  Portanto "nada desenha" está errado — o pipeline funciona.
- No ponto de parada (frame ~1800), passes com 2-3 anexos de cor fecham com **0 draws**.
- Nem todo passe com 0 draws é bug (depth-only, cópias); não registrar como causa.
- Evidência: `boot-83-clears.txt`, `boot-84-clears2.txt`, `boot-85-draws-per-pass.txt`,
  `boot-86-transition.txt`.

**P0-18: tela preta após o menu — ABERTO (input refutado)**

- Sequência: carrega → menu (~frame 1700-1800, 100% de pixels) → **tela preta permanente**.
- **Hipótese de input refutada por controle**: sem nenhum input, frames 2500/3500/5000/8000 são
  todos 0,00% não-pretos (`boot-82`). Com `cross` injetado, o mesmo ocorre (`boot-80`).
- `display_*` **e** `output_*` ficam pretos: a origem está no framebuffer do guest, não na
  apresentação.
- O motor permanece saudável: 60 FPS, 1 draw/frame, GPU 67-97% ociosa, 12.900+ frames,
  `pad read #13801` com valores vivos (`lx=130 ly=127 rx=131 ry=137`).
- Evidência: `boot-80-input-test.txt`, `boot-82-long-nopad.txt`.

**P0-16: espera pós-menu — MEDIDO: não é desempenho**

- **Duas conclusões minhas estavam erradas.** "~950 mil draws/frame" era leitura de contador
  cumulativo; "saturação a 3,7 fps" era a fase de carregamento.
- Com `GOW3_FRAME_STATS=1`: **60,0 FPS estável**, pior frame 18 ms, **1-6 draws/frame**,
  0 compilações de shader após o startup, **GPU idle ~100%**.
- Áudio inicializado: `audio port 0 opened (type 0, 8 ch, float, 256 frames)`.
- 39 threads guest, incluindo `FAsyncLoadingThread` e `FSaveLoadWorker`.
- `CheckPoint1` montado duas vezes; `usrdt53l` não é laço (para na linha 436 de 1671).
- Leitura correta: o motor está num **estado de espera** com apresentação saudável. A investigação
  é de progressão de estado, não de renderização.
- Evidência: `docs/evidence/prompt04/boot-79-frame-stats.txt`.

**P0-17: conteúdo cresce entre frames — investigação anterior**

- Frame 300: 1,96% não-preto, caixa `(512,432,1412,584)`, cores `#75622e`/`#024d76`.
- Frame 1200: **3,71%** não-preto, caixa `(148,224,1772,736)`, cores `#ffffff` e outras.
- Há uma forma preenchida com bordas limpas e gradiente na metade inferior — geometria renderizada.
- Bug de GPU real observado: `SanitizeCopyLayers` clampando layers (ex.: 5→6→mínimo) em todos os
  mips, uma vez por mip. Suspeito, mas o clamp é seguro por si.
- Detalhe: `docs/MEMORY_AUDIT.md`.
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
