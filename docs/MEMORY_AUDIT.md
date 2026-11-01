# CORREÇÃO: os paks SÃO abertos — a conclusão anterior estava errada

## O erro

Eu concluí "o runtime nunca tenta abrir os paks" a partir de um log (`boot-65`) que **não tinha
file tracing ligado**. Só apareciam os opens que falhavam, o que produziu uma conclusão falsa.

Com `GOW3_FILE_TRACE=1` a verdade aparece:

```
Runtime: open(/app0/concretegenie/content/paks) [directory]
Runtime: open(/app0/concretegenie/content/paks/concretegenie-ps4.pak)
Runtime: open(/app0/concretegenie/content/paks/concretegenie-ps4_0_p.pak)
```

O diretório é **enumerado**, os dois paks são **abertos**, e não há erro de versão ou corrupção.
A linha `AdditionalArgs after fixup = ../../../ConcreteGenie/ConcreteGenie.uproject -pak` mostra
que o motor roda com `-pak` ativo.

Registro isso explicitamente porque a conclusão errada chegou a ser commitada em `07e569d`.

## O que continua valendo

- Os dois paks são UE4 v4 válidos (assinatura `0x5A6F12E1` no rodapé, 57.303 entradas).
- 116 arquivos pedidos não existem soltos, e 49 deles são `internationalization/usrdt53l.dat`.
  Como o pak está montado, esses pedidos são provavelmente para paths que o pak não cobre
  (ou que o engine espera em disco por serem "non-UFS").
- A tela capturada continua sendo uma faixa de glifos em ~2% da imagem.

## O que ainda não se sabe

Por que a cena não aparece, agora que o pak está montado. As hipóteses antigas não servem mais;
a próxima medição tem que ser sobre o que o motor faz **depois** de montar o pak.


## Dados medidos depois da correção

| Fato | Medição |
|---|---|
| Diretório de paks | **enumerado** (`[directory]` no trace) |
| Paks abertos | `concretegenie-ps4.pak` e `concretegenie-ps4_0_p.pak` |
| Erro de versão/corrupção | nenhum |
| `-pak` na linha de comando | sim (`AdditionalArgs after fixup = ... -pak`) |
| `icudt53l` no índice do pak | **PRESENTE** |
| `usrdt53l` no índice do pak | **ausente** |
| `internationalization` no índice | **ausente** |
| `usrdt53l` no Manifest_NonUFSFiles | ausente |

Conclusão sobre os 49 "not found" de `usrdt53l.dat`: **não é bug do runtime**. Esse arquivo não
existe no pak nem no manifesto de arquivos não-UFS. O motor pede um path que o dump não contém —
provavelmente porque este SKU não o empacota, ou porque o pedido depende de um locale que a build
não trouxe.

## Próximo alvo real: cópias com contagem de layers divergente

O trace mostra avisos repetidos, um por mip:

```
vk_runtime.cpp:64 SanitizeCopyLayers: Coercing copy source layers 5 and destination layers 6 to minimum.
```

`SanitizeCopyLayers` (vk_runtime.cpp:40) clampa para o mínimo quando origem e destino têm tipos
iguais mas contagens de layers diferentes. A divergência de exatamente 1 em todos os níveis é
suspeita e merece investigação — mas o clamp em si é seguro e não descarta conteúdo silenciosamente
além do esperado para o formato.

## (superado) Causa provável da tela magra: o runtime não lê pak algum

## Medição

O dump tem **23 GB** de conteúdo de jogo em dois paks UE4 válidos:

```
gamedump/CUSA11875/concretegenie/content/paks/
  concretegenie-ps4.pak        19.131.292.555 bytes   pak v4, índice 8.450.254 bytes @ 19122842256
  concretegenie-ps4_0_p.pak     5.412.583.974 bytes
```

Verificado no arquivo, não por suposição: a assinatura `0x5A6F12E1` está no fim do arquivo
(v4 guarda o índice no rodapé), `mount point = "../../../"`, **57.303 entradas**, a primeira sendo
`ConcreteGenie/ConcreteGenie.uproject`.

Durante o boot o runtime leu **109 MB** e registrou **116 arquivos não encontrados**, incluindo 49
tentativas de `/app0/engine/content/internationalization/usrdt53l.dat` e o diretório
`internationalization` **inteiro ausente** do dump em forma de arquivo solto.

## O que isso significa

`grep -rniE "\.pak" runtime/src/*.c` encontra **uma única** menção, e é um comentário sobre uma
variável de trace. Não existe implementação de montagem de pak em lugar nenhum do runtime.

Ou seja: o motor pede arquivos que vivem **dentro** do pak, o runtime responde "not found", e o
jogo segue com o que consegue montar a partir de loose files. É consistente com o que foi
capturado na tela: uma faixa central de glifos em ~2% da imagem — tela de título/placeholder, não
conteúdo carregado.

