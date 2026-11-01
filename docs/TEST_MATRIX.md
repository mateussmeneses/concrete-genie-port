# Matriz de testes

Atualizado: 2026-10-31 UTC. Dump local `gamedump/CUSA11875` inspecionado em modo somente
leitura. **Nenhum boot, menu ou gameplay foi executado.** Evidências em `docs/evidence/`
(caminhos relativos a este diretório).

## Ambiente medido

Windows 11 Home Single Language 10.0.26300; Intel Core i7-14650HX; 33.937.809.408 bytes de
RAM (31,61 GiB). NVIDIA GeForce RTX 5060 Laptop GPU (Vulkan driverInfo 621.01, API 1.4.357);
Intel RaptorLake-S integrada (driverInfo 101.7088, API 1.4.323). MSYS2 CLANG64 clang 22.1.7,
Vulkan 1.4.350 (pkg-config), SDL3 3.4.10, libavcodec 62.28.101, fmt 12.1.0, Python 3.14.
Evidências: `evidence/os.json`, `cpu.json`, `ram.json`, `gpu.json`, `vulkan-summary.txt`,
`msys-packages.txt`.

## Build e testes do projeto (PROMPT 02)

| Verificação | Comando/entrada | Resultado | Evidência / limite |
|---|---|---|---|
| Submódulos | `git submodule status --recursive` | PASS, seis submódulos no SHA fixado | `bootstrap/submodules.txt` |
| Patches idempotentes | `bash build.sh` duas vezes | PASS: aplica na 1ª, "Already applied" na 2ª | `bootstrap/build.txt` |
| Patch inválido falha fechado | patch sintético sem contexto | PASS (exit 1 esperado), mensagem explícita, sem `--reject` | observado nesta sessão |
| Build nativo | `bash build.sh` | PASS, exit 0: `cg-runtime.exe`, `cg-gpu-check.exe` | `bootstrap/build.txt` |
| Testes nativos | `bash build.sh --test` | PASS, exit 0: services, pad-map, aliasing, depth-stencil-state, async-compiler, warmup-inbox | `bootstrap/build-test.txt` |
| Suíte Python do projeto | `python -m unittest discover -s tests -v` | PASS: 14 testes, exit 0 | `bootstrap/python-tests.txt` |
| `--help` sem jogo/build | `python run.py --help` | PASS, exit 0 | `bootstrap/help.txt` |
| Validação de config | `python run.py --check-config` | PASS, exit 0, "NOT VALIDATED" | `bootstrap/config.txt` |
| Config inválida | JSON malformado, chave extra, valor vazio | PASS: exit 1, sem traceback | `test_bootstrap.py` |
| Falta o jogo | `python run.py` | PASS (exit 1 esperado), mensagem acionável, nenhum estado criado | `bootstrap/missing-game.txt` |
| Falta `eboot.bin` | `--game-dir` apontando para pasta vazia | PASS (exit 1), caminho MSYS `/c/...` traduzido | `bootstrap/missing-eboot.txt` |
| Título desconhecido | `inspect_build` com `CUSA99999` | PASS: rejeitado, sem patch | `test_bootstrap.py` |
| Build não registrada (US) | fixture `CUSA11834` sintética | PASS: rejeitado, SHA-256 exibido, nada criado | `test_candidate_is_never_accepted_without_a_verified_build` |
| **Build não registrada (EU, real)** | `python run.py --game-dir gamedump/CUSA11875` | PASS (exit 1 esperado): recusa com `APP_VER=01.07` e SHA-256 real; dump inalterado | `bootstrap/dump-unvalidated.txt` |
| Candidato EU reconhecido | `inspect_build` com SFO `CUSA11875`/`01.07` | PASS: título reconhecido, build ainda recusada | `test_eu_candidate_is_recognised_but_still_unvalidated` |
| Isolamento de saves/cache | fixture verificado + mocks | PASS: save por TITLE_ID, GPU por build, sem `--patches` | `test_verified_fixture_routes_preparation_and_isolates_saves_from_cache` |
| Sobreposição dump/dados | `--data-dir` em `game_dir`/`references` | PASS: rejeitado | `test_dump_and_data_must_not_overlap` |
| Caminho MSYS | `--game-dir /c/...` | PASS: traduzido para `C:/...` | `test_msys_style_paths_are_translated` |
| Auditoria de runtime | `python run.py --audit-runtime` | PASS, exit 0; hooks e patch sites desativados | `bootstrap/runtime-audit.txt` |
| Smoke Vulkan sem guest | `python run.py --vulkan-smoke` | PASS, exit 0; submission + readback 4096 B | `bootstrap/vulkan-smoke.txt` |
| Suíte herdada | `python -m unittest discover -s runtime/tests` | **FAIL**, exit 1: expectativas GoW/MediEvil | `bootstrap/upstream-tests.txt` |

