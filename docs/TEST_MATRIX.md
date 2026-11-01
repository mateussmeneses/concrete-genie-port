# Matriz de testes

Atualizado: 2026-11-01 UTC. Dump `gamedump/CUSA11875` auditado e executado até o primeiro
bloqueio. **Nenhum frame foi renderizado.** Evidências em `docs/evidence/`.

## Ambiente medido

Windows 11 Home Single Language 10.0.26300; Intel Core i7-14650HX; 33.937.809.408 bytes de
RAM (31,61 GiB). NVIDIA GeForce RTX 5060 Laptop GPU (Vulkan driverInfo 621.01, API 1.4.357,
refresh 165 Hz); Intel RaptorLake-S integrada (driverInfo 101.7088, API 1.4.323).
MSYS2 CLANG64 clang 22.1.7, Vulkan 1.4.350 (pkg-config), SDL3 3.4.10, libavcodec 62.28.101,
fmt 12.1.0, Python 3.14. AI Workbench `aiwh` v0.4.0.dev0.

## Build e testes do projeto

| Verificação | Comando | Resultado | Evidência |
|---|---|---|---|
| Submódulos | `git submodule status --recursive` | PASS, SHA fixado | `bootstrap/submodules.txt` |
| Build nativo | `bash build.sh` | PASS, exit 0 | `prompt03/build.txt` |
| Testes nativos | `bash build.sh --test` | PASS, exit 0 | `prompt03/build-test.txt` |
| Suíte Python | `python -m unittest discover -s tests` | PASS, **29 testes**, exit 0 | `prompt03/python-tests.txt` |
| `--help`, `--check-config` | `python run.py ...` | PASS, exit 0 sem dump | `bootstrap/help.txt`, `config.txt` |
| Falta de jogo | `python run.py` | PASS (exit 1), mensagem acionável | `bootstrap/missing-game.txt` |
| Auditoria de runtime | `python run.py --audit-runtime` | PASS, exit 0 | `bootstrap/runtime-audit.txt` |
| Smoke Vulkan | `python run.py --vulkan-smoke` | PASS, exit 0, readback 4096 B | `bootstrap/vulkan-smoke.txt` |
| Patch inválido | `bash build.sh` com patch sintético | PASS (exit 1), sem `--reject` | observado na sessão 02 |
| Suíte herdada | `runtime/tests` | **FAIL**, exit 1 (GoW/MediEvil) | `bootstrap/upstream-tests.txt` |

## Auditoria do dump

| Verificação | Entrada | Resultado | Evidência |
|---|---|---|---|
| Identificação | `sce_sys/param.sfo` + SHA-256 do eboot | `CUSA11875`, `01.07`, `06f143de…33e51` | `prompt03/manifest.json` |
| Container | header SELF | `0x0480`, não cifrado, não comprimido | `manifest.json` |
| Manifesto JSON | `python scripts/audit_game.py <dump> --out …` | PASS, exit 0 | `prompt03/manifest.json` |
| Sem dump / dump inválido | `audit_game.py` com caminho ausente | PASS (exit 1), sem traceback | `tests/test_audit_game.py` |
| Fixtures sintéticas | `tests/test_audit_game.py` | PASS, 16 casos, sem dados comerciais | `prompt03/python-tests.txt` |
| Rejeição da build | `python run.py --game-dir <dump>` | PASS (exit 1), fail-closed com hash | `bootstrap/dump-unvalidated.txt` |

## Pipeline de boot — exit codes reais

| Etapa | Comando | Exit | Observado |
|---|---|---|---|
| SELF → ELF | `prepare.py` | 0 | 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos |
| Link de módulos | `link_modules.py` | 0 | 209 native bindings; libc@0x62a0000, Fios2@0x63b0000 |
| Cobertura de imports | `cg-runtime --cpu-only --check-imports` | 1 | 679/988 resolvidos, 309 faltando |
| Cobertura com GPU | `cg-runtime --check-imports` | 1 | **811/988 resolvidos, 177 faltando** |
| **Boot real** | `cg-runtime boot-linked.bin --app0 <dump>` | **3** | GPU ok, 106 MB mapeados, 465.785 relocations; falha em `0x62c1264` |
| Reprodutibilidade | mesmo comando, 2 execuções | 3 / 3 | mesmo offset `0x62c1264` |

## Primeiro bloqueio

`guest 0x62c1264` = `libc.prx+0x21264` = função `abort` (`L1SBTkC+Cvw#D#A`).

```
55            push rbp
4889e5        mov rbp, rsp
cd44          int 0x44      <- gate de syscall PS4, sem handler no runtime
ba cccccccc   mov edx, 0xcccccccc
b9 0b0002a0   mov ecx, 0xa002000b
90            nop
0f0b          ud2           <- ponto de fault
```

Antes da instrumentação o log dizia `Fault: read access to ffffffffffffffff`, o que sugeria
erro de memória. Depois: `Blocker: guest executed a PS4 syscall gate (int 0x44)`.
Comparação em `prompt03/boot-01-first-fault.txt` e `prompt03/boot-02-blocker-named.txt`.

## Não executado — não inferir aprovação

| Item | Estado |
|---|---|
| Primeiro frame renderizado | **NÃO EXECUTADO** |
| Menu, intro, gameplay, interação | **NÃO EXECUTADO** |
| Áudio do jogo | **NÃO EXECUTADO** |
| Saves (formato e round-trip) | **NÃO EXECUTADO** — formato ainda desconhecido |
| Câmera, gyro, PS Move, PSVR | **NÃO EXECUTADO** — apenas imports presentes |
| Flicker, iluminação/sombras, VRAM/RAM, stutter | **NÃO EXECUTADO** |
| Mouse, captura de cursor | **NÃO EXECUTADO** |
| Outras GPUs além da NVIDIA | **NÃO EXECUTADO** |
| Pacote Windows em máquina limpa | **NÃO EXECUTADO** |

## Como repetir

```bash
# 1. Build e testes sem o jogo
bash build.sh && bash build.sh --test
python -m unittest discover -s tests -v

# 2. Manifesto do dump (somente leitura)
python scripts/audit_game.py gamedump/CUSA11875 --no-tree --out manifest.json

# 3. Prepare + link (escreve só em .cg/)
python -c "import sys;sys.path.insert(0,'runtime/scripts');
from pathlib import Path;from prepare import prepare;from link_modules import link;
prepare(Path('gamedump/CUSA11875'),Path('.cg/audit/prepared'));
link(Path('gamedump/CUSA11875'),Path('.cg/audit/prepared'),module_names=('libc.prx','libSceFios2.prx'))"

# 4. Cobertura de imports, sem executar guest
runtime/out/gpu/cg-runtime.exe .cg/audit/prepared/boot-linked.bin --check-imports

# 5. Boot real (esperado: exit 3 no bloqueio documentado)
runtime/out/gpu/cg-runtime.exe .cg/audit/prepared/boot-linked.bin \
  --app0 "$PWD/gamedump/CUSA11875" --user .cg/audit/run/user --timeout 25
```

## Classificação da suíte herdada vermelha

`runtime/tests` mantém falhas escritas para GoW III/MediEvil (FPS 120 vs 60, versão 2.1.3 vs
1.3.8, XML GoW ausente, perfil GoW inexistente, symlinks sem privilégio, driver Linux).
Não foram corrigidas: reescrever as expectativas transformaria regressões herdadas em falso
positivo. Falhas aceitáveis são tratadas caso a caso, com o motivo em `docs/DECISIONS.md`.
