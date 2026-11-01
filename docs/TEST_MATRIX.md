# Matriz de testes

Atualizado: 2026-11-01 UTC. Dump `CUSA11875`. **Há frames renderizados e uma cena 3D estável; não
há cena jogável verificada** (sem pintura, áudio ou save/load observados).
Evidências em `docs/evidence/`.

## Mapa de estado por frame — instrumentação e resultado

Registro novo, `GOW3_FRAME_MAP=1`, amostra a grade de luminância 3×3 da imagem final e os draws
desde a amostra anterior. `scripts/frame_states.py` lê o log e imprime as faixas de estado.

| Execução | Entrada | Faixas observadas | Evidência |
|---|---|---|---|
| `boot-135` | `cross` | black 1..586, fade 591..616, **scene 621..9021** | `boot-135-framemap-cross.txt` |
| `boot-137` | `cross` (repetição) | black 1..511, fade 516..556, **scene 561..9006** | `boot-137-framemap-repro.txt` |
| `run5-verify` | `cross`, a cada 10 | black 1..431, fade 441..461, **scene 471..9601** | `.cg/audit/statemap/run5-verify.log` |
| `boot-136` | `cross`+`options` | black 1..411, fade 416..461, **bright 466..9041** | `boot-136-framemap-options.txt` |

**O estado não alterna *dentro* de uma execução**, mas **não é determinístico entre execuções**.
Alcançada a cena, ela permanece até o timeout. Porém, com a mesma entrada `cross`, uma execução
terminou em `bright` (`boot-140`) em vez de `scene`:

| Execução | Entrada | Estado final |
|---|---|---|
| `boot-135` | `cross` | **scene** (621..9021) |
| `boot-137` | `cross` | **scene** (561..9006) |
| `boot-138` | `cross` | **scene** (471..9601) |
| `boot-140` | `cross` | **bright** (496..9661) |
| `boot-139` | `cross`, `options` no frame 461 | **scene** (461..24181) |
| `boot-136` | `cross`+`options` | **bright** (466..9041) |

A tela `bright` é a **mesma** nos dois casos que a alcançaram, e aparece **sem nenhum input**
(`boot-140`). Portanto não se pode atribuir `bright` ao OPTIONS, e nenhum teste pode assumir que
`cross` leva à cena.

**Custo medido da instrumentação:** 3,09 ms por amostra (readback incluído), estável de 60 a 1.800
amostras, com o jogo mantendo 30 FPS. A sonda não altera o estado que mede.

## Testes ancorados por estado (`scripts/state_anchored_run.py`)

Um índice de frame não identifica estado quando o ponto de parada varia. O driver espera `settle`
amostras consecutivas do estado pedido e só então escreve o pad file, registrando a âncora no
próprio log.

`boot-139` — âncora em `scene` no frame 461, `options` aplicado depois, confirmado por
`buttons=0x4000` → `buttons=0x4008`. A cena permaneceu `scene` por 23.700 frames.

**Consequência para os testes anteriores:** o teste de pausa `pz` caiu em `bright`, estado que agora
se sabe alcançável **sem input**. Ele não media gameplay pausado nem consequência de OPTIONS.
**Pausa permanece não observada**, sem evidência de defeito.

**Pintura — veredito inalterado:** negativa por três caminhos (R2 parado, R2+stick, R2+sensor
verificado ativo). Esses cinco runs (grade 78/163/50) estavam na mesma cena 3D e seguem comparáveis.

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
| Suíte Python | `python -m unittest discover -s tests` | PASS, **86 testes**, exit 0 | `prompt04/python-tests.txt` |
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

**P0-21: re-enfileiramento de shader — RESOLVIDO**

- Correção A: `Program::queued_permutations` consultado antes de enfileirar (elimina 269.447 filas
  redundantes).
- Correção B: índice = `modules.size() + queued_permutations.size() - 1`, reservado sob
  `unique_lock` (impede o crescimento a 28.474).
- Liberação: `std::erase(...)` em `PublishShaders`, com cópia da `spec` antes do `move`.
- **Aceitação cumprida:** traduções 1.262.000 → **~5**; FPS 0,7 → **30,0**; `capture` 3256 ms →
  **0,0 ms**; frames 2.100 → **9.900**; capturas pós-menu pretas → **100% de conteúdo**.
- Evidência: `boot-92-fix.txt`.

**P0-36: pausa — OPTIONS não pausa (não observado, não é bug declarado)**

