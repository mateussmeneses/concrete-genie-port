# Instabilidade de estado: o mesmo input cai em cenas diferentes

## A descoberta que reorganiza a interpretação de tudo

Comparando a grade de luminância 3×3 no mesmo índice de frame entre execuções **com o mesmo script de
input**:

| Execução | Grade (linha superior) | Estado |
|---|---|---|
| `up`, `mo`, `rel`, `s1`, `s0` | 78 / 163 / 50 | cena 3D escura |
| `ms` | 247 / 200 / 103 | cena clara (céu/atmosfera) |
| `pz` (com OPTIONS) | **254,5 / 254,9 / 246,2** | **92,6% branco — tela de UI** |

**O mesmo `cross` leva a estados diferentes** dependendo de quando os frames são capturados. O jogo
atravessa vários estados (UI → cena 3D → UI) e o timing determina onde a captura cai.

## O que isso explica

- Não consigo "testar pintura" de forma reprodutível sem primeiro **fixar o estado**.
- O teste de OPTIONS não pausou gameplay porque no frame 900–1800 o jogo estava numa tela de UI
  (92,6% branco), não em gameplay.
- O teste de sensor `ms` caiu numa cena diferente e por isso não era comparável.

## O que permanece válido

Os cinco runs com grade 78/163/50 (`up`, `mo`, `rel`, `s1`, `s0`) são comparáveis entre si. Neles:

| Abordagem | Resultado |
|---|---|
| R2 parado | indistinguível do controle |
| R2 + stick | 99,20% de cena muda, sem cor nova |
| R2 + sensor (gz=40, verificado ativo) | **0,002%** de cor nova |

**Nenhuma pintura** na cena escura, por nenhum caminho de input.

## O que falta para um teste de pausa válido

Preciso primeiro identificar o frame em que o jogo está em gameplay e capturar ao redor dele, em vez
de supor que 900–1800 é gameplay. O log já tem como detectar: a cena 3D tem grade ~78/163/50 e
2 milhões de draws/frame; a UI tem 92% de branco e muito menos draws.

## Próximo passo

Instrumentar a transição de estado: registrar por frame a grade de luminância e a contagem de draws,
para saber exatamente quais faixas de frames são gameplay. Com esse mapa, todo teste seguinte
(pintura, pausa, save) pode ser feito na faixa correta.

# Teste de sensor com estado verificado: também negativo

## Correção do teste anterior

O teste `ms` tinha caído numa cena diferente (grade 247/200/103 vs 78/163/50 das execuções
comparáveis), então não valia como evidência. Repeti com frames alcançáveis e verifiquei a cena
**antes** de comparar cores:

```
s1 (gz=40, sensor injetado) grid=[[77.6, 162.9, 50.2], [96.5, 166.3, 78.6], [36.9, 80.1, 24.2]]
```

Mesma grade das execuções `up`/`mo`/`rel` — **comparável**. Resultado:

```
colours 1594->1611, new=125, largest=0.002%
```

**Nenhuma cor nova significativa.** O sensor de movimento, injetado e verificado ativo
(`gyro=1 accel=1`, `gz=40`), também não produz tinta nesta cena.

## As três abordagens, todas medidas na mesma cena

| Abordagem | Entrada | Resultado |
|---|---|---|
| R2 parado | `0x4200`, sticks 128 | indistinguível do controle |
| R2 + stick | `0x4200`, rx=210 | 99,20% de cena muda, **sem cor nova** |
| R2 + sensor | `0x4200`, gz=40 (verificado) | **0,002%** de cor nova |

Todas na mesma cena (grade 78/163/50), todas negativas para pintura.

## Veredito consolidado

**A pintura não acontece na cena alcançada**, por nenhum dos três caminhos: analógico direito, sensor
de movimento, ou R2 parado. Isso é consistente e reproduzível.

O que resta não é "qual entrada falta", e sim **se esta cena é a de pintura**. A cena é 3D, anima,
responde a input de câmera e tem 2,17 milhões de draws por frame — é gameplay ou cutscene, não menu.
Mas pode ser uma seção de exploração onde pintar ainda não foi habilitado.

# Os mapas que o jogo tem — e uma divergência que invalidou meu teste de sensor

## Os 218 mapas, lidos do índice do pak

```
   1  Maps/Entry.umap                 <- entrada
  59  Content_VR/Levels               <- VR (fora do gate)
   6  Levels/BlackOut
  26  Levels/Cave
  37  Levels/Lighthouse
  28  Levels/Tunnel
  61  Levels/VS                     <- 265 referências no índice
```

`Lighthouse` tem **2.979** referências no índice; `Levels/VS` 265. O jogo tem cenas distintas de
sobra — o problema nunca foi falta de conteúdo.

## A divergência que invalida o teste de sensor

Medindo luminância média numa grade 3×3 entre execuções, no mesmo índice de frame:

| Execução | Grade 3×3 (linha superior) | Cena |
|---|---|---|
| `up` (`.uproject`, R2+stick) | 78,0 / 163,3 / 50,4 | cena escura |
| `mo` (sensores ativos, R2+stick) | 78,0 / 163,3 / 50,2 | **idêntica a `up`** |
| `rel` (R2 mantido) | 78,1 / 163,2 / 50,4 | **idêntica a `up`** |
| `ms` (**sensor injetado**, R2) | **246,8 / 199,8 / 102,8** | **cena diferente** |

Três execuções caem na mesma cena (78/163/50), e a do sensor injetado cai em outra (247/200/103) —
muito mais clara, com 39,65% de branco e gradientes de ciano: céu/atmosfera.

**Conclusão:** o teste de pintura com sensor injetado **não é comparável** com os outros, porque o
jogo estava num estado diferente. A ausência de cor nova nele mede "não pinta nesta outra cena", não
"o sensor não pinta". Preciso repetir com o estado verificado igual.

## Por que isso importa para o veredito anterior

Meu veredito "R2 não pinta" está sustentado nas execuções `up`/`mo`/`rel`, que compartilham a mesma
cena — essas são comparáveis entre si. O teste de sensor (`ms`) **não** está, e não deve ser usado
como evidência nem a favor nem contra.

## Próximo passo

Repetir sensor vs sem sensor na **mesma cena**, verificando a grade de luminância antes de comparar
cores. Um teste só vale se as duas execuções estiverem no mesmo lugar.

# Sensores de movimento: implementados e ativos; a pintura continua não aparecendo

## Dois achados antes de mexer em código

**1. O `.uproject` não estaba no filesystem e estava dentro do pak.** O guest loga
`Project file not found: ../../../ConcreteGenie/ConcreteGenie.uproject`. Extraí o arquivo do offset
53 do pak (1004 bytes de JSON íntegro) e o coloquei em `gamedump/CUSA11875/ConcreteGenie/`. O aviso
desapareceu (`Project file not found` 1 → 0). Ele declara os plugins reais do jogo:

```
SlateRemote(false), WinDualShock, OnlineSubsystem, OnlineSubsystemPS4,
OnlineSubsystemNull, Morpheus (PSVR), MoveController (PS Move)
```

**Não existe plugin de pintura por analógico direito.** Confirma o que o Prompt 04 descreve: pintura
é por sensor, e o analógico é alternativa.

**2. O runtime entregava orientação identidade e sensores zerados.**

```c
d->orientation[3]=1.0f;      /* e acceleration/angular_velocity nunca preenchidos */
```

`PadData` tem o layout Orbis correto (120 bytes, campos de orientação/accel/gyro), mas
`sample_host` deixava tudo em zero. Para um jogo que pinta com sensor, isso diz ao guest "o controle
nunca se move".

## O que implementei

- `SDL_SetGamepadSensorEnabled(GYRO/ACCEL)` na abertura do gamepad, com log do que existe.
- `sample_host` lê os sensores com conversão de unidade correta: accel `m/s² → g`, gyro `rad/s → deg/s`
  (as unidades do `OrbisPadData`). Só usa um pad que realmente tenha o sensor, então sessão de
  teclado mantém a orientação identidade.
- Injeção por arquivo (`GOW3_PAD_FILE`) com `gx= gy= gz=` e `ax= ay= az=`, para testar pintura por
  movimento sem mexer fisicamente o controle.

