# Handoff entre IAs

- Data (UTC): 2026-11-01, sessão PROMPT 04 (continuação).
- Branch: `bootstrap/windows`. Nenhum merge, rebase ou reset executado.
- **Critério do PROMPT 04 NÃO atingido: não existe primeira cena jogável.** Não houve frame.

## Avanço desta sessão (medido)

Dois bloqueios resolvidos, com o boot parando três estágios mais adiante:

| Métrica | Antes | Agora |
|---|---|---|
| Bloqueio | `abort` sem causa | **conteúdo em ~2% da tela; sem cena jogável** |
| Reserva do pool 8 GiB | recusada (`NO_MEMORY`) | **concedida** (3 reservas) |
| Threads guest | 0 | **36** |
| Leitura do dump | 0 arquivos | **4.654 leituras, 109.826.114 bytes** |
| AppContent | não inicializava | **inicializado**, perfil offline |
| Exit | 3 (fault) | 20 (import não implementado) |
| Testes Python | 39 | **72** |

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

**Isso não é uma cena jogável.** É uma faixa central de glifos em ~2% da tela, compatível com
tela de título ou indicador de carregamento. Sem câmera, personagem, pintura, menu ou áudio
verificado, o critério do Prompt 04 continua **não cumprido**.

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

Implementar leitura de pak UE4 — o runtime não abre os 23 GB de conteúdo do jogo.

Medido nesta sessão: o dump tem dois paks **válidos** (`concretegenie-ps4.pak` 19,1 GB e
`concretegenie-ps4_0_p.pak` 5,4 GB; assinatura `0x5A6F12E1` no rodapé, `mount point ../../../`,
57.303 entradas), e o runtime **nunca tenta abri-los** — não há implementação de pak em
`runtime/src/`. O motor pede arquivos que vivem dentro do pak, recebe "not found" (116 ocorrências,
49 delas `internationalization/usrdt53l.dat`) e segue com os loose files.

Isso é consistente com a tela capturada (faixa de glifos em ~2% da imagem), mas **não está
confirmado como causa** — confirmar exige ler o pak e ver a tela mudar.

A captura, entretanto, funciona; ela é o instrumento de verificação.

Reprodução exata (o `env` é obrigatório; o prefixo inline não propaga neste shell):

```bash
cd .cg/audit/run && source ../../runtime/msys2-env.sh && export PATH="/c/msys64/clang64/bin:$PATH"
env GOW3_DUMP_DIR="C:/projetos/concrete-genie-port/.cg/audit/dump"     GOW3_FRAME_DUMP_AT=300 GOW3_DUMP_SYNC=1     timeout 110 ../../runtime/out/gpu/cg-runtime.exe     ../../.cg/audit/prepared/boot-linked.bin     --content-profile ../../.cg/audit/prepared/content.bin     --app0 "C:/projetos/concrete-genie-port/gamedump/CUSA11875"     --user ../../.cg/audit/run/user --timeout 85
python scripts/frame_stats.py dump/output_000_1920x1080.raw
```

1. Obter o formato do índice pak **v4** de fonte primária (v4 tem hash por entrada e tabela de
   nomes separada; a tentativa de parse por nome falhou e não deve ser refeita por tentativa).
2. Implementar montagem mínima em `runtime/src/`: abrir o índice, resolver caminho → (offset,
   tamanho, compressão) e servir em `runtime_file_open`.
3. Teste de aceitação: localizar `usrdt53l.dat` e `icudt53l.dat` **pelo nome** no índice, antes de
   servir qualquer byte.
4. Verificar com captura antes/depois: `python scripts/frame_stats.py <frame.raw>`.

Critério de conclusão: o motor para de pedir arquivos que existem no pak, e um frame capturado
mostra conteúdo além da faixa de glifos. Não declarar cena jogável sem movimento, input e áudio.

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
