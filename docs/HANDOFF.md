# Handoff entre IAs

- Data (UTC): 2026-11-01, sessão PROMPT 04 (continuação).
- Branch: `bootstrap/windows`. Nenhum merge, rebase ou reset executado.
- **Critério do PROMPT 04 NÃO atingido: não existe primeira cena jogável.** Não houve frame.

## Avanço desta sessão (medido)

Dois bloqueios resolvidos, com o boot parando três estágios mais adiante:

| Métrica | Antes | Agora |
|---|---|---|
| Bloqueio | `abort` sem causa | fault em `RHIThread` durante init de RHI |
| Reserva do pool 8 GiB | recusada (`NO_MEMORY`) | **concedida** (3 reservas) |
| Threads guest | 0 | **36** |
| Leitura do dump | 0 arquivos | **4.654 leituras, 109.826.114 bytes** |
| AppContent | não inicializava | **inicializado**, perfil offline |
| Exit | 3 (fault) | 20 (import não implementado) |
| Testes Python | 39 | **53** |

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

**Todos os subsistemas de sensor foram resolvidos** e o boot saiu da camada de imports. Estado
atual:

```
Fault: execute access to 0000000000000000 at 0000000000000000
  thread name: RHIThread
  #0 guest offset 0x14d6aec
```

O jogo chegou à **inicialização de RHI do UE4** e configura GPU Vulkan 1.4.357, resolução
1920x1080, um DualSense e 12 sondagens de formato. A falha é `callq *0x8(%rsi)` com `rsi` nulo
em `0x14d6ae9`, seguida de `0x14d6aec`. Determinístico em duas execuções.

Nenhum frame foi renderizado. `RHIThread` falhar **dentro** da inicialização não é cena, menu
nem intro.

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

Resolver a conversão nome→NID para `sceKernelDlsym`.

O módulo já está ligado e inicializado (`prx/binkpluginps4.prx@0x6540000`, `module_start` rodou),
e o boot estendido G3PROBE6 já carrega a tabela de exports. Falta apenas casar o nome que o guest
passa (`"BinkPluginGoto"`) com o NID exportado pelo módulo.

1. Obter o algoritmo de NID do PS4 a partir de fonte primária (não por tentativa): os exports do
   próprio módulo dão pares de validação (`b0xyllnVY-I` = `sceGnmAddEqEvent`, etc.), então
   qualquer implementação pode ser conferida antes de ser usada.
2. Alternativa: localizar no eboot a tabela nome→NID, se o jogo a contiver.
3. Só então preencher os slots.

Critério de conclusão: `runtime_linked_symbol()` devolve endereço não nulo para os 14 nomes
`BinkPlugin*`, e o fault em `RHIThread` muda de lugar. Não preencher com stubs vazios.

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