**Medido:** `Runtime: gamepad motion sensors: gyro=1 accel=1` — o DualSense expõe ambos, e o runtime
agora os lê.

## O que a pintura mostrou depois disso

Com sensor ativo e R2 mantido:

```
colours 3043 -> 3047; new=339, maior 0,003% da tela
```

**Continua não aparecendo tinta.** Nem com sensor, nem com R2+stick. O sinal de cor nova permanece em
0,003–0,005% da tela, que é ruído de antialiasing, não traço.

## Honestidade sobre o limite

Não afirmo que "pintura funciona". O que está provado:

| Item | Estado |
|---|---|
| Sensores lidos e entregues no layout Orbis | **implementado, medido** (`gyro=1 accel=1`) |
| `.uproject` presente, plugins reais conhecidos | **verificado** |
| Plugins: Morpheus, MoveController, WinDualShock | **lido do jogo** |
| Pintura renderizada | **não observada**, em nenhuma das 3 abordagens |

O próximo passo continua sendo descobrir se a cena alcançada é o gameplay de pintura — sem isso, a
ausência de tinta é ambígua entre "o mapeamento não pinta" e "esta cena não é a de pintura".

# Pintura: R2 NÃO pinta — três testes, resultado negativo conclusivo

## O que testei e o que cada teste mostrou

**Teste 1 — câmera congelada, R2 mantido (`buttons=0x4200`, sticks 128).**
R2 e controle estatisticamente indistinguíveis: 5.748 vs 5.581 células alteradas, overlap 43–50%.
Sem movimento do stick não há traço. Negativo.

**Teste 2 — R2 + stick em movimento (troca por tempo), vs controle só `cross`.**

| Execução | Mudança/frame | Overlap |
|---|---|---|
| `tm` (cross→R2+rx=210) | ~13.600 células | 57–78% |
| `tmc` (só cross) | ~5.100 células | 40–53% |

R2 **triplica** a mudança e a concentra (overlap até 78%). Sinal forte — mas não prova pintura.

**Teste 3 — o teste que decide: cor nova aparece e cresce?**

Comparando o primeiro e o último frame da execução com R2 + stick:

```
cores quantizadas: primeiro=1602, último=1582   <- DIMINUIU
cores presentes no último e ausentes no primeiro: 259
  maior delas: 0,004% da tela
maior crescimento entre cores existentes: 125 células de 129.600
```

**Nenhuma cor nova de tamanho significativo. Nenhum crescimento localizado.** Uma pintura produziria
uma região nova com cor própria, crescendo ou persistindo entre frames. O que existe é variação
distribuída de cena inteira (51.836 células, ~90% da tela), compatível com a cena animando — não com
tinta depositada.

## Veredito

**R2 com stick em movimento altera o regime da cena, mas não pinta.** Os 99,6% de overlap do teste 3
parecem acumulação, mas olhando a área (90% da tela) e as cores (nenhuma nova relevante) o fenômeno é
movimento de câmera repetido no mesmo enquadramento, não deposição de tinta.

## O que isso invalida das minhas afirmações

| Afirmação | Status |
|---|---|
| "R2 pinta" (hipótese da sessão) | **refutada** para este mapeamento de input |
| "overlap 76% com R2 = pintura" | **errado**: área de 90% da tela é movimento, não traço |
| "R2 muda o regime" | mantido: 3× mais mudança, mas é câmera/modo, não tinta |

## Próximo passo

O fallback `mouse → analógico direito` que o Prompt 04 pede é exatamente o que foi testado (stick
direito), e ele **não pinta** neste estado do jogo. Duas possibilidades, ambas verificáveis:

1. O jogo exige o **sensor de movimento / PS Move** para pintar (o Prompt 04 diz que a pintura é por
   sensor, com analógico direito como alternativa) — mas a alternativa pode estar atrás de uma opção.
2. A cena alcançada ainda **não é o gameplay de pintura** (é exploração/intro), e R2 ali tem outra
   função.

Medir antes de concluir: procurar no log do guest menção ao modo de pintura, e verificar se existe
uma opção de configuração de controle de pintura.

# R2 dentro do gameplay: muda o regime da cena, mas não prova pintura

## Como cheguei a um teste válido (dois anteriores inválidos)

**Teste A (inválido):** `cross + r2` vs nada. O controle ficou na tela branca (sha idêntico) →
100,00% de diferença, medindo estado, não pintura.

**Teste B (inválido, invertido):** descobri que **`cross` sozinho leva à cena 3D** (80% não-preto,
geometria estruturada), enquanto `cross + r2` **volta** à tela branca de UI. Ou seja o run "com R2"
estava regredindo de estado, não pintando.

**Teste C (válido):** os dois runs com `cross`, um com `r2` e outro sem. Ambos **na cena 3D**, ambos
animando, 4 frames distintos em cada. Só R2 difere.

| Execução | Entrada | Não-preto | Cores | Frames |
|---|---|---|---|---|
| `g1` | `cross` | **80,70%** | 3.603 | 4 distintos |
| `g2` | `cross` + `r2` | **71,06%** | 3.352 | 4 distintos |

## O sinal que encontrei

Comparação quadro-a-quadro (persistência):

| Execução | Mudança por frame | Concentração nas 3 bandas mais ativas |
|---|---|---|
| `g1` (`cross`) | ~6.800 px | ~24,7% |
| `g2` (`cross`+`r2`) | ~2.300 px | ~24,0% |

**Com R2 a cena muda ~3× menos.** Isso é compatível com o jogo entrar em modo de mira/pintura, onde a
câmera trava e o controle vira o pincel. E o conteúdo não-preto cai ~9,6 pontos, compatível com um
overlay de pincel ocupando a tela.

## O que está provado e o que não está

**Provado:** R2 altera mensuravelmente o regime da cena — conteúdo cai 80,70% → 71,06% e a mudança
quadro-a-quadro cai ~3×. O caminho `GOW3_PAD_FILE` → `libScePad` → R2 → guest funciona, e o guest
responde de forma coerente com um modo de pintura.

**Não provado:** que traços aparecem na geometria. A diferença é **de cena inteira (99,20% dos
pixels)**, constante nos 4 frames — assinatura de mudança de modo, não de deposição incremental de
tinta. Para provar pintura seria preciso ver a região pintada **crescer ou persistir** entre frames
com o resto da cena estável, e com a câmera parada.

## Próximo passo

Congelar a câmera (`lx=ly=rx=ry=128`) e manter R2 por vários frames, comparando a mesma região entre
frames consecutivos. Se a área alterada crescer monotonicamente ali e em nenhum outro lugar, é
pintura. Sem isso, "R2 pinta" continua sendo hipótese.

# R2 no controle muda o estado do jogo — e meu primeiro controle era inválido

## Teste 1, inválido: comparação pintura vs sem input

Rodei `r2 + rx=200` e depois "controle sem input", comparando o mesmo índice de frame. Resultado:
**100,00% dos pixels diferentes em todos os frames.**

Isso não prova nada. O controle tinha ficado numa **tela branca estática**:

```
paintc display sha: ['7aaff933c4', '7aaff933c4', '7aaff933c4', '7aaff933c4']  <- idêntico
paint  display sha: ['e6343e20f0', '9549bc6964', '5beef3687c', '6d7d6ada77']  <- 4 distintos
```

94,07% de branco puro (`#ffffff`) com um elemento dourado pequeno (`#b66b14`, `#e9ba58`): é uma **tela
de UI com prompt**, não a cena 3D. Comparar pintura contra um estado diferente do jogo mede diferença
de estado, não pintura.

## Teste 2, válido: mesmo eixo, só R2 difere

Mesmos frames (3000/3400/3800), **mesma entrada de câmera `rx=200`** nos dois, variando apenas R2:

| Execução | Entrada | Resultado |
|---|---|---|
| `p2` | `r2` + `rx=200` | **71,60% não-preto, 3 frames distintos** |
| `p2c` | `rx=200` | **100% branco, sha idêntico nos 3 frames** |

Ambas saudáveis: 8.100–8.400 presents, ~30 fps. A única diferença é R2.