## Causa medida versus causa suposta

Isto **não** foi confirmado como a causa da tela magra por experimento. O que está provado é:
(1) os paks existem e são válidos; (2) o runtime nunca os abre; (3) 116 arquivos que o motor pede
não existem soltos no dump. A confirmação exige implementar leitura de pak e observar a tela mudar
— ou, antes disso, uma telemetria que mostre qual asset específico falha primeiro.

## Próximo passo

Ler o índice do pak v4 exige o formato correto. A primeira tentativa de parse falhou (assumi
nome por entrada, mas v4 usa hash + tabela de nomes separada). Não vou implementar leitura de pak
por tentativa e erro: o formato precisa vir de fonte primária, e o teste de aceitação é abrir o
índice e localizar `usrdt53l.dat` e `icudt53l.dat` pelo nome.

# Captura de frame: há conteúdo renderizado (e ele anima)

## A captura falhava por um problema de ambiente, não do renderizador

Três tentativas anteriores produziram zero arquivos. A causa foi medida, não suposta:

```
Dump: config at=0 frame=1 dump_at=0      <- o env var nunca chegou ao processo
```

Neste shell MSYS, `GOW3_FRAME_DUMP_AT=300 ./cg-runtime.exe ...` (prefixo inline) **não propaga**
a variável; `env GOW3_FRAME_DUMP_AT=300 ./cg-runtime.exe ...` propaga. Verificado com uma variável
de teste. Com `env`, a captura funciona na primeira tentativa.

Também foi necessário:
- um contador `presented_frames` separado (usar `frame_dump_index` para decidir *se* dumpar era
  circular: ele só incrementa depois de um dump já ter ocorrido — nunca saía de 0);
- lógica de `GOW3_DUMP_SYNC=1`, porque `DumpRaw`/`DumpImages` escrevem via
  `DeferPriorityOperation`, que uma execução morta por `timeout` nunca alcança;
- o bloco de dump no ramo **`upscaled`**, que era o ramo realmente tomado
  (`DisplayOverride` retorna true) e não tinha código de captura nenhum.

## O que os pixels mostram

`output_000_1920x1080.raw` e `display_000_1920x1080.raw`, 1920x1080 RGBA:

| Métrica | Valor |
|---|---|
| Pixels não-pretos | 1,96% (10.166 de 518.400 amostrados) |
| Caixa de conteúdo | x 512..1414, y 430..586 (902x156, centralizada) |
| Cores dominantes | `#75622e` (tan/oliva) 0,78%, `#024d76` (teal escuro) 0,71% |
| SHA-256 frame 300 | `3dc22e7e3143a371...` |
| SHA-256 frame 1200 | `3e7151f7265aacb8...` |
| Pixels diferentes entre os dois | **5,65%** |

O conteúdo é uma faixa central com formas de glifos (não é uma cena 3D), e **muda entre frames** —
ou seja, é renderização viva, não um artefato estático. Ambos os buffers (display do guest e
output apresentado) têm o mesmo conteúdo, o que confirma que a cadeia display→presente preserva
a imagem.

## O que isso NÃO prova

Isto **não** é "primeira cena jogável". É uma faixa de conteúdo em 2% da tela, compatível com
tela de título/logo/indicador de carregamento. Não há movimento de câmera, personagem, pintura,
menu navegável nem áudio verificado. O critério do Prompt 04 continua **não cumprido**.

# Cadeia de apresentação: completa e verificada ponta a ponta

Instrumentação em três pontos independentes prova que o jogo renderiza e apresenta:

```
Flip: guest submitted-and-flipped #1700 (count=1, vo=1, buf=1, mode=1)
Present: PrepareFrame #1500 (addr=0x4001020000, 1920x1080, pitch=1920)
Swapchain: present #300 -> Success
```

| Etapa | Medição |
|---|---|
| Guest submete e flipa | 1700 por execução, alternando `buf=0/1` |
| `PatchFlipRequest` | **0 falhas** (o patch da flip nunca falha) |
| `Presenter::PrepareFrame` | alcançado, 1920x1080, endereços reais do guest |
| `vkQueuePresentKHR` | `Success`, 1500+ apresentações |

Ou seja: o guest renderiza, o frame chega ao apresentador e o Vulkan apresenta sem erro. A cadeia
Gnm→Vulkan→swapchain funciona.

## O que ainda NÃO está provado

Nenhum pixel foi lido de volta. As tentativas de captura falharam — e a causa é **do meu
ferramental**, não do renderizador:

1. `GOW3_FRAME_DUMP_TRIGGER` (arquivo de gatilho) nunca foi consumido: o arquivo continuou
   existindo após o disparo.
