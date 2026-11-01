# Estado do projeto

Atualizado: 2026-10-31 UTC. **PROMPT 02 concluído; nenhum boot de Concrete Genie foi
demonstrado.** A build local foi identificada, não validada.

## O que existe agora

- Repositório independente na branch `bootstrap/windows`, com o runtime auditado de MediEvil
  vendorizado em `runtime/` (base `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94`). O upstream não
  foi sobrescrito nem reorganizado; `references/medievil` preserva o checkout original.
- Build Windows CLANG64 reproduzível: `bash build.sh` (submódulos, patches idempotentes,
  `cg-runtime`, `cg-gpu-check`) e `bash build.sh --test` (seis alvos nativos). Exit 0
  registrado em `docs/evidence/bootstrap/`. Detalhes em BASELINE.
- Pipeline independente de dump: `--help`, `--check-config`, mensagem acionável sem jogo,
  `--audit-runtime` e `--vulkan-smoke` rodam sem nenhum arquivo comercial.
- Perfis fail-closed por TITLE_ID: `CUSA11834` (US) e `CUSA11875` (EU) são candidatos com
  `builds: {}`. Título desconhecido, build não registrada, SFO inválido e módulo ausente param
  o pipeline antes de qualquer escrita.
- Prefixo de configuração do projeto (`CG_*`), JSON validado, dados isolados em `.cg/`,
  saves por TITLE_ID separados de cache por SHA-256 do eboot.
- Nomenclatura genérica onde é seguro (`cg-runtime`, `cg-gpu-check`, `concrete-genie.ini`,
  `runtime.manifest`, identidade `cg.runtime`). Hooks e patches de MediEvil foram **removidos**
  do runtime genérico, não promovidos.

## Dump local identificado (não validado)

`gamedump/CUSA11875`, 25 GB, fora do controle de versão (ignorado pelo `.gitignore`).

| Campo | Valor |
|---|---|
| `TITLE_ID` | `CUSA11875` (edição europeia) |
| `TITLE` | `Concrete Genie` |
| `APP_VER` / `VERSION` | `01.07` / `01.00` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` |
| `eboot.bin` | 108.601.759 bytes, SELF (`4F 15 3D 1D`) |
| `eboot.bin` SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` |
| Engine | Unreal Engine 4 (`ConcreteGenie.uproject`) + Bink 2 |

Identificar a build não é validá-la. `CUSA11875` **não** foi registrada em `builds` e
nenhum patch foi habilitado.

## Estado de verificação

| Item | Estado |
|---|---|
| Build nativo (`cg-runtime`, `cg-gpu-check`) | PASSA, exit 0 |
| `build.sh --test`, seis testes nativos | PASSA, exit 0 |
| Suíte Python do projeto (`tests/`) | PASSA, 14 testes, exit 0 |
| `--help`, `--check-config`, falta de jogo | PASSA, respostas válidas sem dump |
| Auditoria de runtime e smoke Vulkan | PASSA (NVIDIA RTX 5060) |
| Pipeline contra o dump real | exit 1, recusa fail-closed com o hash correto |
| Suíte herdada `runtime/tests` | NÃO VERDE, exit 1 (herdada; fora do escopo) |
| **Boot / menu / gameplay / áudio / saves** | **NÃO EXECUTADO** |

## Limites conhecidos

- `eboot.bin` é SELF: descriptografia/descompressão, relocations e imports reais nunca foram
  processados. Loader não executou conteúdo comercial.
- `sce_module/` inclui `libSceNpToolkit2`, `libSceFios2` e quatro módulos de rastreamento
  (face/hand/head tracker) ligados a câmera/PSVR. Nenhum contrato implementado ou verificado.
- `runtime/launcher/medievil_launcher.py` e `packaging/windows/package.sh` ainda carregam
  branding, updater e ícones de MediEvil; não são o ponto de entrada suportado. A entrada
  neutra é `Launch Concrete Genie.cmd` → `run.py`.
- A suíte herdada continua vermelha por expectativas de GoW/MediEvil; não foi filtrada.
- Distribuição Windows limpa, frame pacing, VRAM, flicker e iluminação: não medidos.

## Próxima ação

PROMPT 03 — auditoria do dump: `scripts/audit_game.py` gerando manifesto JSON local com
`TITLE_ID`, `APP_VER`, `CONTENT_ID`, SHA-256, imports/NIDs, módulos, codecs e sinais de UE4,
validado contra `gamedump/CUSA11875` e com fixtures sintéticas. Critério em HANDOFF.

HEAD de partida desta etapa: `60f0aa7a626b6d224f96c510accafc5e88954d13`. Commits desta
etapa são locais; **sem merge automático**.
