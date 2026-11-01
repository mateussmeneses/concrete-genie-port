# Handoff entre IAs

- Data (UTC): 2026-10-31/11-01, sessão PROMPT 03 (auditoria do dump + primeiro boot).
- Branch: `bootstrap/windows`. Nenhum merge, rebase ou reset executado.
- Upstream: runtime vendorizado do MediEvil em `424f3ea...`; `references/medievil` intacto.

## Ferramenta externa integrada (AI Workbench)

`aiwh` v0.4.0.dev0 instalado, `aiwh doctor` exit 0. Executados nesta ordem:
`aiwh audit`, `aiwh init --dry-run` (inspecionado), `aiwh init` (aplicado),
`aiwh game-port --platform ps4 --track compatibility-runtime --save`, `aiwh resume`.

- `aiwh init` **preservou** o conteúdo do Prompt 02 em `AGENTS.md` e `CLAUDE.md`: anexou
  apenas um bloco gerenciado `<!-- AIWH:BEGIN -->` ao final. Verificado por diff semântico
  das linhas originais. 15 skills em cada um de `.agents/`, `.claude/`, `.openclaude/`.
- `.ai-workbench/` está ignorado no Git. O handoff transferível continua aqui.
- `aiwh` **não** executou o jogo e não declara testes. Não instalei MCPs/plugins sugeridos.
- Divergência registrada: `GAME_PORT_PLAN.md` diz "No executable bytes inspected" e
  `CONTEXT.md` diz "No TODO items located". Ambas são falsas para este repositório — os
  bytes do eboot foram inspecionados e o HANDOFF anterior tinha próxima ação explícita.
  A avaliação automática não substitui a evidência.

## Resultado central: build identificada, código guest executado, sem frame

Dump `gamedump/CUSA11875` (EU, 25 GB, fora do Git).

| Campo | Valor |
|---|---|
| `TITLE_ID` / `APP_VER` | `CUSA11875` / `01.07` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` |
| `eboot.bin` | 108.601.759 bytes, SELF `0x0480` (não cifrado) |
| SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` |
| Entry point | `0x37d58d0` |
| Engine | UE4 + Bink 2 + `libSceAjm` |

Pipeline executado até o boot:

1. `prepare` → SELF→ELF: imagem de 103.382.639 bytes, **988 imports**, 463.753 relocations,
   64 módulos. Exit 0.
2. `link` com `libc.prx` + `libSceFios2.prx` → **209 native bindings**, 877 imports para o host.
3. `--check-imports` (sem executar guest): 679/988 resolvidos em `--cpu-only`;
   **811/988 com o shim GPU** → 177 faltando.
4. Boot real: GPU Vulkan inicializada (RTX 5060), 106.136.876 bytes mapeados, 9 segmentos,
   **465.785 relocations aplicadas**, pools de memória guest criados.
5. **Falha** em `guest offset 0x62c1264` = `libc.prx+0x21264`, dentro de `abort`
   (`L1SBTkC+Cvw#D#A`), exit code 3.

### Causa raiz demonstrada no disassembly

```
55            push rbp
4889e5        mov rbp, rsp
cd44          int 0x44        <- gate de syscall PS4, não tratado pelo runtime
ba cccccccc   mov edx, 0xcccccccc
b9 0b0002a0   mov ecx, 0xa002000b
90            nop
0f0b          ud2             <- fault observado aqui
```

`abort` é **exportado por libc**, não um import pendente: o linker ligou o código real.
O runtime não implementa `INT 0x44`, então a syscall nunca retorna e a execução cai no `ud2`.

**Não se sabe ainda por que `abort` foi chamado** — essa informação se perde no abort.

Reprodutibilidade: duas execuções independentes, mesmo offset e mesmo exit 3.

## Correção aplicada nesta etapa

`runtime/src/probe.c`: `is_ps4_syscall_gate()` detecta `INT 0x44` no `Rip` e o relatório de
falha passa a nomear o bloqueio em vez de reportar "read access to ffffffff". Não é um stub
nem um bypass: a syscall continua não atendida, apenas passa a ser diagnosticada.
Evidência antes/depois: `evidence/prompt03/boot-01-first-fault.txt` e
`boot-02-blocker-named.txt`.

## Entregáveis

- `scripts/audit_game.py` — manifesto JSON somente-leitura, schema `concrete-genie-audit/1`.
- `tests/test_audit_game.py` — 16 testes com fixtures sintéticas, sem dump.
- `docs/DUMP_AUDIT.md` — auditoria completa do dump.
- `docs/evidence/prompt03/` — manifest, logs de boot (antes/depois), imports por biblioteca,
  build e testes.
- `profiles.py` — `CUSA11875` com bloco `audited` (fatos) e `builds: {}` (ainda não suportada).

## Estado de verificação

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0 |
| `python -m unittest discover -s tests` | exit 0, **29 testes** |
| `audit_game.py` no dump real | exit 0, manifesto escrito |
| `audit_game.py` sem dump / dump inválido | exit 1, mensagem acionável |
| Boot real | exit 3, bloqueio nomeado em `int 0x44` |
| Pipeline `run.py` com o dump | exit 1, recusa fail-closed |
| **Primeiro frame / menu / gameplay** | **NÃO EXECUTADO** |

## Próxima ação única, verificável

Descobrir **por que a libc chama `abort()`**. O `INT 0x44` é sintoma; a causa está no
caminho anterior. Sequência sugerida, sem adivinhar offsets:

1. Instrumentar `runtime_resolve` para registrar, por thread, os últimos N imports servidos
   e o valor de retorno (ring buffer em memória, dumpado no bloqueio). Isso mostra qual
   serviço foi chamado imediatamente antes do abort.
2. Reexecutar o mesmo `boot-linked.bin` e correlacionar o último import com
   `evidence/prompt03/imports-gpu-by-library.txt`.
3. Só então decidir: implementar semântica real do serviço, ou registrar explicitamente o
   stub com hipótese e teste — nunca um retorno de sucesso cego.

Critério de conclusão: o log nomeia o import cuja resposta levou ao abort, com o valor
retornado e o estágio alcançado, e essa correlação está coberta por um teste.

Não iniciar patches binários, GPU ou otimização antes disso. Nenhum offset de MediEvil,
Matterfall ou GoW III deve ser importado.