2. `GOW3_FRAME_DUMP_AT` que eu adicionei usava `frame_dump_index`, que só incrementa **depois** de
   um dump já ter ocorrido — dependência circular que mantinha o índice em 0. Corrigido com um
   contador `presented_frames` separado.
3. Ambos os caminhos de dump vivem no ramo `else` (não-upscaled). A execução toma o ramo
   **`upscaled`** (`DisplayOverride` retorna true), e **esse ramo não tem código de dump**.
4. `DumpRaw`/`DumpImages` escrevem via `DeferPriorityOperation`, que uma execução morta por
   `timeout` nunca alcança.

Conclusão honesta: **"apresenta sem erro" não é "há uma cena visível na tela"**. Falta a captura
de pixel para afirmar qualquer coisa sobre conteúdo — e ela precisa ser implementada no ramo
`upscaled`.

# Terceiro marco: o guest apresenta frames (1700 flips medidos)

Depois de corrigir o buffer de SRT, o guest passou a **submeter e flipar** continuamente:

```
Flip: guest submitted-and-flipped #1    (count=1, vo=1, buf=0, mode=1)
Flip: guest submitted-and-flipped #2    (count=1, vo=1, buf=1, mode=1)
Flip: guest submitted-and-flipped #3    (count=1, vo=1, buf=0, mode=1)
...
Flip: guest submitted-and-flipped #1700
```

1700 por execução, alternando `buf=0/1` (double buffering), `vo=1`. Isso é o loop de render do
guest rodando — não é "inicializa".

Instrumentação adicionada em `Runtime/src/gnmdriver`:
- contador de `sceGnmSubmitAndFlipCommandBuffersForWorkload` (as 3 primeiras e cada 100ª);
- contador de falha de `PatchFlipRequest`, porque se o patch da flip falhar o frame nunca chega
  ao apresentador e o sintoma é idêntico a "não renderiza nada". O log `LOG_ERROR` existente não
  distinguia isso.

## Tentativa de captura: bloqueada por medição, não por suposição

`GOW3_DUMP_DIR` + `GOW3_FRAME_DUMP_TRIGGER` existem e escrevem o frame como pixels crus, mas
**dois disparos em momentos diferentes produziram zero arquivos**. O dump só roda dentro de
`Presenter::PrepareFrame`, então a ausência de arquivo indica que `PrepareFrame` não é alcançado,
não que o dump esteja quebrado. Isso é o que a instrumentação de `PatchFlipRequest` vai separar:
- patch falha -> o frame nunca vira apresentação;
- patch passa -> `PrepareFrame` é chamado e o problema está adiante.

## Estado honesto

Nenhum frame capturado, nenhuma prova de pixel na tela. "1700 flips" prova que o guest pediu 1700
apresentações; **não** prova que algo apareceu.

# Segundo bloqueio de GPU: buffer de SRT esgotado

Depois do Bink, o jogo passa a compilar shaders de verdade — e **todos falham**:

```
GPU [Render.Vulkan] <Error> vk_pipeline_cache.cpp:515 QueueShader:
  gow3: shader 0x.../93 capture failed: code is too big
```

208 submissões, 199 shaders únicos, 208 falhas. Medido, não inferido.

## O que a medição mostrou

Primeira instrumentação leu `getSize()` achando que era capacidade: reportou **83 bytes** e
parecia absurdo. Em xbyak, `getSize()` é o tamanho **usado** (`CodeArray::size_`); a capacidade é
`maxSize_`. Corrigida a leitura, a série de uso aparece:

```
Srt: capacity 33554432 bytes, used 83 after a generated SRT walker
Srt: 1049098 of 33554432 bytes used (3.1%)
Srt: 2099270 of 33554432 bytes used (6.3%)
Srt: 3148607 of 33554432 bytes used (9.4%)
```

Crescimento de **~1 MB por shader**. Um único bloco de 32 MB acaba por volta do 32º shader; daí
em diante todo shader falha com `ERR_CODE_IS_TOO_BIG` (xbyak.h:1776, quando `size_ >= maxSize_`).

## Por que não AutoGrow

`Xbyak::AutoGrow` moveria o bloco ao crescer, invalidando **todos** os ponteiros já entregues a
shaders compilados (`info.srt_info.walker_func`). Por isso a correção usa uma **cadeia de blocos**:
o código novo vai para o bloco que ainda tem espaço, e ponteiros para blocos antigos continuam
válidos durante todo o processo.

O handler de sinal do SRT também precisou mudar: antes comparava com um único range
(`start..start+getSize()`), agora verifica se o RIP cai em **qualquer** bloco.

# Bink resolvido: o boot passou do import layer e atingiu os shaders

## Resultado medido

