# Handoff entre IAs

- Data (UTC): 2026-11-01, sessão PROMPT 04 (continuação).
- Branch: `bootstrap/windows`, HEAD `ca2cb59` + esta sessão. Nenhum merge, rebase ou reset executado.
- IA/sessão: agente Hermes (DeepSeek v4.1), sessão de input ancorado por estado.
- Base upstream / submódulos: MediEvil `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94`;
  `git submodule status --recursive` em `docs/BASELINE.md`.
- Build alvo: **CUSA11875** (EU), APP_VER `01.07`, `eboot.bin` SHA-256 `06f143de…33e51`
  (108.601.759 bytes). `CUSA11834` (US) é candidata documental, **não validada**.
- Estado: build exit 0; testes nativos exit 0; **95 testes Python** exit 0; boot sem `STOP` de
  import; cena 3D estável a 30 FPS quando alcançada; **sem áudio, sem pintura, sem save/load
  verificados**.

## Próxima ação única, verificável

Descobrir **o que decide entre a cena e a tela clara**, já que a medição mostra que não é o input.

Hipótese a testar: a execução que termina em `bright` **nunca conclui a carga**. Medir, por frame e
em ambas as execuções, os pacotes de carga concluídos e o estado do `FAsyncLoadingThread`. Se a
execução `bright` tiver 0 pacotes concluídos enquanto a `scene` avança, a causa é IO/carga; se ambas
tiverem a mesma contagem, a causa é de renderização ou de estado do guest e a hipótese cai.

Critério de aceitação: o log nomeia a diferença entre uma execução que chega a `scene` e uma que
para em `bright`, com contadores concretos por frame — ou a hipótese é refutada com os mesmos
contadores. Não declarar gameplay, pausa ou pintura antes disso: sem saber por que a cena às vezes
não é alcançada, qualquer teste de gameplay tem 50% de chance de medir a tela errada.

## Estado atual (critério e counts)

Critério do PROMPT 04 **NÃO atingido**: não existe primeira cena jogável demonstrada com input,
áudio e save. A cena 3D renderiza e é estável, mas a pintura não foi observada por nenhum caminho,
o áudio nunca tocou e o save/load não foi exercitado.

## Onde o estado do jogo está agora (medido, não inferido)

Instrumentação nova (`GOW3_FRAME_MAP=1`) grava por frame a grade de luminância 3×3 da imagem
apresentada e a contagem de draws. Ela substitui a amostragem manual que produziu duas conclusões
erradas. Resumo de quatro execuções independentes:

| Execução | Entrada | Estado observado |
|---|---|---|
| `boot-135` | `cross` | preto 1..586, fade 591..616, **cena 3D 621..9021** |
| `boot-137` | `cross` (repetição) | preto 1..511, fade 516..556, **cena 3D 561..9006** |
| `run5-verify` | `cross`, amostra a cada 10 | preto 1..431, fade 441..461, **cena 3D 471..9601** |
| `boot-140` | `cross` (controle) | preto 1..441, fade 446..491, **UI clara 496..9661** |
| `boot-139` | `cross`, `options` no frame 461 | preto 1..421, fade 426..456, **cena 3D 461..24181** |
| `boot-136` | `cross` + `options` desde o início | preto 1..411, fade 416..461, **UI clara 466..9041** |

Dentro de uma execução o estado **não oscila**: alcançada a cena, ela permanece. **Entre execuções
não é determinístico:** `boot-140`, com a mesma entrada `cross` das outras, terminou em UI clara.
Essa tela é a mesma que aparece com `options` e aparece **sem input nenhum**, portanto não pode ser
atribuída ao OPTIONS — e nenhum teste pode assumir que `cross` leva à cena.

Custo da instrumentação, medido: **3,09 ms por amostra** (readback incluído), estável em 1.800
amostras, com o jogo mantendo 30 FPS. Ela não muda o estado que mede.

## Avanço desta sessão: input aplicado no estado certo, não no frame certo

`scripts/state_anchored_run.py` espera `settle` amostras consecutivas do estado pedido e só então
escreve o pad file, registrando a âncora no log. Ele recusa rodar quando `GOW3_PAD_FILE` e o arquivo
que ele escreve divergem — defeito que fez uma execução inteira ler `buttons=0x00000000` e parecer
válida.

