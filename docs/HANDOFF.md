# Handoff entre IAs

- Data (UTC): 2026-11-01, sessão PROMPT 04 (continuação).
- Branch: `bootstrap/windows`. Nenhum merge, rebase ou reset executado.
- **Critério do PROMPT 04 NÃO atingido: não existe primeira cena jogável.** Não houve frame.

## Avanço desta sessão (medido)

Dois bloqueios resolvidos, com o boot parando três estágios mais adiante:

| Métrica | Antes | Agora |
|---|---|---|
| Bloqueio | `abort` sem causa | `NpToolkit2::Core::init` (serviço) |
| Reserva do pool 8 GiB | recusada (`NO_MEMORY`) | **concedida** (3 reservas) |
| Threads guest | 0 | **22**, incluindo `TaskGraphThreadNP 0..N` (UE4) |
| Leitura do dump | 0 arquivos | **174 leituras, 10.107.208 bytes** |
| AppContent | não inicializava | **inicializado**, perfil offline |
| Exit | 3 (fault) | 20 (import não implementado) |
| Testes Python | 39 | **50** |

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

```
STOP: first unsupported PS4 import: LLdnqVnnNBQ#libSceNpToolkit2 (index 657)
API: _ZN3sce7Toolkit2NP2V24Core4initERKNS3_7Request10InitParamsE
```

`Core::init` é o **serviço** que inicializa o subsistema PSN, não um construtor. O guest faz
`testl %eax,%eax; je <continua>` e, com 0, passaria a tratar o PSN como inicializado.

**Não foi respondido por decisão.** As 79 funções de `libSceNpToolkit2` incluiriam caminhos que
acreditariam num subsistema nunca inicializado, e a falha apareceria muito depois. Falta uma
decisão de arquitetura registrada: recusar com erro tratado, ou implementar um PSN local mínimo
com estado.

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

Decidir e registrar a política de PSN offline para `Core::init`:

1. Avaliar o que o guest faz no ramo de falha (`0x40c791f`) — se degrada para modo offline
   legítimo, recusar com erro é a resposta correta e barata.
2. Se o jogo exige sucesso, implementar um PSN local mínimo **com estado** (init cria um
   contexto; as chamadas seguintes validam contra ele e falham com código real, não com zero).

Critério de conclusão: o `STOP` desaparece, o boot avança para um estágio novo e nomeado, e o
subsistema responde com códigos coerentes — não com sucesso cego.

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