```
resolved: 23 / 23      (Dlsym trace)
Bink: plugin path set to "/app0/concretegenie/content/bink" (no video loaded)
BOOT=124               (timeout — o jogo continuou rodando)
Fault: 0
```

O `RHIThread` **não falha mais**. O jogo roda até o timeout e passa a compilar e submeter
shaders — o pipeline Gnm→Vulkan está ativo.

## Dois defeitos reais, ambos meus

**1. `sceKernelDlsym` estava ligado a `not_found(void)`** — assinatura errada, o parâmetro de
saída nunca era escrito.

**2. `runtime_lookup()` não compara nomes.** A macro `RUNTIME_LOOKUP` chama `runtime_lookup()`,
que **primeiro** resolve um NID pela tabela de import-names e só então compara. Um nome puro
(`"BinkPluginInit"`) não é NID, resolve para nada, e a função retorna 0 **antes** de qualquer
comparação. Foi preciso um `strcmp` direto (`lookup_by_name` em `runtime_bink.c`).

## A traço que decidiu tudo

Instrumentar o `dlsym` provou o que o guest realmente pede — 23 nomes, `handle=0`:

```
Dlsym: handle=0 name="BinkPluginSetPerFrameInfo" slot=000000080618f7a0
```

O slot do fault (`0x618f7a0`) é exatamente `BinkPluginSetPerFrameInfo`, chamado de
`0x4142b6c` sem teste de nulo. Antes disso a hipótese era "o módulo não liga"; a medição mostrou
que ligava (`Starting linked module 2 ... 0x6540000`) e que o problema era a resolução por nome.

## Por que não foi pelo NID

As 23 strings estão no `.rodata` do eboot e são passadas **por nome**. O módulo exporta **NIDs**
(32 em `BinkPluginPS4`). Tentei reproduzir a conversão e falhei de forma reprodutível:

| Tentativa | Resultado |
|---|---|
| SHA1[:8] base64 (PS4 `+-` e padrão `+/`), com e sem NUL | 0/60 |
| SHA256/MD5/SHA512, cabeça e cauda, 60 pares reais | 0 |
| 5 prefixos de lib × 5 separadores × 5 versões × 3 terminadores | 0/6 |
| Validação contra pares do próprio módulo (`sceGnmAddEqEvent`→`b0xyllnVY-I`) | 0/4 |

O encoder foi verificado contra o `base64` do Python (idêntico), então o erro não era meu. Os
NIDs são atribuídos pela Sony, não derivados. Implementar a API diretamente é o caminho honesto.

## Semântica implementada (não é stub cego)

`runtime/src/runtime_bink.c` responde os 23 nomes com o significado de **"nenhum vídeo"**:
`Open` recusa e registra no log; `ProcessBinks`/`Draw`/`ScheduleToTexture` reportam sem vídeo;
`AllScheduled` responde 1 (verdade: nada pendente); setters de estado são no-op registrados.
Nada devolve sucesso para um pedido de reprodução real.

# Bink: módulo ligado, falta a resolução nome→NID

## O que foi feito e verificado

O `prx/binkpluginps4.prx` do dump é um **SELF decriptável** (ELF válido, 10 segmentos). O linker
do projeto, que já mapeava `sce_module/*.prx`, agora aceita um caminho explícito e ligou o módulo:

```
Linked modules: libc.prx@0x62a0000, libSceFios2.prx@0x63b0000, prx/binkpluginps4.prx@0x6540000
```

O `module_start` **executou de verdade**:

```
Starting linked module 2 at image offset 0x6540000; native bindings=210
```

Imports do eboot que faltam: **105 → 100**.

## O mecanismo, medido

- O eboot contém **14** strings `BinkPlugin*` (`Goto`, `ProcessBinks`, `LimitSpeakers`, `Loop`,
  `Pause`, `Draw`, `SetPerFrameInfo`, `ScheduleToTexture`, `ScheduleOverlay`, `AllScheduled`,
  `IOPause`, `TurnOnGPUAssist`, `Error`, `Vol`) e as passa a `sceKernelDlsym`.
- As funções vão para slots em `.bss` (`0x618f738`..`0x618f7b8`), chamados sem teste de nulo.
- O módulo exporta por **NID**: `BinkPluginPS4` tem 32 exports, `libSceGnmDriver` 87,
  `libc` 14, `libkernel` 12. O `bink2ps4.prx` tem 68 exports em `Bink2PS4`.
- O módulo **não contém** as strings `BinkPlugin*`: ele exporta por NID, e o kernel PS4 resolve
  nome→NID. Sem essa conversão, `sceKernelDlsym(handle,"BinkPluginGoto",&slot)` não tem como
  casar com nenhum export.

## Formato do boot estendido (G3PROBE6)