- OPTIONS mantido a partir do frame 3000 (`buttons=0x4008` confirmado no log de leitura do pad).
- Cena continua mudando **~5% por frame** depois disso (3200: 5,26%, 3600: 5,79%, 4400: 5,17%);
  cores constantes (776–781); sem congelamento nem menu.
- **Provado:** o input chega ao guest; o efeito de pausa não ocorre nesta cena.
- **Não provado:** que a pausa esteja quebrada — pode ser cena sem pausa, ou outro botão.
- Evidência: `boot-132-pause-gameplay.txt`.

**P0-35: mapa de estado — cena estável em 13 amostras / 4.800 frames**

- `cross` mantido, 12.000 frames, 13 capturas: **71,2% não-preto, ~760 cores, top #000000 6,5%**
  em todas. Sem alternância UI↔3D.
- Corrige minha conclusão anterior de "instabilidade": a variação entre runs vem do **ponto de parada
  de cada run**, não do jogo oscilando.
- Evidência: `boot-131-statemap.txt`.

**P0-34: instabilidade de estado (REFUTADO — ver P0-35)**

- Grade de luminância 3×3 no mesmo frame entre execuções: `up/mo/rel/s1/s0` = **78/163/50** (cena 3D),
  `ms` = **247/200/103** (cena clara), `pz` com OPTIONS = **254,5/254,9/246** (**92,6% branco, UI**).
- O mesmo `cross` leva a estados diferentes conforme o timing da captura. O jogo alterna UI ↔ cena 3D.
- **Explica** por que o teste de OPTIONS não pausou gameplay (nos frames 900–1800 era UI) e por que
  `ms` não era comparável.
- **Válido** (os cinco runs com grade 78/163/50): R2 parado = indistinguível do controle;
  R2+stick = 99,20% de cena muda sem cor nova; R2+sensor (gz=40, ativo) = **0,002%** de cor nova.
  **Nenhuma pintura por nenhum caminho.**
- Evidência: `boot-126`…`boot-130`, `boot-125`.

**P0-33: sensores de movimento — implementados e ativos (histórico)**

- **`.uproject` extraído do pak** (offset 53, 1004 bytes) para `gamedump/CUSA11875/ConcreteGenie/`;
  `Project file not found` 1 → 0. Declara os plugins reais: `Morpheus`, `MoveController`,
  `WinDualShock`, `OnlineSubsystem*`. **Não há plugin de pintura por analógico** — confirma que
  pintura é por sensor com analógico como alternativa.
- **Gap real encontrado:** `sample_host` deixava `acceleration`/`angular_velocity` zerados e
  `orientation[3]=1.0f`. Implementado `SDL_SetGamepadSensorEnabled` + leitura com conversão
  (`m/s²→g`, `rad/s→deg/s`). Medido: `gamepad motion sensors: gyro=1 accel=1`.
- Injeção de sensor por `GOW3_PAD_FILE` (`gx= gy= gz= ax= ay= az=`) para teste reprodutível.
- **Pintura continua não observada:** com sensor + R2, cores novas seguem em 0,003% da tela.
- Evidência: `boot-123-uproject.txt`, `boot-124-motion.txt`, `boot-125-motion-injected.txt`.

**P0-32: pintura — R2 NÃO pinta (histórico)**

- Teste 1 (câmera congelada, `0x4200`, sticks 128): R2 vs controle indistinguíveis
  (5.748 vs 5.581 células, overlap 43–50%). Negativo.
- Teste 2 (R2 + stick movendo vs só `cross`): mudança ~13.600 vs ~5.100 células, overlap até 78%.
  Sinal forte, mas não prova.
- Teste 3 (**decisivo** — cor nova aparece e cresce?): cores quantizadas **diminuíram** (1602 → 1582);
  259 cores novas, maior delas **0,004% da tela**; maior crescimento 125 de 129.600 células.
- **Veredito:** R2 com stick altera o regime (câmera/modo), **não deposita tinta**. Os 99,6% de
  overlap vêm de 90% da tela mudando — movimento, não traço.
- **Refuta** a hipótese "R2 pinta" para o mapeamento mouse→analógico direito neste estado do jogo.
- Evidência: `boot-117-paint-frozen.txt` … `boot-122-r2-held.txt`.

**P0-31: R2 no gameplay — muda o regime, pintura não provada (histórico)**