`boot-139`: âncora em `scene` no frame 461, `options` aplicado depois, confirmado no log do pad
(`buttons=0x4000` → `buttons=0x4008`). A cena permaneceu `scene` por ~23.700 frames e continuou se
movendo (delta médio de grade 0,48 contra 0,56 de um controle na mesma cena).

**Consequência:** a tela clara do teste `pz` **não** é efeito de OPTIONS — ela também aparece com
`cross` sozinho. O teste de pausa anterior media um estado de carregamento, não gameplay. **Pausa
continua não observada**, sem evidência de defeito. A pintura segue negativa pelos três caminhos.

## Avanço desta sessão (medido)

Dois bloqueios resolvidos, com o boot parando três estágios mais adiante:

| Métrica | Antes | Agora |
|---|---|---|
| Bloqueio | `abort` sem causa | **jogabilidade não verificada (cena 3D renderiza a 30 FPS)** |
| Reserva do pool 8 GiB | recusada (`NO_MEMORY`) | **concedida** (3 reservas) |
| Threads guest | 0 | **36** |
| Leitura do dump | 0 arquivos | **4.654 leituras, 109.826.114 bytes** |
| AppContent | não inicializava | **inicializado**, perfil offline |
| Exit | 3 (fault) | 20 (import não implementado) |
| Testes Python | 39 | **73** |

### Correção 1 — janela de memória do guest

O guest exige `0x1000000000` + 8 GiB com `MAP_FIXED|MAP_NO_OVERWRITE` (`movabsq` em
`0xdf855e`). O runtime colocava ali um mapeamento de 6 MiB **escolhido por ele** — o log
mostra `guest hint 0x0, flags 0x0`, provando que a colocação era decisão do runtime, não
pedido do guest.

`find_free_unhinted()` em `runtime_memory.c`: colocações sem hint começam em
`USER_MIN + 8 GiB`. As três reservas do guest passam; o mapeamento de 6 MiB foi para
`0x1200000000`. Determinístico em duas execuções.

### Correção 2 — perfil de conteúdo

O pipeline rodava `prepare` e `link` mas não `content_profile.prepare`, então o boot parava em
`STOP: AppContent needs --content-profile`. Gerado `content.bin` e passado com
`--content-profile`.

### Correção 3 — construtor `InitParams`

Tamanho **medido**, não adivinhado, no frame do guest:

```
0x40c762a  leaq -0x398(%rbp), %rbx    ; base do InitParams
0x40c76c1  leaq -0x260(%rbp), %rdi    ; objeto seguinte no mesmo frame
```

`0x398 - 0x260 = 0x138` = **312 bytes**; o objeto termina 560 bytes abaixo do canário.

`runtime/src/runtime_np.c` implementa **apenas construtores** (`C1Ev`/`C2Ev`), com teste que
rejeita qualquer símbolo que não seja construtor. Sem sucesso cego para serviços.

## Bloqueio atual

**O boot não falha mais.** Roda até o timeout (exit 124), sem fault, com o pipeline Gnm→Vulkan
ativo:

```
resolved: 23 / 23                                    (Bink, por nome)
Bink: plugin path set to "/app0/concretegenie/content/bink" (no video loaded)
Barriers: 6145 image barriers in one batch (largest so far)
GPU [Render.Vulkan] <Warning> emit_spirv.cpp:516 Float64 denorm preserving is not supported
```

Duas causas foram encontradas e corrigidas nesta sessão (ambas medidas, ver `docs/MEMORY_AUDIT.md`):

1. **`sceKernelDlsym`** — ligado a `not_found(void)`, assinatura errada; e `runtime_lookup()`
   resolve NID antes de comparar, então um nome puro (`"BinkPluginInit"`) nunca casava. Foi
   preciso `strcmp` direto.
2. **Buffer de SRT** — um único bloco de 32 MB recebia ~1 MB por shader e esgotava no ~32º,
   derrubando 208 de 208 submissões com `code is too big`. Corrigido com cadeia de blocos.

**A cadeia de apresentação foi verificada ponta a ponta** e há frame capturado com conteúdo:

```
Flip: guest submitted-and-flipped #1700 (count=1, vo=1, buf=1, mode=1)
Present: PrepareFrame #1500 (addr=0x4001020000, 1920x1080, pitch=1920)
Swapchain: present #300 -> Success
```

`python scripts/frame_stats.py <frame.raw> --diff <outro>` reporta: 1920x1080, **1,96%** de pixels
não-pretos, caixa `(512, 432, 1412, 584)`, cores `#75622e`/`#024d76`, e **5,65% de pixels
diferentes** entre os frames 300 e 1200 — ou seja, anima.

**O jogo chega ao MENU PRINCIPAL.** Medido por contagem de draws por frame:

| Frame | Draws/frame | Tela |
|---|---|---|
| 60 | ~4 | abertura (0,85% não-preto) |
| 300 | ~3,6 | texto/logo (1,96%) |
| 900 | ~3,3 | barra de progresso (1,36%) |
| 1800 | **~950.000** | **menu (100% não-preto, paleta dourada)** |

Entre 1500 e 1800: 2.169.079 draws. O frame 1800 é 100% preenchido, fundo branco, conteúdo em duas
faixas (y 583..911 e 942..1031) com `#e7b344`/`#de9b0b` — estrutura de menu.

**Ainda não é gameplay.** Sem input, áudio, movimentação, pintura ou save/load testados. O critério
do Prompt 04 continua **não cumprido**, mas o port passou de "tela de título" para "menu".

### Decisão tomada: `Core::init` **recusa**, não sucede

Resolvido nesta sessão. `Core::init` retorna `0x80550003` (NpToolkit2 "não inicializado") em vez
de 0. O call site faz `testl %eax,%eax; je <continua>`, e o ramo de falha do guest (`0x40c791f`)
destrói o objeto, revalida o canário e retorna limpo — recusar é caminho tratado.

O jogo **aceitou a recusa** e continuou (22 threads, 11 arquivos, 176 leituras), avançando pelo
construtor e destrutor de `InitParams` até `TermParams`. Devolver 0 teria feito as 79 funções de
NpToolkit2 acreditarem num subsistema inexistente.

### Tamanho de `InitParams` corrigido: 312 → 352

A primeira medida usou `rbp-0x260` como objeto seguinte; o guest escreve campos até `-0x320` e o
objeto seguinte começa em `-0x238`. Correto: **352 bytes**. Teste novo garante que a constante
nunca fique menor que os campos observados.

### Bloqueio atual: sequência de construtores `Request`

Há **51** construtores/destrutores de `Request`/`Response` do NpToolkit2 neste eboot
(`docs/evidence/prompt04/`). Cada um precisa do próprio tamanho medido no seu call site —
`TermParams` sai de outro ponto (`0x40ca5f6`, objeto em `rbp-0x30`). Escalar sem medir cada um
repetiria o erro dos 312 bytes.

## Meia-verdade corrigida nesta sessão

Eu havia concluído "o runtime escolheu `0x1000000000`". O hint de 0 provava isso **só** para o
mapeamento de 6 MiB. O disassembly do call site mostrou `movabsq $0x1000000000, %rdi` — o
guest **exige** esse endereço para o pool. As duas medições juntas dão a resposta; uma sozinha
levaria a corrigir o lado errado.

## Estado de verificação

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0 |
| `python -m unittest discover -s tests` | exit 0, **43 testes** |
| Boot | exit 20 no import nomeado, determinístico |
| **Primeiro frame / menu / gameplay / áudio / controles** | **NÃO EXECUTADO** |

Áudio, controles, shader cache e frame pacing continuam sem auditoria porque dependem de cena
visível. Os imports de PSVR/câmera/Move já estão registrados em
`docs/evidence/prompt03/imports-gpu-by-library.txt`.

## Próxima ação única, verificável

Descobrir qual input o jogo usa para pausar nesta cena, ou registrar pausa como não observada.

**Feito nesta sessão (mapa de estado + pausa):**

1. **Mapa de estado:** `cross` mantido, 12.000 frames, 13 capturas — **71,2% não-preto, ~760 cores,
   top `#000000` 6,5% em todas as amostras**. Cena estável, sem alternância UI↔3D.
   Isso **corrige** minha conclusão anterior de "instabilidade": a variação entre execuções vinha do
   ponto de parada de cada run, não do jogo oscilando. Mesma classe de erro que a "tela preta".