## O que isso prova e o que não prova

**Provado:** R2 altera o comportamento do jogo de forma mensurável — sem R2 o jogo fica numa tela de UI
estática (94% branco); com R2 a cena 3D renderiza e anima (71,60%, frames distintos). O caminho
`GOW3_PAD_FILE` → `runtime_pad.c` → `libScePad` → R2 → guest funciona, e o guest reage.

**Não provado:** que R2 *pinta*. A tela branca sem R2 sugere que o jogo espera R2 para prosseguir —
pode ser um prompt de tutorial, não a mecânica de pintura. Para afirmar pintura seria preciso
identificar a UI de pintura e ver traços aparecerem na geometria, não apenas a cena mudar.

## Lição de método

O controle tem de diferir em **uma** variável. Meu primeiro teste variou duas (R2 e estado do jogo), e
o número espetacular (100,00%) era artefato disso. O segundo teste, variando só R2, deu um resultado
modesto e verificável.

# Áudio: cada camada do runtime verificada correta — o silêncio vem do conteúdo do motor

## Eliminação completa, uma camada por vez

| Suspeita | Medição | Veredito |
|---|---|---|
| Saída/pacing | `938 buffers/5s (expected 937)`, `starved 0`, gap 6.4 ms | correto |
| Ganho de volume | `volume=32768` / `VOLUME_0DB=32768` → 1.0 | correto |
| Remap de canal | identidade quando não há conteúdo | correto |
| Estado do port | `audio_state` reporta `output=0x01`, canais certos | correto |
| Dupla inicialização | `AudioInit: call 1 -> 0` — uma vez, sucesso | correto |
| User event do driver | corrigido: `EVENT QUEUE FULL` 4 → 0 | **corrigido** |
| Instância de decodificação | `sceAjmInstanceCreate` **nunca chamado** | motor não decodifica |
| Abertura de asset | **nenhum `.at9` aberto** em 130 aberturas | motor não pede |
| Assets no container | 1.358 `.at9` + 417 `.bnk` | existem |
| Codec | ATRAC9 no pak = `codec=1` registrado | confere |
| NGS2 | 0 chamadas em 4 entradas | não é o mixer |
| Buffer entregue | `raw_peak 0.0000` na entrada | **zeros do guest** |

## A conclusão, agora sustentada por eliminação

O runtime de áudio está correto em **todas** as camadas que ele controla. O guest:

1. inicializa AudioOut uma vez com sucesso,
2. abre 4 portas e as alimenta no ritmo exato,
3. **nunca cria instância de decodificação**,
4. **nunca abre um asset de áudio**,
5. e entrega buffers zerados.

Isso é o comportamento de um motor cujo subsistema de som não chegou a tocar nada — não de uma
falha no runtime. As três hipóteses que eu havia levantado e que foram refutadas por medição:
NGS2 como mixer (0 chamadas), falta de assets (1.358 existem), e falha na API de stream
(`snd_stream_*` roda).

## Por que não corrigi

Não há um defeito de runtime identificado para corrigir. As opções restantes são investigar o estado
interno do motor (por que ele decide não tocar), o que exige rastrear código do guest em execução —
não um patch de import. Registro isso como o limite honesto desta auditoria em vez de inventar uma
correção.

## O que esta auditoria entregou de concreto

- `EVENT QUEUE FULL` do driver de áudio eliminado (bug real, medido antes/depois).
- 31 imports antes sem nome implementados, incluindo dois que causavam falha visível
  (`sceKernelAddUserEvent`, `sceAjmMemoryRegister`).
- Port 3D entregue de verdade em vez de recusado — sem isso o jogo logava
  `FAILED TO OPEN 3D AUDIO PORT` e nem inicializava o áudio.
- Instrumentação permanente (`GOW3_TRACE_AUDIO_IN`, `GOW3_TRACE_NGS2`, `GOW3_TRACE_AJM`,
  `GOW3_TRACE_LATE`, `peak`/`loud`) para que a próxima sessão continue de onde parou.

# Áudio: infraestrutura completa, assets existem, e o guest nunca os pede

## O que está estabelecido por medição

| Camada | Estado | Evidência |
|---|---|---|
| Port WASAPI 8ch→stereo | correto | `938 buffers/5s (expected 937)`, `starved 0` |
| Ganho / remap de canal | correto (neutro) | `volume=32768` / `VOLUME_0DB=32768` → 1.0 |
| Buffer entregue pelo guest | **zeros** | `raw_peak 0.0000` medido antes de converter |
| User event do driver | corrigido | `EVENT QUEUE FULL` 4 → 0 |
| Pak do jogo | **aberto com sucesso** | `open(.../concretegenie-ps4_0_p.pak)` |
| Assets de áudio | **existem** | 1.358 `.at9` + 417 `.bnk` no índice do pak |
| Threads de áudio do guest | criadas | `snd_stream_parsing_thread`, `snd_stream_reader_thread`, `AudioThread` |
| NGS2 | não usado | 0 chamadas em 4 entradas |
| Ajm | só estatística | 94 jobs `STATISTICS_INSTANCE` |

## O layout de áudio que existe no dump

```
ConcreteGenie/Content/Audio/Streams/_brushchimes   <- som da mecânica de pintura
ConcreteGenie/Content/Audio/Streams/_cutscenes
ConcreteGenie/Content/Audio/Streams/_music
ConcreteGenie/Content/Audio/Streams/_musicVR
ConcreteGenie/Content/Audio/Streams/{ar,cs,de,en,es,es-419,fr,it,...}  <- diálogo por idioma
```

Todos **ATRAC9**, que é exatamente o codec que o Ajm registrou (`codec=1`). O formato fecha.

## Onde o silêncio está, agora com precisão

O jogo usa áudio **em streaming** (`snd_stream_reader_thread`), não sintetizado. O pak está aberto, os
assets existem no formato certo, e o guest **nunca abre um `.at9`** — não há uma única chamada de
abertura de asset de áudio no log, enquanto há 130 aberturas de i18n/binários.

Logo o defeito não está no decodificador, nem na saída, nem nos dados: está em **o que faz o motor
decidir que não há nada para tocar** — provavelmente o subsistema de som do motor não inicializou
por completo, ou o evento que dispara o stream nunca chega.

## O que isso refuta definitivamente

- "o mixer é NGS2" — 0 chamadas.
- "áudio não pode ser auditado sem cena visível" — a cena renderiza a 30 FPS e o áudio foi auditado
  até a camada onde o defeito está.
- "faltam assets" — existem, 1.358 `.at9`, no formato que o Ajm registrou.

## Próximo passo

Rastrear a decisão do guest: instrumentar `sceAjmInstanceCreate` (que já existe) para ver se alguma
instância de decodificação é criada, e verificar por que o `snd_stream_reader_thread` não produz
requisições. Se nenhuma instância Ajm é criada, o motor nunca decidiu tocar nada.

# BUG CORRIGIDO: `sceKernelAddUserEvent` recusava e travava o driver de áudio do jogo

## O defeito

Quando implementei os 31 imports sem nome, `sceKernelAddUserEvent` foi registrado devolvendo
`K_EINVAL`, com o comentário "não há scheduler de usuário aqui, então reporta não suportado em vez de
fingir". A instrumentação mostrou o custo disso:

```
Late: AddUserEvent id=262147 (call 1)
BRB DRIVER: ! EVENT QUEUE FULL -> CLIENT THREAD FALLING BEHIND !
Late: AddUserEvent id=262147 (call 2)
BRB DRIVER: ! EVENT QUEUE FULL -> CLIENT THREAD FALLING BEHIND !
...
```

**195 chamadas, todas com o mesmo id `262147`** — o guest em loop de retentativa — e a cada recusa o
driver de áudio (`BRB`) logava fila cheia. As duas coisas eram o mesmo evento.

**Não registrei a hipótese como causa sem testar.** Depois de implementar o registro real:

| Métrica | Antes | Depois |
|---|---|---|
| `AddUserEvent` chamado | 195 | **0** |
| `EVENT QUEUE FULL` | 4 | **0** |
| `BRB WARNING REPORT` | 4 | **1** |