## Inspeção do dump (somente leitura)

| Item | Valor verificado |
|---|---|
| `TITLE_ID` / `TITLE` | `CUSA11875` / `Concrete Genie` |
| `APP_VER` / `VERSION` | `01.07` / `01.00` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` |
| `CATEGORY` | `gp` |
| `eboot.bin` | 108.601.759 bytes, magic SELF `4F 15 3D 1D` |
| `eboot.bin` SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` |
| Engine | UE4 (`ue4commandline.txt` → `ConcreteGenie.uproject`) |
| Middleware | Bink 2 (`bink2ps4.prx`, `binkpluginps4.prx`) |
| Módulos | 12 em `sce_module/` (libc, Fios2, NpToolkit2, JobManager, AudioLatencyEstimation, Face, FaceTracker, Hand, HandTracker, HeadTracker, S3DConversion, Smart) |

Integridade: o SHA-256 do `eboot.bin` foi recalculado depois da execução do pipeline e não
mudou; nenhum arquivo do dump teve mtime alterado. O diretório de estado (`.cg/`) não recebeu
conteúdo novo.

## Não executado (não inferir aprovação)

| Item | Estado |
|---|---|
| Descriptografia/descompressão SELF → ELF | NÃO EXECUTADO |
| Imports/NIDs reais, relocations, TLS dos PRX | NÃO EXECUTADO |
| Boot do eboot, loader com conteúdo real | NÃO EXECUTADO |
| Menu, gameplay, áudio do jogo, saves do jogo | NÃO EXECUTADO |
| Pintura, gyro, câmera, PS Move, PSVR | NÃO EXECUTADO |
| Flicker, iluminação/sombras, VRAM/RAM, stutter, cold/warm cache | NÃO EXECUTADO |
| Mouse, captura de cursor, mapeamento de input real | NÃO EXECUTADO |
| Outras GPUs além da NVIDIA enumerada | NÃO EXECUTADO |
| Pacote Windows em máquina limpa | NÃO EXECUTADO (`package.sh` ainda é de MediEvil) |

## Como repetir

```bash
# MSYS2 CLANG64, na raiz do projeto
bash build.sh
bash build.sh --test
python -m unittest discover -s tests -v
python run.py --help
python run.py --check-config
python run.py --audit-runtime
python run.py --vulkan-smoke
python run.py                                  # sem jogo: deve falhar com mensagem acionável
python run.py --game-dir C:/caminho/CUSA11875  # deve recusar a build, exit 1
```

Os cinco primeiros e os três de smoke não exigem arquivo comercial. O último exige o dump e
**deve continuar recusando** até que uma auditoria registre a build.

## Classificação da suíte herdada vermelha

`runtime/tests` mantém falhas de expectativas escritas para GoW III/MediEvil (FPS 120 vs 60,
versão 2.1.3 vs 1.3.8, XML GoW ausente, perfil GoW inexistente, symlinks sem privilégio,
descoberta de driver Linux). Não foram corrigidas: reescrever essas expectativas para ficar
verde transformaria regressões herdadas em falso positivo.