- **`cross` sozinho leva à cena 3D** (80% não-preto, geometria). `cross + r2` **volta** à tela branca
  de UI — meu teste anterior estava invertido.
- **Teste válido** (ambos com `cross`, só R2 difere, ambos na cena 3D, 4 frames distintos):

  | Execução | Entrada | Não-preto | Mudança/frame |
  |---|---|---|---|
  | `g1` | `cross` | **80,70%** | ~6.800 px |
  | `g2` | `cross` + `r2` | **71,06%** | ~2.300 px |

- **Provado:** R2 altera o regime — conteúdo cai 9,6 pontos e a mudança quadro-a-quadro cai ~3×
  (compatível com modo de mira onde a câmera trava).
- **Não provado:** traços na geometria. A diferença é de **cena inteira (99,20%)** e constante nos 4
  frames — assinatura de mudança de modo, não de tinta incremental.
- Evidência: `boot-112-cross-advance.txt` … `boot-116-ingame-r2.txt`.

**P0-30: R2 muda o estado do jogo (histórico)**

- **Teste 1 (inválido):** pintura vs "sem input" deu 100,00% de diferença, mas o controle era uma
  **tela branca estática** (sha idêntico nos 4 frames, 94,07% `#ffffff`). Variava duas coisas.
- **Teste 2 (válido):** mesmos frames, mesma câmera `rx=200`, só R2 difere:

  | Execução | Entrada | Resultado |
  |---|---|---|
  | `p2` | `r2` + `rx=200` | 71,60% não-preto, **3 frames distintos** |
  | `p2c` | `rx=200` | **100% branco, sha idêntico** |

  Ambas saudáveis (8.100–8.400 presents, ~30 fps).
- **Provado:** R2 altera o comportamento; o caminho `GOW3_PAD_FILE` → `libScePad` → R2 → guest
  funciona e o guest reage.
- **Não provado:** que R2 *pinta*. A tela branca sem R2 parece ser um prompt de UI, não a mecânica.
- Evidência: `boot-108-paint.txt`, `boot-109-paint-control.txt`, `boot-110-paint-r2.txt`,
  `boot-111-paint-rxonly.txt`.

**P0-29: áudio — todas as camadas do runtime verificadas corretas (silêncio vem do motor)**

- Eliminação por medição: saída (`938 buffers/5s`, `starved 0`), ganho (1.0), remap (identidade),
  estado do port (`output=0x01`), init única (`AudioInit: call 1 -> 0`) — **todos corretos**.
- `sceAjmInstanceCreate` **nunca chamado**; **nenhum `.at9` aberto** em 130 aberturas; assets existem
  (1.358 `.at9`), codec confere (ATRAC9 = `codec=1`); NGS2 com 0 chamadas; buffer do guest zerado.
- **Nenhum defeito de runtime identificado.** O motor não chega a tocar nada; investigar exige
  rastrear código do guest em execução, não um patch de import.
- Evidência: `boot-106-ajm-instances.txt`, `boot-107-audio-init.txt`.

**P0-28: áudio — infraestrutura completa, assets existem, guest nunca os pede**

- Pak **aberto**: `open(.../concretegenie-ps4_0_p.pak)`.
- Assets **existem** no índice: **1.358 `.at9`** + 417 `.bnk`:
  `Content/Audio/Streams/{_brushchimes,_cutscenes,_music,_musicVR,<idiomas>}` — todos ATRAC9, o
  mesmo codec que o Ajm registrou (`codec=1`).
- Threads do guest criadas: `snd_stream_parsing_thread`, `snd_stream_reader_thread`, `AudioThread`
  → áudio **em streaming**, não sintetizado (explica NGS2 com 0 chamadas).
- **Nenhum `.at9` é aberto** em 130 aberturas de arquivo. O defeito está na decisão do motor de não
  tocar nada, não no decodificador, saída ou dados.
- Evidência: `boot-104-userevent-fixed.txt`, `boot-105-pak-reads.txt`.

**P0-27: `sceKernelAddUserEvent` recusado — RESOLVIDO**

- Implementado devolvendo `K_EINVAL`; o guest chamava **195 vezes com o mesmo id `262147`** (loop de
  retentativa) e a cada recusa o driver logava
  `BRB DRIVER: ! EVENT QUEUE FULL -> CLIENT THREAD FALLING BEHIND !`.
- Após registro real (tabela de 64 slots, idempotente, `GetUserData`/`Delete` reais):
  `AddUserEvent` 195 → **0**, `EVENT QUEUE FULL` 4 → **0**, `BRB WARNING REPORT` 4 → **1**.