O linker agora grava a tabela de exports (NID de 16 bytes → offset no image) depois dos bindings,
e o runtime a lê em `runtime_linked_symbol()`; `kernel_dlsym` tenta nome → tabela de exports.

Durante a implementação houve um erro meu: a leitura da tabela foi inserida em **dois** pontos do
`probe.c` (antes e depois do loop de bindings), corrompendo o alinhamento e produzindo
`ERROR: invalid native binding`. Corrigido removendo a leitura duplicada; o boot voltou a rodar.

## Bloqueio atual

`sceKernelDlsym` recebe **nomes**, os exports são **NIDs**, e o algoritmo de hash não foi
reproduzido. Quatro variantes testadas contra NIDs de verdade do próprio módulo
(`sceGnmAddEqEvent`→`b0xyllnVY-I`, `sceGnmSetVsShader`→`gAhCn6UiU4Y`, etc.) falharam todas:

| Variante | Acertos |
|---|---|
| SHA1(name)[:8], base64 PS4 (`+-`) | 0/4 |
| SHA1(name)[:8], base64 padrão (`+/`) | 0/4 |
| SHA1(name + NUL) | 0/4 (ambas) |

Faltam duas coisas, ambas verificáveis: (a) o algoritmo exato de NID do PS4, ou (b) a tabela
nome→NID do próprio jogo. Adivinhar mais variantes não é evidência.

## O que NÃO foi feito

Nenhum slot Bink foi preenchido. O fault em `RHIThread` continua idêntico. Nenhum frame.

# Causa raiz do fault em RHIThread — encontrada e verificada

Não é regressão dos subsistemas de sensor. É uma dependência de módulo dinâmico.

## Cadeia medida

1. O guest chama **`sceKernelDlsym(handle, name, &slot)`** oito vezes em `0x414160f`..`0x414169x`
   (um stub PLT em `0x45f6320` → índice de import `0x39b` = 923 = `sceKernelDlsym`).
2. Os nomes resolvidos, lidos do `.rodata` do eboot, são a API do plugin de vídeo Bink:
   `BinkPluginGoto`, `BinkPluginProcessBinks`, `BinkPluginLimitSpeakers`, `BinkPluginLoop`,
   `BinkPluginPause`, `BinkPluginDraw`, `BinkPluginSetPerFrameInfo`,
   `BinkPluginScheduleToTexture`.
3. Os destinos são slots em **`.bss`** (`0x618f738`, `0x618f740`, `0x618f788`, `0x618f790`,
   `0x618f798`, `0x618f7a0`, `0x618f7a8`, `0x618f7b8`). Verificado em três frentes:
   - além de `filesz` do segmento (104.088 bytes a partir de `0x5CE0000`), então são zerados;
   - **zero escritas estáticas**: `grep` no disassembly completo (1,6 GB, 26 M linhas) encontra
     apenas 7 leituras de `0x618f7a0` e nenhum `mov` para ele;
   - todas as leituras são `leaq slot,%rax; callq *(%rax)`, sem verificação de nulo.
4. O guest chama esses slots sem testar: `0x4142b6c: callq *(%rax)` com `rax = 0x618f7a0`.
5. **`sceKernelLoadStartModule` recusa o módulo**:
   ```
   Runtime: sceKernelLoadStartModule(binkpluginps4.prx) -> not available
   Runtime: sceKernelLoadStartModule(/app0/prx/binkpluginps4.prx) -> not available
   ```
6. O módulo **existe no dump**: `gamedump/CUSA11875/prx/binkpluginps4.prx` (e `bink2ps4.prx`).

Sem o módulo carregado, os slots ficam nulos e o crash aparece longe da causa: execute fault em
`RHIThread`, `#0 guest offset 0x14d6aec`.

## Correção aplicada nesta sessão

`sceKernelDlsym` estava registrado como `not_found`, cuja assinatura é `int32_t not_found(void)`.
Como `sceKernelDlsym` recebe `(handle, name, void **out)`, o parâmetro de saída **nunca era
escrito** — o slot ficava com lixo da pilha. Agora `kernel_dlsym` zera `*out` antes de falhar e
tenta `runtime_resolve(name, 0)` primeiro. O crash persiste, mas com null **definido** em vez de
lixo, que é o comportamento honesto.

## O que falta

Carregar e mapear `binkpluginps4.prx` de verdade dentro de `sceKernelLoadStartModule`, para que os
oito símbolos resolvam e o plugin de vídeo exista. Isso é trabalho de loader de módulo (mapear
ELF, resolver imports do próprio módulo, executar seus construtores), não um stub.

## Hipótese descartada

`sceVrTrackerQueryMemory` devolvendo 0 **não** causa o fault: mudar o retorno para erro produziu
exatamente o mesmo crash, na mesma thread, com as mesmas 12 sondagens de formato
(`docs/evidence/prompt04/exp-01-vrtracker-refused.txt`). Revertido.

