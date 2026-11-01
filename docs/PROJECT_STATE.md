# Estado do projeto

Atualizado: 2026-11-01 UTC. **PROMPT 03 concluído até o primeiro bloqueio observável.**
O código guest do jogo executou; nenhum frame foi renderizado.

## Onde o port está

- Repositório independente na branch `bootstrap/windows`, runtime do MediEvil vendorizado em
  `runtime/` (base `424f3ea`). Upstream não sobrescrito nem reorganizado.
- Build Windows CLANG64 reproduzível (`bash build.sh`, `bash build.sh --test`), exit 0.
- Pipeline sem dump funcionando: `--help`, `--check-config`, falta-de-jogo acionável,
  `--audit-runtime`, `--vulkan-smoke`. 29 testes Python verdes.
- `scripts/audit_game.py` gera manifesto JSON somente-leitura do dump.
- AI Workbench integrado como ferramenta externa: skills em `.agents/`, `.claude/`,
  `.openclaude/`; `.ai-workbench/` fora do Git; `AGENTS.md`/`CLAUDE.md` preservados com
  bloco gerenciado anexado.

## Dump identificado e pipeline executado

`gamedump/CUSA11875` (edição europeia, 25 GB, ignorado pelo Git).

| Campo | Valor |
|---|---|
| `TITLE_ID` / `APP_VER` | `CUSA11875` / `01.07` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` |
| `TITLE` | `Concrete Genie` |
| `eboot.bin` | 108.601.759 bytes, SELF `0x0480` (não cifrado, não comprimido) |
| SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` |
| Entry point | `0x37d58d0` |
| Engine | Unreal Engine 4 + Bink 2 + `libSceAjm` |

Pipeline real, com exit codes:

1. `prepare` (SELF→ELF): 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos — exit 0.
2. `link` (`libc.prx`, `libSceFios2.prx`): 209 native bindings — exit 0.
3. `--check-imports`: **811/988 imports resolvidos** (com shim GPU), 177 faltando — exit 1.
4. Boot: Vulkan inicializado, 106 MB mapeados, 465.785 relocations aplicadas — **exit 3**.

## Primeiro bloqueio observável

`guest offset 0x62c1264` = `libc.prx+0x21264`, função `abort`. Bytes reais:

```
55 4889e5 cd44 bacccccccc b90b0002a0 90 0f0b
   push rbp; mov rbp,rsp; INT 0x44; ... ; ud2
```

O runtime não implementa o gate de syscall PS4 `INT 0x44`; a chamada nunca retorna e a
execução cai no `ud2`. `abort` é exportado pela própria libc, não um import pendente.

Como o abort acontece, **a razão original da chamada se perde. Descobri-la é a próxima ação.**

Correção desta etapa (diagnóstico, não bypass): `is_ps4_syscall_gate()` em `probe.c` nomeia
o bloqueio em vez de reportar "read access to ffffffff".

## Cobertura de imports (medida, não estimada)

| Modo | Resolvidos | Faltando |
|---|---|---|
| `--cpu-only` | 679 / 988 | 309 |
| com shim GPU | **811 / 988** | **177** |

Gaps concentrados em `libSceNpToolkit2` (79), `libSceHmd` (22), `libSceAudio3d` (14),
`libSceVrTracker` (11), `libSceSocialScreen` (7), `libSceCamera` (7), `libSceHmdSetupDialog` (6),
`libSceVrServiceDialog` (5), `libSceMove` (5). Tabela em `docs/evidence/prompt03/`.

## Estado de verificação

| Item | Estado |
|---|---|
| Build nativo + testes nativos | PASSA, exit 0 |
| Suíte Python (`tests/`) | PASSA, 29 testes, exit 0 |
| `audit_game.py` no dump real | PASSA, manifesto escrito |
| Smoke sem dump (help/config/audit/vulkan) | PASSA |
| Código guest executado | **SIM** — módulos ligados, relocations aplicadas |
| **Primeiro frame** | **NÃO** — bloqueio em `int 0x44` dentro de `abort` |
| Menu, intro, gameplay | NÃO EXECUTADO |
| Áudio, saves, câmera/gyro/Move/PSVR | NÃO EXECUTADO (apenas imports presentes) |
| Flicker, iluminação, VRAM, frame pacing | NÃO EXECUTADO |

## Limites conhecidos

- Não se sabe por que `abort` foi chamado; o `INT 0x44` é sintoma, não causa.
- 177 imports sem implementação; nenhum foi stubbado com retorno de sucesso cego.
- `CUSA11834` (US) nunca foi vista em dump; permanece candidata do playbook.
- `runtime/launcher/medievil_launcher.py` e `package.sh` ainda têm branding de MediEvil e
  não são ponto de entrada suportado.
- Suíte herdada `runtime/tests` segue vermelha por expectativas de GoW/MediEvil; não foi
  "consertada" para parecer verde.
- `profiles.py` mantém `CUSA11875` com `builds: {}`: a build foi identificada, não suportada.

## Próxima ação

Instrumentar `runtime_resolve` para registrar os últimos imports servidos e seus valores de
retorno por thread, e dumpá-los no bloqueio. Isso nomeia o serviço cuja resposta levou ao
`abort`. Critério completo em `docs/HANDOFF.md`.