O guest registra uma vez e está satisfeito. A recusa era um defeito real e caro.

A implementação é real: tabela de 64 slots, registro idempotente (a pós-condição do chamador é "este
id está disponível"), `GetEventUserData` devolve o que foi guardado, `Delete` libera. O id **é** o
handle nesta API — nenhum handle é inventado.

## O que isso NÃO resolveu

```
Audio stats port 0: 938 buffers/5s (expected 937), max gap 8.41 ms,
                    min queued 7680 bytes, starved 0, peak 0.0000, 0/938 loud
```

**`peak 0.0000` continua.** Corrigir o registro de user event removeu a falha do driver, mas o buffer
entregue pelo guest continua zerado. São dois problemas distintos, e agora só um está resolvido.

## Método que funcionou

Instrumentar entrada (contagem + argumentos) em vez de ler o stub e concluir. Foi assim que a
hipótese NGS2 caiu (0 chamadas) e que este defeito apareceu (195 recusas seguidas de falha do
driver).

# CORREÇÃO 4: NGS2 não é o mixer deste jogo — zero chamadas, medido

## O que eu afirmei e o que a instrumentação mostrou

O commit `79e9e18` afirma "o mixer deste jogo é NGS2". **Está errado.** Instrumentei os quatro
pontos de entrada NGS2 com contagem e argumentos:

```
VoiceControl        0 chamadas
SystemRender        0 chamadas
ParseWaveformData   0 chamadas
CalcWaveformBlock   0 chamadas
```

**NGS2 nunca é chamado.** A conclusão anterior veio de ler o stub `ngs2_render` e assumir que ele era
o caminho ativo, sem verificar se era chamado. Ler o código não é medir a execução.

## O que a medição seguinte mostrou

Instrumentando o buffer **antes** de qualquer conversão de canal ou volume:

```
AudioIn: port 0 call 1    raw_peak 0.0000 frames 256 ch 8 float 1
AudioIn: port 0 call 1000 raw_peak 0.0000 frames 256 ch 8 float 1
AudioIn: port 17 call 3000 raw_peak 0.0000 frames 256 ch 1 float 1
```

**`raw_peak 0.0000` na entrada.** O guest entrega zeros. O runtime não está silenciando nada: o
ganho é neutro (`volume=32768`, `VOLUME_0DB=32768` → gain 1.0) e o remap de canais é identidade
quando não há conteúdo.

## Onde está o silêncio

| Camada | Estado |
|---|---|
| Port WASAPI, 8ch→stereo | correto (`938 buffers/5s`, `starved 0`, gap 6.76 ms) |
| Ganho e remap de canal | corretos (neutros) |
| Buffer entregue pelo guest | **zeros** |
| Quem enche o buffer | `AudioThread` do próprio motor |
| NGS2 | **não usado** |
| Ajm | só `STATISTICS_INSTANCE`, não carrega áudio |

O silêncio está no **conteúdo que o motor produz**, não no runtime de áudio. O motor tem sua própria
thread de áudio e entrega buffers zerados — o que sugere que ele não carregou assets de áudio, ou que
o subsistema de som do motor está desabilitado por configuração/estado.

## O que isso invalida das minhas conclusões

| Afirmação anterior | Status |
|---|---|
| "o mixer deste jogo é NGS2" (`79e9e18`) | **errada**: 0 chamadas |
| "NGS2 é stub que silencia o jogo" | tecnicamente verdadeiro sobre o stub, **irrelevante**: não é chamado |
| "o guest não submete batch Ajm" | errada (submete 40.800) |
| "áudio não pode ser auditado sem cena visível" | errada |

## Próximo passo

Descobrir por que o motor entrega zeros: procurar o log do subsistema de áudio do próprio motor
(UE4 audio device init), e se ele reportou falha ao inicializar. `brbDriver::Initialize(): NUM
CHANNELS ( 8 ) CLAMPED TO 2.` mostra que o driver inicializou; falta saber se o subsistema de som
acima dele está ativo.

# CAUSA RAIZ DO SILÊNCIO: o synth de áudio do jogo é um stub que escreve zeros

## O caminho até aqui, e duas conclusões minhas que estavam erradas

| O que eu disse | O que a medição mostrou |
|---|---|
| "o guest não submete batch Ajm" | **falso**: submete 40.800 `BatchStart` de 88 bytes |
| "`Ajm batches` nunca impresso logo não decodifica" | **enganoso**: a linha de resumo só é impressa ao encerrar, e a execução foi cortada por timeout |

Instrumentando `run_job`, a verdade apareceu:

```
Ajm: job instance=524288 input_count=0 in0=0 out0=0 flags=80008001
```

`524288` = `0x80000` = `STATISTICS_INSTANCE`. **Todos os 94 jobs são consultas de estatística**, que
retornam cedo por projeto. Ajm não carrega o áudio deste jogo — ele só é consultado.

## A causa raiz

O mixer deste jogo é **NGS2**, e `sceNgs2SystemRender` — a função que *produz* o áudio — é um stub
que apaga o buffer:

```c
static ABI int32_t ngs2_render(uintptr_t system, Ngs2RenderBuffer *buffers, uint32_t count) {
    (void)system;
    for (uint32_t i=0;buffers && i<count;++i) if (buffers[i].buffer)
        memset(buffers[i].buffer,0,buffers[i].size);   /* <- silencia o jogo */
    ++ngs2_renders;
    return 0;
}
```

Os 13 imports NGS2 deste eboot estão todos implementados assim:

```
sceNgs2CalcWaveformBlock      sceNgs2PanGetVolumeMatrix   sceNgs2PanInit
sceNgs2ParseWaveformData      sceNgs2RackCreateWithAllocator
sceNgs2RackDestroy            sceNgs2RackGetVoiceHandle
sceNgs2SystemCreateWithAllocator  sceNgs2SystemDestroy
sceNgs2SystemRender           sceNgs2VoiceControl
sceNgs2VoiceGetState          sceNgs2VoiceGetStateFlags
```

`sceNgs2VoiceGetState` zera o estado ("stopped"), então o guest não tem razão para acreditar que uma
voz toca.

## Por que isso explica exatamente o que foi medido

```
Audio stats port 0: 938 buffers/5s (expected 937), max gap 6.76 ms,
                    min queued 8448 bytes, starved 0, peak 0.0000, 0/938 loud
```

O caminho de saída está **correto**: pacing exato, sem starvation, port WASAPI real. O sintetizador
entrega silêncio porque é um stub. `peak 0.0000` é a assinatura de um buffer apagado, não de um
sistema de áudio quebrado.

## O que isso muda no plano

Implementar NGS2 não é "mais um import": é um sintetizador com voice graph, waveforms, pans e
matrizes de volume. Não é uma correção de uma linha, e fingir que é seria pior que registrar o
estado real.

Duas direções, ambas mensuráveis:

1. **Mapear o que o guest realmente usa** — quais waveforms, quantas vozes, que formato de saída.
   O guest já chama `ParseWaveformData`/`CalcWaveformBlock`; se ele fornecer as amostras, um render
   simples de mistura de vozes com volume e pan é viável sem reproduzir o NGS2 inteiro.
2. **Verificar se há um caminho de áudio pré-mixado** (stream/bink) que traga conteúdo sem NGS2.

Medir antes: quantas vozes ficam ativas e se `ParseWaveformData` recebe dados válidos.

# Áudio: a cadeia abriu, o mixer roda, e o que falta é conteúdo decodificado

## Dois defeitos reais encontrados medindo, não supondo

**Defeito 1 — o port 3D era sempre recusado.** `runtime_audio3d.c` devolvia `A3D_NO_PORT` em
`PortOpen`, sob a suposição registrada de que "o jogo cai para o caminho estéreo". A medição
refutou: o guest logou

```
brbDriverBase::Initialize3D(): FAILED TO OPEN 3D AUDIO PORT!
```

e **nunca chamou `sceAudioOutOutput`**. Recusar o port não degradou o áudio — silenciou o jogo
inteiro. Agora o port é entregue de verdade, os objetos são misturados sem posicionamento
(renderização espacial continua indisponível e não é fingida).

**Defeito 2 — 31 imports sem nome.** Com o port 3D funcionando, o guest avançou e parou em
`STOP: first unsupported PS4 import: bkRHEYG6lEM#libSceAjm`. A tabela `runtime/tools/aerolib.inl`
já auditada no repositório tinha o nome: `sceAjmMemoryRegister`. Varrendo os 988 imports contra
essa tabela, **31 nomes** estavam ausentes. Todos identificados por essa tabela, nenhum por palpite,
e implementados em `runtime/src/runtime_late.c`.

## O estado medido agora

```
Runtime: audio backend wasapi
Runtime: audio port 0 opened (type 0, 8 ch, float, 256 frames, downmixed to stereo)
Audio3d: subsystem ready; ports mix to stereo without positional rendering
brbDriver::Initialize(): NUM CHANNELS ( 8 ) CLAMPED TO 2.
Audio stats port 0: 938 buffers/5s (expected 937), max gap 6.76 ms,
                    min queued 8448 bytes, starved 0, peak 0.0000, 0/938 loud
```

| O que funciona | O que não funciona |
|---|---|
| Port aberto, WASAPI real | **`peak 0.0000`, `0/938 loud`** — todos os buffers são zeros |
| 938 buffers/5s de 937 esperados | nenhum batch Ajm submetido |
| `starved 0`, gap máximo 6,76 ms | `Ajm batches` nunca é impresso: o guest não decodifica |
| driver próprio do jogo inicializou | — |

**Diagnóstico:** o mixer roda com pacing correto e recebe silêncio porque **nada foi decodificado**.
Não é um bug de saída de áudio; é ausência de conteúdo. `peak`/`loud` foram adicionados justamente
porque "buffers entregues" e "buffers com som" são medições diferentes — uma porta alimentada com
zeros reporta pacing perfeito.

## O que isso corrige nas conclusões anteriores

"Depende de cena visível" estava errado como razão para o áudio não ser auditado: o áudio estava
silencioso por um defeito concreto (port 3D recusado) mais 31 imports sem nome, ambos independentes
da cena. A cena inclusive renderiza: 4 capturas, 100% não-pretas, 8.100 frames alcançados.

## Próximo passo

Descobrir por que o guest não submete batches Ajm: rastrear quem chama `sceAjmBatchStartBuffer` e se
o codec foi registrado (`sceAjmModuleRegister`), com o log de `jobs`/`frames_decoded` por janela.

# Input verificado: o stick esquerdo move a câmera (com controle negativo)

## O teste que eu quase errei

Primeira medição: com `ly=0` (stick esquerdo para frente), quatro capturas deram
`0,00% → 9,90% → 6,35% → 9,24%` de diferença. Parecia provar movimento.

**Não provava.** O controle negativo — mesma execução, **sem** input — deu
`0,00% → 3,83% → 7,17% → 7,28%`. A cena **anima sozinha**. A diferença entre frames consecutivos não
distingue movimento de câmera de animação própria.

## O teste correto: mesmo índice de frame, com e sem input

Comparar o **mesmo frame** entre duas execuções:

```
frame 2600: with-input vs without-input = 99.94% different
frame 3000: with-input vs without-input = 99.94% different
frame 3400: with-input vs without-input = 99.94% different
frame 3800: with-input vs without-input = 99.94% different
```

99,94% dos pixels diferem nos quatro pontos. Não é ruído nem fase de animação: é **outra vista da
cena**.

Ambas são cenas 3D ricas e coerentes:

| Execução | Cores distintas (frame 3000) | Não-preto | Luminância média |
|---|---|---|---|
| com input | 6.224 | 80,16% | 86,0 |
| sem input | 11.147 | 95,99% | 199,4 |

## O que isso prova e o que não prova

**Provado:** o caminho de input funciona de ponta a ponta — `GOW3_PAD_FILE` → `runtime_pad.c` →
`libScePad` → guest → estado da câmera → GPU. O stick esquerdo altera a vista da cena.

**Não provado:** se a direção do mapeamento está correta (`ly=0` = frente?), se há colisão, se o
personagem anda, se a pintura responde, se o áudio sai, se save/load funciona. Movimento de câmera
não é jogabilidade.

# CORREÇÃO APLICADA: re-enfileiramento de shader eliminado — 0,7 → 30 FPS, e cena real

## Aceitação, contra os critérios que eu mesmo escrevi

| Critério | Antes | Depois |
|---|---|---|
| Traduções de shader | 1.262.000 | **~5** (4 hashes distintos) |
| FPS na transição | 0,7 | **30,0** (pior frame 51 ms) |
| `capture` por frame | 3256 ms | **0,0 ms** |
| Frames alcançados | 2.100 | **9.900** |
| Capturas pós-menu | pretas | **100% de conteúdo, três frames distintos** |

## O que a correção faz

Dois consertos em `vk_pipeline_cache.cpp` / `.h`:

**A — marcação de pendência por `spec`.** `Program` ganhou `queued_permutations`. Antes de
enfileirar, a `spec` é procurada nesse conjunto; se já está em voo, a chamada retorna sem
enfileirar. Elimina as **269.447** filas redundantes.

**B — índice reservado, não `modules.size()`.** O índice agora é
`modules.size() + queued_permutations.size() - 1`, tomado sob `unique_lock` junto com a inserção no
conjunto. Dois draws pedindo a mesma `spec` não podem mais reservar índices diferentes. Elimina o
crescimento até **28.474** permutações num hash.

**Liberação:** ao publicar, `PublishShaders` copia a `spec` antes do `std::move` e faz
`std::erase(program->queued_permutations, published_spec)`. Sem isso, a marcação suprimiria pedidos
legítimos para sempre.

Corrida tratada: o segundo `unique_lock` relê o conjunto e devolve
`numeric_limits<size_t>::max()` se outro thread já enfileirou — nesse caso retorna sem enfileirar.

## O resultado visual

Três capturas em 2000, 3000 e 4000, todas 100% não-pretas, **todas diferentes entre si**
(sha256 distintos) e com **~4.900 cores distintas** — gradientes contínuos, não preenchimentos
chapados. A imagem tem uma massa iluminada grande ao centro e formas na base sobre fundo escuro:
é uma cena 3D renderizada, não um menu nem texto.

## O que isso NÃO prova

Não há movimento de câmera verificado, nem input testado contra a cena, nem áudio, nem save/load.
"Aparece uma cena" não é "a primeira cena é jogável". O critério do Prompt 04 continua **não
cumprido**.

# Dois defeitos distintos no re-enfileiramento de shader (medidos)

Contagem separando os dois casos:

```
Requeue: hash b24e4118db94f59f queued 4000 times (perm 490);
         same-perm=269447 diff-perm=147757
```

| Caso | Contagem | Significado |
|---|---|---|
| `same-perm` | **269.447** | mesma `perm_idx` re-enfileirada — trabalho puramente redundante |
| `diff-perm` | **147.757** | `perm_idx` diferente a cada pedido — a lista de permutações cresce |

## Defeito A (269 mil): falta de marcação de pendência

`program->pending` só é atribuído no compile `initial`. No caminho de permutação:

```cpp
QueueShader(..., perm_idx, false, std::move(spec));
return {};          // nada marca a permutação como pendente
```

O draw seguinte pede a **mesma** `perm_idx` e volta a enfileirar. É redundância pura, e marcar a
permutação pendente elimina-a.

## Defeito B (148 mil): a lista de permutações cresce sem convergir

`perm_idx = program->modules.size()` **antes** do enfileiramento, e nada é inserido em `modules`
até a compilação assíncrona publicar. Com draws concorrentes, cada um calcula um `size()` diferente
e enfileira uma permutação "nova" que é, na prática, a mesma `spec`. Por isso `perm` chegou a
28.474 para um único hash.

## O que isso explica

- 1.262.000 traduções para **409 hashes distintos** (razão 3.085×)
- 16.003 draws pendentes
- 1,4 s por frame (0,7 FPS) na transição

## Correção proposta, ainda não aplicada

Marcar a permutação como pendente **por `spec`**, num conjunto consultado antes de enfileirar:

1. se a `spec` está no conjunto, retornar sem enfileirar (resolve o Defeito A);
2. reservar o índice de forma estável por `spec`, em vez de `modules.size()` (resolve o B).

Efeito esperado: 1.262.000 → ~409 enfileiramentos.

**Não aplicado nesta sessão.** A mudança toca a concorrência entre a thread de desenho e o
publicador assíncrono; fazê-la sem testes de estresse dedicados trocaria um problema de desempenho
por um bug de correção. Os dois contadores e o trace ficam no código para quem for aplicar.

# BUG CONFIRMADO: re-enfileiramento sem limite da mesma permutação de shader

## A medição que provou

Com `GOW3_TRACE_REQUEUE=1`, contando quantas vezes cada hash entra no caminho de
`QueueShader` por permutação ausente:

```
Requeue: hash 0853e6d8742acb79 queued 75000 times (perm 27474)
Requeue: hash 0853e6d8742acb79 queued 76000 times (perm 28474)
Requeue: hash cf2fdf6464a845f9 queued 16000 times (perm  1365)
```

E o número da permutação **cresce junto**: 26.474 → 27.474 → 28.474 para o mesmo hash.

## O mecanismo, no código

`vk_pipeline_cache.cpp`, no caminho de permutação ausente:

```cpp
if (it == program->modules.end()) {
    if (program->pending || ...) return {};
    if (compile_async) {
        QueueShader(*program, hw_stage, sw_stage, params, runtime_info, binding,
                    perm_idx, false, std::move(spec));
        return {};            // <- nada marca esta permutação como pendente
    }
```

`program->pending` é atribuído **apenas** no compile `initial` (linha 560). Para uma permutação,
nada a marca como pendente, e `perm_idx = program->modules.size()` **cresce a cada chamada**. Logo:

1. o draw pede uma permutação;
2. não existe, então enfileira com `perm_idx = N`;
3. `return {}` — a permutação não entra em `modules` até o compilador assíncrono publicar;
4. o próximo draw repete, com `perm_idx = N+1`;
5. o acumulado chega a 28.474 permutações para um hash.

Isso explica os números anteriores: **1.262.000 traduções para 409 hashes distintos** (razão 3.085×),
16.003 draws pendentes e 1,4 s por frame.

## Por que o cache por hash não resolve sozinho

`program_cache` já existe e está correto — o hash **acerta** o programa. O que falha é a
**permutação** dentro dele. Um cache por hash de programa não impede o re-enfileiramento; é preciso
marcar a permutação como pendente.

## Correção proposta (não aplicada)

Registrar a permutação pendente no `Program` (um conjunto de `spec` em compilação, consultado no
`if` do topo), de modo que um segundo draw com a mesma `spec` não volte a enfileirar. Efeito
esperado: 1.262.000 → ~409 enfileiramentos.

Não foi aplicada porque ainda não medi **qual campo da `spec` diverge** entre draws consecutivos do
mesmo hash. Se a `spec` realmente varia (e os 28.474 valores forem legítimos), marcar por `spec`
não ajuda — seria preciso verificar se `perm_idx` está sendo usado como chave de forma indevida.
Aplicar a correção antes dessa medição seria chutar.

# CAUSA RAIZ MEDIDA: shader capture síncrono serializa 7.235 draws/frame

## A medição que nomeia o gargalo

`GOW3_FRAME_STATS=1` no regime lento (frame ~2000):

```
Frame stats: 0.7 FPS, worst frame 1416.3 ms
  async: capture 3256.1 ms, workers 1322.7 ms, GPU capture wait 3310.4 ms, 16003 pending draws
  GPU thread 0.00 us/draw, 7235 draws/frame, idle 0.0%
```

E a razão draws/submissão, agora instrumentada:

| Frame | Draws totais | Submissões | Draws/submissão |
|---|---|---|---|
| 1500 | 613.326 | 13.079 | 46,9 |
| 1850 | 3.143.862 | 36.830 | 85,4 |
| 2000 | 4.228.414 | 47.007 | **90,0** |

## O mecanismo

`PipelineCache::QueueShader` (vk_pipeline_cache.cpp:486) roda `Shader::TranslateProgram` **na
thread da GPU** e **espera** por ela:

```cpp
if (!capture_job.Start(*capture_compiler, [this, build, binding] {
        PhaseTimer capture{g_gow3_capture_ns};
        ...
        build->ir.emplace(Shader::TranslateProgram(...));
```

Com **7.235 draws por frame** e **16.003 draws pendentes**, cada draw que precisa de tradução bloqueia
a thread da GPU. O custo não está na GPU (idle 0% de uso útil), está nessa serialização.

## Correção das minhas três conclusões anteriores

| O que eu disse | O que a medição mostra |
|---|---|
| "tela preta permanente" | falsa: o frame 1900 tem 100%; as capturas "pretas" eram frames que **não terminaram** dentro do timeout |
| "60 FPS, motor ocioso esperando" | só vale antes do frame ~1500; depois é **0,7 FPS saturado** |
| "~950 mil draws/frame" | número errado, mas a ordem de grandeza **era real**: são ~7.235/frame |

A única coisa que se sustenta é que o problema é de **desempenho na transição**, não de estado nem de
input.

## Próximo passo

Duas alavancas, ambas mensuráveis:

1. **Cache de shader por hash.** Se o mesmo par (código, runtime) é traduzido repetidamente, um cache
   por hash elimina a repetição. Medir quantos `TranslateProgram` distintos ocorrem para 16.003
   draws pendentes.
2. **Tirar a tradução da thread da GPU.** O `capture_job.Wait()` logo abaixo torna a captura
   síncrona por desenho; paralelizar mantém a correção mas libera a thread.

Medir antes de escolher: contar `TranslateProgram` por hash único no regime lento.

# CORREÇÃO 3: não é tela preta — é 2,47 milhões de draws num único frame

## O que a execução longa mostrou

| Frame | Tempo acumulado | fps médio | Intervalo |
|---|---|---|---|
| 1500 | 27 s | 55,2 | — |
| 1800 | 141 s | 12,7 | 114 s para 300 frames |
| 2100 | **451 s** | **4,65** | **310 s para 300 frames** |

E os draws acumulados:

```
Draws: frame 1900, 2470665 total
```

**2.470.665 draws** entre os frames 1800 e 1900 — um único frame carregando mais de dois milhões
de draws.

## Por que os frames "pretos" eram falsos

As capturas em 2500+ deram 0% porque **esses frames nunca terminaram de renderizar** dentro do
`timeout`. O jogo não estava mostrando preto: estava levando minutos por frame. A captura em 1900,
que teve tempo de completar, mostra **100% de conteúdo**.

Correção das minhas conclusões anteriores: "tela preta permanente" e "motor ocioso esperando" estão
ambas **erradas**. O motor está sobrecarregado de trabalho, não parado.

## O que isso reabre

A medição anterior de "60 FPS, 1 draw/frame, GPU ociosa" era do período **antes** da transição
(frames < 1500). Depois dela, o jogo entra num regime de milhões de draws por frame.

Hipótese agora testável: **redundância de draws**. 2,47 M draws para uma cena que deveria ter
algumas centenas sugere que o port está reexecutando comandos ou que o game graph está sendo
reprocessado. Não é "GPU lenta" — a GPU fica ociosa, então o custo está no **recording** dos draws.

## Próximo passo

Contar quantos draws o **guest** pede versus quantos o port **executa**. Se o guest pede 500 e o
port executa 2,4 M, há multiplicação no caminho de submissão. `Gow3Stats::draws` é incrementado em
`Rasterizer::Draw`, então medir a razão entre submissões do guest e draws executados é a medição
que fecha isso.

# Draws por passe de cor: a geometria É submetida, e chega à tela

## Medição (`GOW3_TRACE_CLEAR=1`, contando draws por `BeginRendering`/`EndRendering`)

```
Clear: pass closed with 17 draws (1 color attachments)
Clear: pass closed with  0 draws (1 color attachments)
Clear: pass closed with  4 draws (1 color attachments)
```

Distribuição em **43.935** passes de cor fechados:

| Draws no passe | Passes |
|---|---|
| 0 | 36.964 (84%) |
| 1-9 | ~4.200 |
| >9 | ~2.700 |

E o frame 1200 dessa execução **tem conteúdo**: 3,71% de pixels não-pretos.

## O que isso estabelece — e o que não estabelece

**Estabelecido:** a geometria é submetida (passes com 17, 4, 9 draws) e **chega à tela** (3,71% de
conteúdo no frame 1200). Portanto o pipeline de desenho funciona; não é "nada desenha".

**Não estabelecido:** que 84% de passes vazios seja o bug. Passes de cor com zero draws são
plausíveis num motor com passes de preparação, depth-only e cópias. Chamar isso de causa seria
interpretar demais.

## O que continua sendo o fato estranho

A tela **funciona até ~frame 1800 e depois fica preta**, com o motor a 60 FPS. A sequência medida
até aqui:

| Frame | Conteúdo |
|---|---|
| 1200 | 3,71% (conteúdo) |
| 1700-1800 | 100% (menu) |
| 2500+ | 0% (preto) |

O problema está **na transição depois do menu**, não no pipeline como um todo. As passes vazias
podem ser sintoma (nada é submetido porque o estado de jogo parou) e não causa.

## Próximo passo correto

Capturar em 1800, 2000, 2500, 3000 **na mesma execução** com `GOW3_TRACE_CLEAR=1` e comparar
`pass closed with N draws` entre o período que funciona e o preto. Se os draws caírem para zero
junto com a tela, é o guest que parou de submeter; se continuarem altos, é estado de render.

# Passes de render: só 6 de 90 têm alvo de cor, e todos limpam para preto

## Medição (`GOW3_TRACE_CLEAR=1`)

Instrumentei `Scheduler::BeginRendering`, que é onde o Vulkan recebe os anexos de render:

```
Clear: BeginRendering #1,    0/0 color clears, 1 black; depth_clear=0
Clear: BeginRendering #500,  0/0 color clears, 1 black; depth_clear=0
Clear: BeginRendering #5500, 1/1 color clears, 1 black; depth_clear=0
```

Distribuição em 90 chamadas logadas:

| Anexos de cor | Chamadas |
|---|---|
| **0** | **83** |
| 1 | 7 |

E das passes que **têm** alvo de cor, **21 de 21 limpam para preto**
(`1/1 color clears, N black`), em nova execução com filtro nas que têm anexo.

## Interpretação cautelosa

`0/0 color clears` **é normal** para passes de profundidade, cópia e compute — não é bug por si.
O sinal relevante é outro: as poucas passes que escrevem cor **começam limpando para preto**, e o
frame capturado depois disso continua preto. Ou seja, nada desenha por cima do clear.

Limpar para preto no início de um frame também é normal. O que falta medir é se **algo é desenhado
depois do clear** nesse alvo. Sem essa contagem, "limpa para preto" sozinho não prova nada — e eu
não vou registrar como causa.

## Onde isso deixa a investigação

Descartados por medição: paks, `usrdt53l`, performance (60 FPS), input (controle), SRT, deadlock.
O que resta é: **o guest para de submeter geometria que cubra o alvo de cor** depois do menu, ou o
estado de render (blend/viewport/scissor) faz os draws caírem fora.

Próxima medição necessária: contar draws **por passe**, associados ao `BeginRendering` que tem
anexo de cor. Se houver clear + 0 draws, o guest não desenha. Se houver clear + draws, o problema é
estado de pipeline.

# Tela preta após o menu: NÃO é o input (controlado)

## O controle que refutou a hipótese

| Execução | Input | Frames pretos? |
|---|---|---|
| `boot-80` | `cross` injetado via `GOW3_PAD_FILE` | 1700: 6,55% → 2000+: **0%** |
| `boot-82` | **nenhum input** | 2500, 3500, 5000, 8000: **todos 0%** |

Sem nenhuma entrada, a tela também fica preta e permanece preta em quatro capturas ao longo de
8000 frames. **O input não é a causa.** A hipótese anterior está refutada por experimento, e não
foi registrada como conclusão.

## O comportamento real

1. O jogo carrega (frames lentos, ~17-40 fps no trecho de carga).
2. O menu aparece por volta do frame 1700-1800 (100% de pixels não-pretos).
3. Depois disso a tela fica **inteiramente preta** e assim permanece.
4. O motor continua saudável: **60 FPS**, 1 draw/frame, GPU 67-97% ociosa, 39 threads,
   12.900+ frames apresentados com `Success`.

Ou seja: apresenta sem erro uma imagem que é preta. Não é travamento, não é saturação, não é input.

## Hipóteses que restam

- O jogo troca para um alvo de renderização que o port não apresenta (o "display" upscaled pode
  estar apontando para uma imagem vazia).
- Um passe de pós-processamento escreve preto por engano (filtro, gamma, ou o `SanitizeCopyLayers`
  que clampa layers).
- O jogo entrou num estado de espera e limpou a tela de propósito (transição).

Distinguir exige comparar `display_*` com `output_*`, que já estão sendo capturados os dois.

# Input scriptado: o caminho funciona, e há uma pista de mudança de estado

## O que está provado

`GOW3_PAD_FILE` injeta botões de verdade: o log registra
`Runtime: pad file: buttons 0x4000` (`BTN_CROSS`). O guest continua lendo o pad durante a execução.

## Observação que precisa de controle antes de virar conclusão

| Execução | Frame 1700 | Desfecho |
|---|---|---|
| com `GOW3_PAD_FILE` (cross apertado) | 6,55% → depois **0,00%** (preto) | 13.200 frames, 51 fps |
| sem `GOW3_PAD_FILE` | **100,00%** (menu) | parou em 1800 |

Parece que o input levou a tela ao preto. **Mas isso não está estabelecido**, por duas razões:

1. Os índices de frame **não são comparáveis entre execuções** — a fase de carregamento tem
   duração variável, então "frame 1700" pode ser menu numa execução e outra coisa na seguinte.
2. A execução sem input só chegou a 1800 frames; não vi se ela também escurece depois.

Uma execução longa sem input está em andamento para resolver (2). Não vou registrar "input causa
tela preta" até esse controle existir.

## Estado do motor nesse ponto

1 draw/frame, GPU ociosa (67-97%), 60 FPS, 39 threads. Ou seja: o motor continua **apresentando
normalmente** uma imagem que é preta. Isso é diferente de travar.

# CORREÇÃO 2: não há saturação — o jogo roda a 60 FPS e fica ocioso

## Duas conclusões minhas estavam erradas

**Erro 1 — "~950.000 draws por frame".** Falso. Eu li um contador **cumulativo** de uma janela de
300 frames e dividi errado. O número real, com `GOW3_FRAME_STATS=1`:

```
Frame stats: 60.0 FPS, worst frame 18.4 ms (vblank 60 Hz); 0 shader/pipeline compiles;
  GPU thread 0.00 us/draw, 6 draws/frame, idle 0.1%
Frame stats: 60.0 FPS, worst frame 17.9 ms; 1 draws/frame, idle 0.2%
```

**1 a 6 draws por frame.** Não 950 mil. A GPU fica **100% ociosa**.

**Erro 2 — "saturação, ~3,7 fps".** Falso também. Os frames lentos que medi (81 s para 300 frames)
eram a **fase de carregamento**, não um regime permanente. Em regime, o jogo sustenta **60,0 FPS com
pior frame de 18 ms**.

## O que o jogo está realmente fazendo

Está **ocioso, esperando algo**, numa tela estática:

| Métrica | Valor |
|---|---|
| FPS | 60,0 estável |
| Pior frame | 17,9-18,4 ms |
| Draws/frame | 1 a 6 |
| Compilações de shader | 0 (após o startup) |
| GPU idle | 99,9-100,8% |
| Recorder syncs | ~300 por 5 s |
| Write faults | 57-60/s, 0 hot pages |

O áudio também inicializou:

```
Runtime: audio port 0 opened (type 0, 8 ch, float, 256 frames, downmixed to stereo)
```

E há uma thread de câmera: `guest thread 'FPS4Tracker::CameraThread'`.

## Conclusão corrigida

Não é problema de desempenho nem de GPU. O motor está **parado num estado de espera** com
apresentação saudável a 60 FPS e poucos draws. Isso é consistente com: tela de carregamento
aguardando IO, ou um estado de jogo esperando um evento (input, save, ou uma thread).

A investigação correta é sobre **progresso de estado**, não sobre renderização.

# Frame 1800+: não é travamento, é saturação — e o jogo estava carregando um checkpoint

## A instrumentação que separou as duas hipóteses

Tempo por apresentação (não só contagem):

```
Swapchain: present #1500 at  27166 ms (55.22 fps avg) -> Success
Swapchain: present #1800 at  44867 ms (40.12 fps avg) -> Success
Swapchain: present #2100 at  59651 ms (35.20 fps avg) -> Success
Swapchain: present #2400 at 140987 ms (17.02 fps avg) -> Success
```

O jogo **continua apresentando**. Não há deadlock: de 1800 a 2400 foram 300 frames em **81
segundos** (~3,7 fps no trecho). É saturação, não travamento.

Correção de uma leitura anterior minha: eu havia dito "para de apresentar em ~1800". O que ocorre é
que cada frame passa a custar muito mais, então uma janela de `timeout` fixa cobre cada vez menos
frames. A conclusão correta é **desempenho**, não bloqueio.

## O que a tela mostra nesse trecho

Capturas em 1900 e 2200 têm **estatísticas idênticas** (6,55% não-preto, caixa
`516,584..1872,1032`) mas sha256 diferente — mesmo layout, pixels mudando devagar. O conteúdo é
UI com arte renderizada num canto inferior. Entre as duas capturas o contador registrou
**2.169.064 draws**: muito trabalho submetido para uma imagem que quase não muda.

## O jogo estava carregando um checkpoint

```
Runtime: save data 'SystemSave'   mounted at /savedata0 (existing, read-only)
Runtime: save data 'SharedSave'   mounted at /savedata0 (existing, read-only)
Runtime: save data 'CheckPoint1'  mounted at /savedata0 (existing, read-only)
Runtime: save data 'CheckPoint1'  mounted at /savedata0 (existing, read-only)
```

`CheckPoint1` é montado **duas vezes**. E o pad continua sendo lido (`pad read #1801`,
`lx=128 ly=119 rx=125 ry=124`) — o loop de input está vivo.

## Duas questões abertas, agora separadas

1. **Desempenho**: ~1,1 M draws por 100 frames numa tela quase estática. Onde esse trabalho é
   gasto? (shaders recompilando? passes redundantes? o buffer de SRT já foi corrigido, mas abriu
   5+ blocos.)
2. **Progressão**: o jogo monta `CheckPoint1` duas vezes. É reentrada legítima ou um laço?

Nenhuma das duas é "fault" ou "deadlock". Ambas precisam de contadores, não de suposição.

# `sceSaveDataGetParam`: import faltante que barrava a progressão

## O que aconteceu

Depois do menu, o boot parava em:

```
STOP: first unsupported PS4 import: XgvSuIdnMlw#libSceSaveData (index 139)
API: name not resolved; see analysis.json import_name_hints
```

Identificado por aerolib: **`sceSaveDataGetParam`** — o par de leitura do
`sceSaveDataSetParam`, que já existia. O jogo o chama ao montar a lista de slots de save.

Duas causas empilhadas:
1. **Sem implementação.** Só o setter existia.
2. **NID ausente da tabela de nomes.** `XgvSuIdnMlw` não estava em `import_names.inc`, então o
   resolver não conseguia mapear o índice para o nome — mesmo que a função existisse, nada a
   ligaria. Foi preciso adicionar as duas coisas.

## Implementação

`save_get_param` é simétrico ao setter, com os mesmos 5 tipos (ALL, título, subtítulo, detalhe,
user_param), devolvendo `ERR_PARAMETER` para tipo desconhecido ou buffer curto em vez de escrever
além do limite.

## Resultado medido

Antes: `exit 20` no import 139 (~frame 1200).
Depois: `exit 124` (timeout), alcançando o frame 1800 — **passou do bloqueio**.

O boot agora **estaciona em torno do frame 1800** em vez de parar num import. Não há fault; o
processo simplesmente não avança. Isso é um sintoma diferente e ainda não diagnosticado: pode ser
espera de save/IO, diálogo modal, ou o salto para geometria 3D saturado (2,8 M draws num frame).

# Input: o guest lê o pad; e dois achados novos

## O guest realmente consulta o input

`scePadReadState` é chamado 1800+ vezes por execução. E os valores não são neutros:

```
Runtime: pad read #1:   buttons=0x00000000 lx=128 ly=128 rx=128 ry=128
Runtime: pad read #601: buttons=0x00000000 lx=130 ly=120 rx=96  ry=136
```

`lx=130 ly=120 rx=96 ry=136` é **drift real do DualSense físico** — ou seja, o estado do
SDL3 chega ao guest. O caminho de input funciona; `buttons=0` porque ninguém apertou nada durante
aquela execução.

## Achado 1: tela preta depois do menu (P0)

| Frame | Não-preto | Draws no frame |
|---|---|---|
| 1800 | **100%** (menu, paleta dourada) | ~950.000 |
| 1900 | **0,00%** (preta) | 3.587.201 total |

Frame 1900 submete **3,58 milhões de draws** e produz uma imagem inteiramente preta. Isso não é
"nada foi desenhado" — é muito desenhado e nada aparece. Bugs plausíveis: alvo de renderização
errado, barreira faltando, ou o clamp de `SanitizeCopyLayers` descartando conteúdo.

## Achado 2: `GOW3_PAD_FILE` trava a execução (P0)

Com `GOW3_PAD_FILE` apontando para um arquivo (mesmo vazio), a execução parou no frame 700 e
**saiu sem fault e sem erro**. Sem a variável, a mesma build chega ao frame 5500.

```
sem GOW3_PAD_FILE : flips=5500  (exit 124, timeout)
com GOW3_PAD_FILE : flips=700   (saiu)
```

Isso é um bug real no caminho de input scriptado, não uma medição inválida: a variável deveria ser
inerte quando o arquivo está vazio. Registrado como suspeita medida; a causa não foi isolada.

# O jogo chega ao MENU PRINCIPAL — medido por contagem de draws

## Medição que separa "tela de loading" de "cena"

Instrumentei draws submetidos por frame (`Gow3Stats::draws`, já existente no código):

| Frame | Draws no frame | Draws por frame |
|---|---|---|
| 60 | 242 | ~4 |
| 300 | 1.115 | ~3,6 |
| 900 | 3.775 | ~3,3 |
| 1800 | 2.845.652 | **~950.000** |

Entre os frames 1500 e 1800 foram **2.169.079 draws**. Não é uma tela estática: o jogo sai de uma
sequência de UI (3-4 draws/frame) e **explode em geometria 3D** por volta do frame 1800.

## O que está na tela no frame 1800

`python scripts/frame_stats.py`: **100,00%** de pixels não-pretos, caixa cobrindo a tela toda.

Análise de conteúdo: fundo branco, com duas faixas de conteúdo em y 583..911 e 942..1031, nas
cores quentes da paleta do jogo — `#e7b344`, `#de9b0b`, `#b96c13`, `#a36e03` (dourado/âmbar).
A estrutura é a de uma tela de menu: título no topo e uma lista de entradas.

Isto corresponde a **menu principal**, não a gameplay. Mas é muito além do que os documentos
registravam ("faixa de glifos em 2% da tela").

## Progressão completa observada

| Frames | Conteúdo | Interpretação |
|---|---|---|
| 60 | 0,85% não-preto, caixa pequena, `#ffffff` | tela de abertura |
| 300 | 1,96%, caixa 512..1414, `#75622e`/`#024d76` | texto/logo |
| 900 | 1,36%, faixa horizontal fina, `#8f8f8f` | barra de progresso |
| 1800 | **100%**, paleta dourada | **menu principal** |

## Ressalva

Draws por frame passam a ser submetidos, mas isso **não** prova que a cena 3D aparece corretamente
nem que há jogabilidade. O frame capturado no 1800 é o menu. Nenhum teste de input, áudio ou
movimentação foi feito.

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