2. **Pausa com OPTIONS:** aplicado no frame 3000 (`buttons=0x4008` confirmado). A cena continua
   mudando **~5% por frame** depois (`3200: 5,26%`, `3600: 5,79%`, `4400: 5,17%`), cores constantes,
   sem congelamento nem menu.

**Provado:** o input chega ao guest. **Não provado:** que pausa esteja quebrada — pode ser cena sem
pausa, ou outro botão. Registrado como **não observado**, não como bug.

**Pintura — veredito consolidado (inalterado):** negativa por três caminhos na cena 3D comparável —
R2 parado, R2+stick, R2+sensor verificado ativo.

**Próximo passo único:** identificar o botão de pausa. Se OPTIONS não pausa, testar touchpad e
triangle, e verificar se a cena tem menu de pausa por outro gatilho. Sem isso, pausa fica como
"não observada" honestamente.

### Instrumentação que substitui a amostragem manual

`GOW3_FRAME_MAP=1` registra, por frame apresentado, a grade de luminância 3×3 da imagem final e os
draws desde a amostra anterior. `scripts/frame_states.py` classifica cada amostra em
`black`/`fade`/`bright`/`scene` e imprime as faixas de frame.

```bash
env GOW3_FRAME_MAP=1 GOW3_FRAME_MAP_EVERY=10 GOW3_PAD_FILE=".../pad.txt" \
  timeout 320 runtime/out/gpu/cg-runtime.exe .cg/audit/prepared/boot-linked.bin \
  --content-profile .cg/audit/prepared/content.bin --app0 "<dump>" --user .cg/audit/run/user \
  --timeout 290 > run.log 2>&1
python scripts/frame_states.py run.log --frames 3000,4400
```

**Achado que a instrumentação produziu:** o estado alcançado depende do **ponto de parada do boot**,
não do script de input. Quatro execuções com `cross` chegaram à cena 3D em frames diferentes
(471, 561, 621) e permaneceram nela até o timeout, sem alternância. A execução com `options` passou
da cena para uma UI clara em 466 e nunca saiu — 8.500 frames parada ali.

Isso significa que um teste de pausa em `options` a partir do frame 3000 estava medindo uma tela de
UI estática, não gameplay pausado. A cena não "ignorou" OPTIONS; o input chegou mas o jogo já estava
fora da cena.

**Verificado e funcionando:** cena 3D a 30 FPS; input move a câmera (99,94% dos pixels diferem vs
controle sem input); 9.600+ frames; boot sem `STOP` de import; 31 imports antes sem nome agora
resolvidos; mapa de estado por frame com custo medido de 3,09 ms.

**Ainda não verificado:** pintura (R2), save/load, colisão, direção do mapeamento de input.

**Verificado nesta sessão: input move a câmera.**

O teste que **quase** deu falso positivo: com `ly=0`, quatro capturas diferiam progressivamente
(`9,90% / 6,35% / 9,24%`). Mas o **controle negativo sem input** também difere
(`3,83% / 7,17% / 7,28%`) — a cena anima sozinha.

O teste válido compara o **mesmo frame** entre execuções:

```
frame 2600..3800: with-input vs without-input = 99.94% different (4/4)
```

Ambas coerentes: 6.224 cores / 80,16% não-preto (com input) vs 11.147 / 95,99% (sem input). O
caminho `GOW3_PAD_FILE` → `runtime_pad.c` → `libScePad` → guest → câmera → GPU funciona.

**Ainda não verificado:** direção do mapeamento (`ly=0` = frente?), colisão, caminhada, pintura,
áudio de saída, save/load.

Reprodução do teste de movimento (com controle):

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
printf "ly=0
" > pad.txt
env GOW3_PAD_FILE="C:/projetos/concrete-genie-port/.cg/audit/run/pad.txt"     GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/mv"     GOW3_FRAME_DUMP_AT=2600,3000,3400,3800 GOW3_DUMP_SYNC=1     timeout 360 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 330
```

Próximo passo: R2 (pintura) com `GOW3_PAD_FILE` e captura antes/depois, comparando mesmo frame
contra controle sem input — o mesmo método que corrigiu a medição de movimento.
o input documentado. Depois: áudio e save/load.
Frame stats: 0.7 FPS, worst frame 1416.3 ms
  capture 3256.1 ms, workers 1322.7 ms, GPU capture wait 3310.4 ms, 16003 pending draws
  7235 draws/frame, GPU thread idle 0.0%
```