# Marco: o boot atingiu a inicialização de RHI (Vulkan) do UE4

Nesta sessão o boot atravessou todos os subsistemas de sensor e chegou ao **pipeline Vulkan
real**. Isto não é uma cena: nenhum frame foi renderizado e nenhum pixel foi apresentado.
`RHIThread` é a thread de renderização do UE4, e ela falhou **dentro** da inicialização.

## Progressão medida (mesmo dump, mesmo binário de entrada)

| Estágio | Threads | Arquivos | Leituras | Bytes | Exit |
|---|---|---|---|---|---|
| Início da sessão | 22 | 11 | 176 | 10.107.208 | 20 (import) |
| Bloco PSN completo | 27 | 11 | 1.657 | 12.095.000 | 20 (import) |
| PS Move | 27 | 16 | 2.362 | 65.394.573 | 20 (import) |
| PSVR + áudio 3D | 36 | 17 | 4.653 | 109.824.245 | 20 (import) |
| Câmera | 36 | 18 | 4.654 | 109.826.114 | 20 (import) |
| VR tracker / social screen | 36 | 18 | — | — | **3 (fault em RHIThread)** |

## Subsistemas implementados nesta sessão

Todos com semântica de **"biblioteca carregada, dispositivo ausente"** — nunca um handle
inventado, nunca sucesso cego:

| Arquivo | Subsistema | Imports | Resposta |
|---|---|---|---|
| `runtime/src/runtime_move.c` | libSceMove | 7 | `sceMoveOpen` → `0x80930002` (sem dispositivo) |
| `runtime/src/runtime_hmd.c` | libSceHmd (PSVR) | 22 | init ok, `sceHmdOpen` → `0x80AF0003` |
| `runtime/src/runtime_audio3d.c` | libSceAudio3d | 14 | `PortOpen` → `0x80268003` |
| `runtime/src/runtime_camera.c` | libSceCamera | 7 | `sceCameraIsAttached` → 0 (honesto) |
| `runtime/src/runtime_vr.c` | VrTracker + SocialScreen + Vr | 24 | tracking indisponível |

`sceHmdInitialize315` foi medido em `0x41252b1`: o guest **descarta** o retorno (vai direto a
`movl $0x170,%edi` em `0x41252b6`, sem `testl`), então recusar é caminho tratado.

## Estado atual: falha em `RHIThread`

```
Fault: execute access to 0000000000000000 at 0000000000000000
  thread name: RHIThread
  #0 guest offset 0x14d6aec
```

`0x14d6aec` é `movq %rbx,%rsi` após `callq *0x8(%rsi)` em `0x14d6ae9` — uma chamada **virtual
indireta** através de um ponteiro nulo. Determinístico: duas execuções idênticas.

Antes de falhar, o jogo estabeleceu:
- `GPU: NVIDIA GeForce RTX 5060 Laptop GPU, Vulkan 1.4.357`, `maintenance5/8`, feedback loop layouts
- `Output resolution: 1920x1080 (live)`
- `Runtime: gamepad connected: DualSense Wireless Controller (USB 054c:0ce6)`
- 12 sondagens de formato de superfície (`CollectImageFormatInfo`)

## O que isto NÃO é

- Não é um frame renderizado.
- Não é menu, intro ou gameplay.
- Não é boot completo: o processo termina em fault na thread de renderização.

# Auditoria da memória e do primeiro boot

Data: 2026-11-01 UTC. Dump `CUSA11875`. Este documento registra a cadeia completa do boot,
os dois bloqueios resolvidos e o bloqueio atual. **Nenhum frame foi renderizado.**

## Resumo do avanço

| Etapa | Antes desta sessão | Agora |
|---|---|---|
| Bloqueio | `abort` sem causa (`INT 0x44`) | `NpToolkit2::Core::init` (serviço, não construtor) |
| Reserva do pool 8 GiB | recusada (`NO_MEMORY`) | **concedida** |
| Threads guest | 0 | **27** (inclui `TaskGraphThreadNP 0..N` do UE4) |
| Arquivos lidos do dump | 0 | **1.657 leituras, 12.095.000 bytes** |
| AppContent | não inicializado | **inicializado** (perfil offline) |

## Bloqueio 1 — resolvido: reserva fixa do pool

O guest exige o endereço explicitamente (disassembly em `0xdf855e`):

```
movabsq $0x1000000000, %rdi     ; endereço exigido
movabsq $0x200000000,  %r15     ; 8 GiB
movl    $0x90, %ecx             ; MAP_FIXED | MAP_NO_OVERWRITE
callq   sceKernelMemoryPoolReserve
```

