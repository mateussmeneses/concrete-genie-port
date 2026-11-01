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

Investigar o fault em `RHIThread` em `0x14d6aec`:

1. Desassemblar a função em torno de `0x14d6a9x` e identificar qual ponteiro virtual é nulo — é o
   primeiro ponto em que o runtime entrega um objeto incompleto ao código de renderização.
2. Verificar se algum dos subsistemas recém-implementados (áudio 3D, PSVR, VrTracker) devolve
   uma estrutura que o RHI depois lê. `sceVrTrackerQueryMemory` devolve 0 sem preencher a saída;
   o guest testa o retorno (`testl %eax,%eax; jne` em `0x36f3f56`), então a hipótese principal é
   que 0 = sucesso leve o guest a consumir uma estrutura que nunca foi preenchida.
3. Adicionar telemetria ao redor do ponteiro nulo antes de mudar comportamento.

Critério de conclusão: o fault nomeia a origem (import, estrutura ou caminho de GPU) com log
correspondente. Não corrigir devolvendo sucesso a mais chamadas.

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