`PipelineCache::QueueShader` (vk_pipeline_cache.cpp:486) executa `Shader::TranslateProgram` na
thread da GPU e **espera** (`capture_job.Wait()`). Com 16.003 draws pendentes, cada tradução
serializa a fila.

Medição que deve vir antes da correção:

1. Contar `TranslateProgram` chamados versus **hashes únicos** no regime lento. Se 16.003 pendentes
   colapsam em poucas centenas de hashes, um cache por hash elimina o custo; se são milhares de
   hashes distintos, o problema é variedade de estado de pipeline.
2. Medir o custo médio de um `TranslateProgram` — se for ~1 ms, 16.003 deles explicam 1,4 s/frame.

Duas alavancas possíveis (escolher depois de medir):
- **Cache de shader por hash** — elimina repetição, sem mudar semântica.
- **Tirar a tradução da thread da GPU** — mantém correção e libera a thread.

Reprodução:

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_FRAME_STATS=1 GOW3_FRAME_DUMP_AT=1500,1850,2000 GOW3_DUMP_SYNC=1     timeout 400 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 370
```

Critério de conclusão: FPS volta a dezenas depois do frame 1800 e uma captura em 2500+ mostra
conteúdo. Não otimizar antes de medir hashes.

Adicionei dois pontos de medição, ambos atrás de `GOW3_TRACE_CLEAR=1`:
- `Scheduler::BeginRendering` → anexos e clears de cada passe.
- `Scheduler::EndRendering` → **draws que caíram dentro do passe**.

Uso:

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_TRACE_CLEAR=1 GOW3_FRAME_STATS=1     GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/tr"     GOW3_FRAME_DUMP_AT=1500,1900,2400,3200 GOW3_DUMP_SYNC=1     timeout 320 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 290
```

## Medido até agora

| Frame | Conteúdo | Observação |
|---|---|---|
| 1200 | 3,71% | pipeline desenha |
| 1500 | 6,50% | idem |
| 1900 | **100%** | menu |
| 2500+ | 0% | preto |

43.935 passes de cor: 84% fecham com 0 draws — mas há passes com 17 draws, e a tela mostra
conteúdo. **"Nada desenha" está errado.**

O bloqueio prático: a execução **não passa do frame ~1800** dentro de 290-320 s de `timeout`, então
não consigo capturar 2400/3200 para ver o período preto. A fase de carga consome quase todo o tempo.

## Próximo passo

Duas opções, ambas concretas:

1. **Aumentar a janela** para ~600 s e capturar 2400/3200 com `GOW3_TRACE_CLEAR=1`, comparando
   draws por passe entre o período que funciona e o preto. É a medição que fecha a questão.
2. **Pular a carga**: verificar se há um modo de iniciar direto no menu (o jogo monta
   `CheckPoint1`; se ele retomar de save, o menu pode ser alcançável em menos frames).

Critério de conclusão: comparar draws/passe em frame que funciona versus frame preto, e nomear se o
guest parou de submeter ou se o estado de render está errado.

**Fato controlado:** o jogo carrega, mostra o menu (~frame 1700-1800, 100% de pixels), e então fica
**inteiramente preto** e permanece. Sem nenhum input acontece igual (frames 2500/3500/5000/8000
todos em 0,00%). Portanto **input não é a causa** — hipótese testada e refutada.

`display_*` e `output_*` ficam pretos **ao mesmo tempo**, então a origem está no framebuffer do
guest, não no caminho de apresentação.

O motor continua saudável: 60 FPS, 1 draw/frame, GPU ociosa, `pad read #13801` com stick vivo.
Não é travamento.

Próximo passo — escolher entre duas medições:

1. **Contar os draws que chegam ao framebuffer do guest.** 1 draw/frame com tela preta sugere que o
   guest parou de emitir geometria; se ele emite e o preto persiste, o problema é de estado de
   render (blend, clear, viewport).