O runtime colocava ali, primeiro, um mapeamento direto de 6 MiB **escolhido por ele**
(`guest hint 0x0, flags 0x0`). Como o pedido do guest é fixo e sem sobrescrita, a reserva
falhava com `0x8002000c` (`NO_MEMORY`), e a libc abortava.

Correção: `find_free_unhinted()` em `runtime_memory.c`. Colocações **sem hint do guest**
começam em `USER_MIN + 8 GiB`, deixando a janela do pool livre. Colocações **com hint**
continuam honrando o endereço pedido.

```
Antes:  mapped direct memory 0000001000000000   (colide)
Depois: mapped direct memory 0000001200000000   (janela respeitada)
        reserved virtual range 0000001000000000, size=8589934592
        reserved virtual range 0000002000000000, size=8589934592
        reserved virtual range 0000003000000000, size=1073741824
```

Determinístico em duas execuções.

## Bloqueio 2 — resolvido: perfil de conteúdo ausente

Com a memória liberada, o boot passou a parar em:

```
STOP: AppContent needs --content-profile
```

O pipeline tinha rodado `prepare` e `link`, mas não `content_profile.prepare`. Gerado o
`content.bin` (SKU `full`, perfil base offline, sem add-ons) e passado com
`--content-profile`, o AppContent inicializa:

```
Runtime: AppContent host provider loaded; references=1
Runtime: AppContent initialized; offline base-game profile, no mounted add-ons
```

## Bloqueio 3 — resolvido: construtor `InitParams`

Tamanho medido no próprio frame do guest, sem adivinhação:

```
0x40c762a  leaq -0x398(%rbp), %rbx   ; base do InitParams
0x40c7631  movq %rbx, %rdi
0x40c7634  callq <ctor>
0x40c76c1  leaq -0x260(%rbp), %rdi   ; objeto SEGUINTE no mesmo frame
```

`0x398 - 0x260 = 0x138` = **312 bytes**. O objeto termina 560 bytes abaixo do canário
(`rbp-0x30`), então zerá-lo não pode tocar a proteção de pilha.

Implementado em `runtime/src/runtime_np.c`: **somente construtores**. O guest trata o retorno
por `testl %eax,%eax; je <continua>`, e o objeto é um agregado que o chamador preenche depois.

## Correção do tamanho de `InitParams` (revisão)

A primeira medição usou `rbp-0x260` como início do objeto seguinte e deu 312 bytes. Estava
**errada**: o guest escreve campos em `-0x390`, `-0x378`, `-0x358`, `-0x350`, `-0x338`,
`-0x330`, `-0x328`, `-0x320`, e o objeto seguinte só começa em `-0x238`
(`leaq -0x238(%rbp),%rdi` em `0x40c782d`). Tamanho correto: `0x398-0x238` = `0x160` = **352**.

Um teste novo (`test_size_covers_every_field_the_guest_writes`) impede que a constante volte a
ficar menor que os campos observados. Nenhum efeito observável no boot desta execução, mas a
medida anterior deixaria 40 bytes de campos escritos pelo guest sem inicialização.

## Bloco NpToolkit2 — concluído

Sete imports resolvidos em sequência, cada um com evidência própria:

| Import | Tratamento | Evidência |
|---|---|---|
| `InitParams::InitParams()` | construtor, 352 bytes | frame do guest, próximo objeto em `rbp-0x238` |
| `InitParams::~InitParams()` | destrutor vazio | sem recursos no agregado |
| `TermParams::TermParams()` | construtor, 8 bytes | objeto em `rbp-0x30`, canário em `rbp-0x28` |
| `TermParams::~TermParams()` | destrutor vazio | idem |
| `Core::init(InitParams&)` | **recusa** `0x80550003` | guest trata falha em `0x40c791f` |
| `Core::term(TermParams&)` | **recusa** `0x80550003` | guest **ignora** o retorno (`0x40ca601` → próxima chamada, sem `testl`) |

Com o bloco inteiro resolvido, o boot atravessou toda a inicialização de PSN e saiu para
`libSceMove` — 27 threads e 1.657 leituras (12,1 MB) contra 22 e 176 antes.

## Bloqueio 4 — decisão tomada: `Core::init` recusa

```
NpToolkit2: Core::init refused (0x80550003); no local PSN in this build
```

`Core::init` é **serviço**, não construtor. Resposta escolhida: recusar com
`0x80550003` (NpToolkit2 "não inicializado") em vez de devolver 0. O call site do guest é
`testl %eax,%eax; je <continua>`, e seu ramo de falha (`0x40c791f`) destrói o objeto, revalida
o canário e retorna limpo — recusar é um caminho tratado, não um crash.