- **Não resolveu o silêncio:** `peak 0.0000` persiste. São dois problemas distintos.
- Evidência: `boot-103-late-calls.txt`, `boot-104-userevent-fixed.txt`.

**P0-26: áudio silencioso — o guest entrega zeros (medido na entrada)**

- `GOW3_TRACE_AUDIO_IN=1` inspeciona o buffer **antes** de volume/remap:
  **`raw_peak 0.0000`** em todas as portas (0, 1, 17), todas as chamadas.
- Ganho é neutro (`volume=32768`, `VOLUME_0DB=32768` → 1.0); remap de canal identidade. O runtime
  **não** silencia nada.
- **`GOW3_TRACE_NGS2=1`: 0 chamadas** a `SystemRender`, `VoiceControl`, `ParseWaveformData`,
  `CalcWaveformBlock`. **NGS2 não é o mixer deste jogo** — corrige a afirmação do commit `79e9e18`.
- Unthread de áudio do guest: apenas `AudioThread` (do motor) + `brbDriver`/`brbClient`.
- O silêncio está no conteúdo produzido **pelo motor**, não no runtime de áudio.
- Evidência: `boot-101-ngs2-trace.txt`, `boot-102-raw-audio.txt`.

**P0-25: áudio silencioso — hipótese NGS2 (REFUTADA, histórico)**

- `sceNgs2SystemRender` faz `memset(buffers[i].buffer,0,size)` — o synth do jogo apaga o buffer.
- Os **13 imports NGS2** deste eboot são stubs; `sceNgs2VoiceGetState` zera o estado ("stopped").
- NGS2, **não Ajm**, é o mixer deste jogo. Ajm só é consultado: todos os 94 jobs são
  `STATISTICS_INSTANCE` (`instance=524288`), que retornam cedo por projeto.
- Duas conclusões minhas anteriores corrigidas: (a) "o guest não submete batch Ajm" — submete
  40.800; (b) "`Ajm batches` nunca impresso logo não decodifica" — a linha só sai ao encerrar, e a
  execução foi cortada por timeout.
- `peak 0.0000`, `0/938 loud` é a assinatura de buffer apagado, não de saída de áudio quebrada.
- Implementar NGS2 = sintetizador com voice graph/waveforms/pans, não correção de uma linha.
- Evidência: `boot-99-ajm-trace.txt`, `boot-100-ajm-jobs.txt`.

**P0-24: áudio — cadeia aberta, mixer rodando, conteúdo ausente (histórico)**

- Defeito corrigido: `runtime_audio3d.c` recusava todo `PortOpen`. O guest não caía para estéreo —
  logava `brbDriverBase::Initialize3D(): FAILED TO OPEN 3D AUDIO PORT!` e nunca chamava
  `sceAudioOutOutput`. Recusar silenciava o jogo. Agora o port é entregue e mistura sem
  posicionamento.
- Defeito corrigido: **31 imports** sem nome (não só Ajm). Identificados via
  `runtime/tools/aerolib.inl` e implementados em `runtime/src/runtime_late.c`. `STOP: first
  unsupported PS4 import` desapareceu.
- Medido: `938 buffers/5s (expected 937)`, `max gap 6.76 ms`, `starved 0`,
  **`peak 0.0000`, `0/938 loud`** → o mixer roda e recebe zeros.
- `Ajm batches` nunca é impresso: o guest não submete batch de decodificação. É ausência de
  conteúdo, não falha de saída.
- `brbDriver::Initialize(): NUM CHANNELS ( 8 ) CLAMPED TO 2.` — driver do jogo inicializou.
- Evidência: `boot-95-audio-peak.txt`, `boot-96-audio-fixed.txt`, `boot-97-ajm-named.txt`,
  `boot-98-late-imports.txt`.

**P0-22: cena 3D renderizada — OBSERVADO**

**Movimento de câmera por input — VERIFICADO (com controle negativo)**

- `GOW3_PAD_FILE` com `ly=0`: 4 capturas (2600/3000/3400/3800) com 10.800 frames alcançados.
- **Controle negativo** (sem input, mesmos índices): também muda entre frames
  (`0,00% → 3,83% → 7,17% → 7,28%`), porque a cena anima sozinha. Comparação entre frames
  consecutivos **não** prova input.