2. **Verificar clears.** Um `sceGnmDrawInitDefaultHardwareState`/clear preto por frame explicaria
   tudo. Logar clears por frame é pequeno e decisivo.

Descarte antes de investigar: paks (abertos), `usrdt53l` (ausente do dump, não é laço), GPU
performance (60 FPS), input (refutado), buffer de SRT (corrigido, 4 blocos).

Comando base:

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_FRAME_STATS=1 GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/nopad2"     GOW3_FRAME_DUMP_AT=2500,3500,5000 GOW3_DUMP_SYNC=1     timeout 340 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 310
python scripts/frame_stats.py nopad2/output_002_1920x1080.raw
```

Critério de conclusão: uma captura pós-menu com conteúdo. Não declarar jogável sem movimento,
input verificado e áudio.

**Correção de medições minhas anteriores:** "950 mil draws/frame" e "saturação a 3,7 fps" estavam
erradas (contador cumulativo e fase de carregamento, respectivamente). O estado real, com
`GOW3_FRAME_STATS=1`:

```
Frame stats: 60.0 FPS, worst frame 18.4 ms (vblank 60 Hz); 0 shader compiles;
  GPU thread 0.00 us/draw, 1-6 draws/frame, idle 0.1%
```

60 FPS estável, GPU ociosa, 1-6 draws/frame. O áudio inicializou
(`audio port 0 opened, 8 ch float`). 39 threads guest, incluindo `FAsyncLoadingThread` e
`FSaveLoadWorker`.

Próximo passo — identificar o estado, não otimizar:

1. `CheckPoint1` é montado duas vezes. Verificar se a segunda é reentrada legítima ou laço:
   adicionar contador em `save_mount` por nome.
2. `FAsyncLoadingThread` existe: contar pacotes de carga concluídos por segundo. Se for 0, a carga
   travou e o problema está no IO; se >0, está progredindo e só precisa de mais tempo.
3. Se ambos estiverem parados, o bloqueio é um evento de jogo (input/diálogo): enviar input via
   `GOW3_PAD_FILE` e ver se o estado muda — o guest lê o pad 1800+ vezes com valores reais.

Comando base (note `env`, obrigatório):

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_FRAME_STATS=1 GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/tlB"     GOW3_FRAME_DUMP_AT=1900 GOW3_DUMP_SYNC=1     timeout 200 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 170
```

Critério de conclusão: o estado muda (novo conteúdo na captura) e o motivo da espera está nomeado
num log. Não otimizar FPS: já são 60.

O avanço desta sessão: `sceSaveDataGetParam` era o import que barrava; implementado, o boot saiu de
`exit 20` (frame 1200) para `exit 124` (frame 1800). Agora ele **para de apresentar** em ~1800 sem
fault e sem erro — sintoma diferente, ainda não diagnosticado.

Suspeitas em ordem de probabilidade:
1. **Espera de IO/save** — `sceSaveData*` foi recentemente ligado; um mount ou leitura pode estar
   bloqueando. Medir com `GOW3_FILE_TRACE=1` se há um open pendente depois do frame 1800.
2. **Saturação ao entrar em 3D** — 2,8 M draws num único frame; o pipeline pode estar levando
   minutos por frame em vez de travar. Medir o intervalo entre apresentações.
3. **Diálogo modal** — o jogo pode estar esperando confirmação de um diálogo do sistema.

Reprodução:

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_FILE_TRACE=1 GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/tl9"     GOW3_FRAME_DUMP_AT=1900,2400,3000 GOW3_DUMP_SYNC=1     timeout 230 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 200
```

Critério de conclusão: o contador de frames passa de 1800 e uma captura mostra conteúdo novo.
Depois disso, testar input no menu (o guest já lê o pad: `pad read #1801`, com drift real do
DualSense em `lx=130 ly=120 rx=96 ry=136`).

O menu principal é alcançado por volta do frame 1800. O próximo passo deixa de ser diagnóstico de
renderização e passa a ser interação: apertar um botão e ver o menu responder.