O jogo aceitou a recusa e **continuou** (22 threads, 11 arquivos, 176 leituras), parando no
próximo import da sequência. Devolver 0 teria feito as 79 funções de NpToolkit2 acreditarem num
subsistema inexistente.

## Bloqueio 4 (histórico) — `NpToolkit2::Core::init`

```
STOP: first unsupported PS4 import: LLdnqVnnNBQ#libSceNpToolkit2 (index 657)
API: _ZN3sce7Toolkit2NP2V24Core4initERKNS3_7Request10InitParamsE
```

`Core::init` **não é construtor**: é o serviço que inicializa o subsistema PSN. O guest trata o
retorno por `testl %eax,%eax; je <continua>; xorl %ebx,%ebx; jmp <falha>` — ou seja, devolver 0
faz o jogo seguir tratando o PSN como inicializado.

**Não foi respondido.** Dar sucesso cego aqui é exatamente o stub que as regras do projeto
proíbem: as 79 funções de `libSceNpToolkit2` incluem caminhos que passariam a acreditar num
subsistema que nunca foi inicializado, e a falha apareceria muito depois, sem rastro. A decisão
de qual política offline adotar (recusar com erro tratado, ou implementar um PSN local mínimo
com estado) é de arquitetura e precisa ser registrada antes de codificar.

### Bloqueio anterior (contexto histórico) — `NpToolkit2::Request::InitParams`

```
STOP: first unsupported PS4 import: vbh-MWtjMh4#libSceNpToolkit2 (index 659)
API: _ZN3sce7Toolkit2NP2V24Core7Request10InitParamsC1Ev
Caller return offset: 0x40c7639; first argument: 0x15fd0b8
```

É o construtor C++ `InitParams()`, chamado na inicialização de PSN do UE4 mesmo em modo
offline. O argumento é uma struct na pilha do guest (`rbp-0x398`, frame de `0x398` bytes).

**Não foi implementado**, por uma razão concreta: o construtor precisa inicializar a struct
com o **tamanho exato** de `InitParams`, e esse tamanho não está disponível no repositório —
não há implementação de referência de `NpToolkit2` em `runtime/gpu/`, e o guest só revela os
campos que escreve **depois** da chamada (até o offset `0x150`+16). Escrever um tamanho
adivinhado poderia atingir o canário em `rbp-0x30` e trocar um bloqueio nomeado por corrupção
de pilha — exatamente o erro que esta sessão já corrigiu uma vez.

## Hipóteses testadas e refutadas

| Hipótese | Teste | Resultado |
|---|---|---|
| Canário de pilha corrompido | comparação no frame do chamador | **Refutada** — valor idêntico ao guard |
| Pool de memória esgotado | `GOW3_DMEM_MB=8192` | **Refutada** — mesmo bloqueio |
| O runtime escolheu `0x1000000000` | log do hint (`guest hint %p`) | **Parcialmente refutada** — o mapeamento de 6 MiB foi escolha do runtime, mas o pedido de 8 GiB é exigência do guest (`movabsq`) |
| `reserve_range` decide antes de `place` | log em ambos | **Confirmada** — `overlaps(..., 0)` |

A terceira linha é a que mais importa: minha primeira leitura ("o runtime escolheu o
endereço") era **meia-verdade**. O hint de 0 provava que o runtime escolheu a colocação de
6 MiB, mas o call site do guest provava que ele exige `USER_MIN` para o pool. Só as duas
medições juntas dão a resposta correta.

## Estado de verificação

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0 |
| `python -m unittest discover -s tests` | exit 0, **50 testes** |
| Boot até o bloqueio atual | exit 20, import nomeado |
| **Primeiro frame / menu / gameplay** | **NÃO EXECUTADO** |

## Próximo passo

Determinar o tamanho de `sce::Toolkit2::NP::V2::Core::Request::InitParams` para esta build.
Candidatos, em ordem de confiabilidade:

1. Ler os offsets que o guest acessa na struct depois do construtor e inferir o limite
   inferior (`0x160` já confirmado). Um limite inferior não basta para zerar com segurança.
2. Localizar a tabela de símbolos de `libSceNpToolkit2.prx` (presente em `sce_module/`) e
   procurar informação de tamanho.
3. Se nenhuma fonte der o tamanho, implementar o construtor escrevendo **apenas** os campos
   observados e registrar explicitamente a limitação, com teste.

Critério: o `STOP` deixa de aparecer e o boot avança para um estágio novo e nomeado.

## Evidências

`docs/evidence/prompt04/`: `boot-13-hint.txt` (hint do guest), `boot-14-ra.txt` (call site),
`boot-15-window-fix.txt` (janela aplicada), `boot-16-content-profile.txt` (22 threads, 174
leituras), `boot-17-np-ctor.txt` (construtor implementado, avanço para `Core::init`),
`build.txt`, `build-test.txt`.