- **Teste correto** (mesmo frame, duas execuções): **99,94% dos pixels diferem** nos quatro índices.
- Ambas coerentes: 6.224 cores / 80,16% não-preto (com input) vs 11.147 / 95,99% (sem input).
- **Provado:** `GOW3_PAD_FILE` → `runtime_pad.c` → `libScePad` → guest → câmera → GPU funciona.
- **Não provado:** direção do mapeamento, colisão, caminhada do personagem, pintura.
- Evidência: `boot-93-movement.txt`, `boot-94-noinput-control.txt`.

- Três capturas (frames 2000/3000/4000): 100% não-pretas, todas diferentes, ~4.900 cores distintas
  (gradientes contínuos). Massa iluminada central sobre fundo escuro.
- **Não é jogabilidade**: sem câmera, input, áudio ou save/load verificados.

**P0-23: re-enfileiramento — DEFEITOS MEDIDOS (histórico)**

- `GOW3_TRACE_SHADER_KEYS=1`: **1.262.000 traduções para 409 hashes distintos** (3.085× redundância).
- `GOW3_TRACE_REQUEUE=1`: `same-perm=269.447` (mesma permutação re-enfileirada) e
  `diff-perm=147.757` (permutação nova a cada pedido); `perm` chegou a 28.474 num hash.
- Defeito A: `program->pending` só é setado no compile `initial`; no caminho de permutação nada a
  marca, então o próximo draw repete.
- Defeito B: `perm_idx = modules.size()` antes do enfileiramento; concorrência faz cada draw
  calcular um índice distinto para a mesma `spec`.
- **Correção não aplicada**: toca a concorrência entre thread de desenho e publicador assíncrono;
  sem testes de estresse trocaria desempenho por correção. Contadores ficam no código.
- Evidência: `boot-89-shader-keys.txt`, `boot-90-requeue.txt`, `boot-91-same-spec.txt`.

**P0-20: 0,7 FPS na transição — causa imediata (shader capture síncrono)**

- `Frame stats: 0.7 FPS, worst frame 1416 ms; capture 3256 ms, workers 1322 ms,
  GPU capture wait 3310 ms, 16003 pending draws; 7235 draws/frame; GPU thread idle 0.0%`.
- `QueueShader` roda `TranslateProgram` **na thread da GPU** e faz `capture_job.Wait()`, então cada
  draw que precisa tradução serializa a fila. Com 16.003 pendentes, o frame leva 1,4 s.
- Draws por submissão: 46,9 (frame 1500) → 85,4 (1850) → **90,0** (2000).
- Evidência: `boot-87-long-run.txt`, `boot-88-draws-per-sub.txt`.

**P0-19: passes de cor vazias na transição — investigação**

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

Cada linha abaixo é o que **falta**; nada aqui foi aprovado.

| Item | Estado |
|---|---|
| Primeiro frame / imagem de conteúdo | **EXECUTADO** — frames com conteúdo capturados (`GOW3_FRAME_DUMP_AT`) |
| Cena 3D estável | **EXECUTADO** — faixa `scene` contínua em 4 execuções (ver mapa acima) |
| Intro e menu principal | **PARCIAL** — menu medido por draws (`boot-70`), mas nunca navegado por input |
| Pintura (R2, stick, sensor) | **EXECUTADO e NEGATIVO** — nenhuma cor nova por nenhum dos três caminhos |
| Pausa | **NÃO OBSERVADO** — OPTIONS muda o estado para UI, não congela a cena |
| Áudio (reprodução, pausas, dispositivos) | **NÃO AUDITADO** — runtime correto em todas as camadas; o guest entrega zeros |
| Save/load | NÃO EXECUTADO — formato ainda desconhecido |
| Controles SDL3 gamepad / teclado+mouse | **PARCIAL** — `GOW3_PAD_FILE` move a câmera; mouse não validado |
| Mouse → eixo direito (fallback de pintura) | NÃO IMPLEMENTADO nem validado |
| Câmera, gyro, PS Move, PSVR | NÃO EXECUTADO — imports registrados; sensores do gamepad lidos |
| Frame pacing | **MEDIDO** — mediana 33,34 ms, p99 34,38 ms, 30 FPS estável (`boot-131`) |
| Shader cache cold/warm | NÃO MEDIDO — compilações já caem a 0 após o startup |
| Flicker, iluminação, VRAM, readback | NÃO AUDITADO |
| Outras GPUs | NÃO EXECUTADO — só RTX 5060 |
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
