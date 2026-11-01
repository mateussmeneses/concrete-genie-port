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