1. Capturar o menu com `GOW3_FRAME_DUMP_AT` e confirmar os limites exatos das entradas.
2. Enviar input (SDL gamepad já conectado: DualSense) e capturar de novo — a seleção mudou?
3. Se o menu não responde, o bloqueio é input, não GPU: auditar `scePadReadState` e o caminho
   SDL3 → estado do pad do guest.
4. Depois do menu: áudio (`sceAudioOut`, `sceAudio3d`) e save/load.

Reprodução:

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/tl3"     GOW3_FRAME_DUMP_AT=1500,1800,2100 GOW3_DUMP_SYNC=1     timeout 240 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 210
python scripts/frame_stats.py tl3/output_001_1920x1080.raw
```

Critério de conclusão: o menu responde a input (captura antes/depois diferente na seleção) e há
áudio. Não declarar jogável sem movimentação e pintura.

**Correção importante:** eu havia concluído que o runtime não lia os paks. **Estava errado** —
aquela conclusão veio de um log sem `GOW3_FILE_TRACE=1`. Medido agora: o diretório de paks é
enumerado, os dois paks são abertos, e o motor roda com `-pak`. Nenhum erro de versão.

1. Suspender a hipótese de pak: ela está descartada por medição.
2. `usrdt53l.dat` também está descartado: não existe no índice do pak nem no manifesto non-UFS.
3. Atacar o aviso real de GPU: `SanitizeCopyLayers` clampa layers divergentes em **todos** os mips
   (`vk_runtime.cpp:40`). Medir se a divergência 5→6 é legítima ou sintoma de descrição de imagem
   errada — e se o clamp descarta dados que a cena precisa.
4. Comparar capturas com `python scripts/frame_stats.py <a.raw> --diff <b.raw>` enquanto o jogo
   roda mais tempo (o conteúdo cresce de 1,96% para 3,71% entre os frames 300 e 1200).

Reprodução (o `env` é obrigatório):

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_FILE_TRACE=1 GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/dump"     GOW3_FRAME_DUMP_AT=1200 GOW3_DUMP_SYNC=1     timeout 160 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 130
python scripts/frame_stats.py dump/output_000_1920x1080.raw
```

Critério de conclusão: identificar se o clamp de layers descarta conteúdo, e obter um frame com
cena coerente em área significativa da tela. Não declarar cena jogável sem movimento, input e áudio.

A causa do fault já está medida (`docs/MEMORY_AUDIT.md`): o jogo resolve 8 funções do plugin Bink
por `sceKernelDlsym` para slots em `.bss` e as chama sem testar nulo; o módulo existe em
`gamedump/CUSA11875/prx/binkpluginps4.prx`, mas `sceKernelLoadStartModule` o recusa com
"not available".

1. Implementar mapeamento real de módulo em `load_start_module` (`runtime/src/runtime_extra.c`):
   mapear o ELF do `.prx`, aplicar relocações, resolver imports contra os módulos já ligados.
2. Fazer `sceKernelDlsym` procurar os símbolos exportados pelo módulo carregado — hoje ele só
   tenta `runtime_resolve` e falha.
3. Verificar com `--check-imports` e com o boot que os 8 slots são preenchidos.

Critério de conclusão: os slots `0x618f738`..`0x618f7b8` recebem endereços não nulos e o fault em
`RHIThread` muda de lugar. Não preencher os slots com stubs vazios para "passar": o plugin desenha
vídeo e devolver um no-op deixaria o jogo acreditando que o vídeo foi apresentado.

## Reprodução

```bash
# prepare + link + content profile sobre o dump (escreve só em .cg/)
python - <<'PY'
import sys; from pathlib import Path
sys.path.insert(0,'runtime/scripts')
from prepare import prepare; from link_modules import link; from content_profile import prepare as cp
g=Path('gamedump/CUSA11875'); o=Path('.cg/audit/prepared')
prepare(g,o); link(g,o,module_names=('libc.prx','libSceFios2.prx')); cp(g,o)
PY

runtime/out/gpu/cg-runtime.exe .cg/audit/prepared/boot-linked.bin \
  --content-profile .cg/audit/prepared/content.bin \
  --app0 "$PWD/gamedump/CUSA11875" --user .cg/audit/run/user --timeout 60
# esperado: exit 20, STOP no import NpToolkit2 InitParams
```
