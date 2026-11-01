# Handoff entre IAs

- Data (UTC): 2026-10-31, sessão PROMPT 02 (bootstrap) + inspeção inicial do dump.
- IA/sessão: Hermes Agent. Sucessora da sessão Codex que produziu a auditoria PROMPT 01.
- Branch: `bootstrap/windows`. HEAD de partida: `60f0aa7a626b6d224f96c510accafc5e88954d13`.
  **Nenhum merge, rebase ou reset foi executado.** Commits desta etapa são locais.
- Upstream: runtime vendorizado do MediEvil em
  `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94` (`runtime/`), checkout de inspeção em
  `references/medievil`. Submódulos no SHA fixado; ver `docs/evidence/bootstrap/submodules.txt`.

## O que foi feito nesta etapa

1. **Bootstrap independente** — branch própria, runtime vendorizado sem reorganização,
   nomes genéricos (`cg-runtime`, `cg-gpu-check`, `concrete-genie.ini`, `runtime.manifest`,
   identidade `cg.runtime`), config `CG_*`, dados isolados em `.cg/`.
2. **Perfis por TITLE_ID, fail-closed** — `CUSA11834` (US) e `CUSA11875` (EU) como candidatos
   com `builds: {}`. Qualquer eboot é recusado com o SHA-256 calculado na mensagem.
3. **Hooks de outro jogo removidos** do runtime genérico (cheats, multiplicadores, health
   bar, `apply_patches`, sites SSE4a fixos, `r.SetRes`). Emulação SSE4a por fault handler
   permanece — é genérica, sem offsets de título.
4. **Build reproduzível corrigido em três bugs reais** — descritos em `docs/BASELINE.md` e
   `docs/DECISIONS.md`: patches que nunca aplicavam, `windres` sem temp dir, `winmm` ausente
   nos alvos de teste. Nenhum `--reject`, nenhum exit code silenciado.
5. **Smoke independente de dump** — `--help`, `--check-config`, falta de jogo, `--audit-runtime`,
   `--vulkan-smoke`; todos validados sem arquivo comercial.
6. **Governança multi-IA preenchida** — `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, e os sete
   documentos em `docs/`.

## Dump — o que foi efetivamente verificado

O operador forneceu um dump local em `gamedump/CUSA11875` (25 GB, fora do controle de versão).

| Campo | Valor verificado |
|---|---|
| Caminho | `gamedump/CUSA11875/` |
| `TITLE_ID` | `CUSA11875` |
| `TITLE` (param.sfo) | `Concrete Genie` |
| `APP_VER` | `01.07` |
| `VERSION` (param.sfo) | `01.00` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` |
| `CATEGORY` | `gp` |
| `eboot.bin` tamanho | 108.601.759 bytes |
| `eboot.bin` SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` |
| Container | SELF (magic `4F 15 3D 1D`) |
| Engine | Unreal Engine 4 (`ue4commandline.txt` → `ConcreteGenie.uproject`) |
| Middleware | Bink 2 (`prx/bink2ps4.prx`, `binkpluginps4.prx`) |
| Módulos `sce_module/` | libc, libSceFios2, libSceNpToolkit2, libSceJobManager, libSceAudioLatencyEstimation, libSceFace, libSceFaceTracker, libSceHand, libSceHandTracker, libSceHeadTracker, libSceS3DConversion, libSceSmart |

Isso **identifica** a build. Não valida boot, imports, loader, menu ou gameplay.

### Resultado do pipeline contra o dump real

```
$ python run.py --game-dir C:/projetos/concrete-genie-port/gamedump/CUSA11875
Concrete Genie: Unvalidated build: CUSA11875 APP_VER=01.07
eboot SHA-256=06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51.
Candidate title only; inspect the dump before registering support. No patches applied.
exit 1
```
Evidência: `docs/evidence/bootstrap/dump-unvalidated.txt`. Nenhum diretório de estado foi
criado, nenhum byte do dump foi escrito — o hash foi recalculado depois e não mudou.

## Estado de execução

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0, seis testes nativos |
| `python -m unittest discover -s tests -v` | exit 0, 14 testes |
| `--help` / `--check-config` | exit 0 |
| falta de jogo | exit 1 com mensagem acionável |
| `--audit-runtime` | exit 0, "Runtime audit PASS" |
| `--vulkan-smoke` | exit 0, NVIDIA RTX 5060, submission + readback 4096 B |
| pipeline com dump real | exit 1, recusa fail-closed |
| suíte herdada `runtime/tests` | exit 1 (GoW/MediEvil), não corrigida |
| **boot / menu / gameplay / áudio / saves** | **NÃO EXECUTADO** |

## Falhas e riscos conhecidos

- `eboot.bin` é SELF; descriptografia/descompressão e relocations reais não foram testadas.
- Módulos presentes incluem `libSceNpToolkit2`, `libSceFios2` e quatro módulos de
  rastreamento de rosto/mão/cabeça (PSVR/câmera). Nenhum contrato foi implementado ou
  verificado para eles nesta etapa.
- `runtime/launcher/medievil_launcher.py` e `packaging/windows/package.sh` ainda têm branding,
  updater e ícones de MediEvil. Não são ponto de entrada suportado; a entrada neutra é
  `Launch Concrete Genie.cmd` → `run.py`.
- Suíte herdada vermelha: não foi "consertada" para parecer verde.

## Próxima ação única, verificável

**PROMPT 03 — auditoria do dump.** Escrever `scripts/audit_game.py` que produza um manifesto
JSON local (sem distribuir binários) com `TITLE_ID`, `APP_VER`, `CONTENT_ID`, SHA-256 de
`eboot.bin`, tabela de imports/NIDs, módulos de `sce_module/`, codecs e sinais de UE4,
validado contra `gamedump/CUSA11875` e com fixtures sintéticas para os testes.

Critério de conclusão: o manifesto é reproduzível em duas execuções com o mesmo hash; os
testes de parsing passam sem o dump; e nenhum binário comercial entra no índice do Git.
Registrar a build em `CANDIDATES['CUSA11875']['builds']` **somente** após o manifesto
justificar a lista de módulos — e ainda assim isso não equivale a boot validado.

Não iniciar patch binário, GPU ou otimização antes disso.
