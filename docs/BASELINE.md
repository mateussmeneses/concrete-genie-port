# Baseline — build e testes reproduzíveis (PROMPT 02)

Medido em 2026-10-31 UTC, Windows 11 build 26300, MSYS2 CLANG64, Intel i7-14650HX,
NVIDIA RTX 5060 Laptop. **Sem dump de Concrete Genie.** Nada aqui demonstra boot do jogo.

## Pré-requisitos (MSYS2 CLANG64)

```bash
pacman -S --needed git patch \
  mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python} \
  mingw-w64-clang-x86_64-{vulkan-headers,vulkan-loader,vulkan-memory-allocator,glslang} \
  mingw-w64-clang-x86_64-{sdl3,fmt,boost,robin-map,xxhash,ffmpeg,zydis} \
  mingw-w64-clang-x86_64-{spirv-tools,spirv-headers,spirv-cross}
```

O `pacman` acima é a lista de instalação (não foi executado nesta sessão; as versões abaixo
são as que já estavam presentes). Versões medidas: clang 22.1.7, Vulkan headers/loader
pkg-config 1.4.350, SDL3 3.4.10, libavcodec 62.28.101, fmt 12.1.0, Python 3.14 (Windows).

## Submódulos fixados

`git submodule status --recursive` (evidência: `docs/evidence/bootstrap/submodules.txt`):

```
c64f093404125e960813f95f1996c14780f0dd69 runtime/gpu/third_party/fsr-vulkan
f1cc2ae15e53a861a874c3034aae6798fde194ab runtime/gpu/third_party/imgui
e046b69a3736d314fad813e159b1c192eaef92cd runtime/gpu/third_party/magic_enum
2948eebafc5b9f1c69bebed80333e403a09bd62d runtime/gpu/third_party/miniz
cd6bad3cad2e07a3e277c23d2b1f065320024717 runtime/gpu/third_party/xbyak
efca2e3af35562a09a9bb6deed90e45b4b824dc4 runtime/third_party/LibAtrac9
```

Base upstream do runtime vendorizado: MediEvil `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94`.

## Comandos e resultados observados

| # | Comando (MSYS2 CLANG64) | Exit | Observado |
|---|---|---|---|
| 1 | `bash build.sh` | 0 | Submodules ok; 2 patches FSR aplicados; `cg-runtime.exe`, `cg-gpu-check.exe` gerados |
| 2 | `bash build.sh` (repetição) | 0 | "Already applied" nos 2 patches; idempotente, sem reaplicar |
| 3 | `bash build.sh` com patch inválido injetado | 1 | "Patch applies neither forward nor in reverse"; build parou, sem `--reject` |
| 4 | `bash build.sh --test` | 0 | services-test, pad-map-test, aliasing, depth-stencil-state, async-compiler, warmup-inbox executados |
| 5 | `python -m unittest discover -s tests -v` | 0 | 13 testes, OK |
| 6 | `python run.py --help` | 0 | Ajuda completa, sem exigir jogo ou build |
| 7 | `python run.py --check-config` | 0 | JSON resolvido + "game support NOT VALIDATED" |
| 8 | `python run.py` | 1 | "No game configured. Set CG_GAME_DIR ou --game-dir" |
| 9 | `python run.py --game-dir /c/.../gamedump` | 1 | "No eboot.bin in <path>"; caminho MSYS traduzido corretamente |
| 10 | `python run.py --audit-runtime` | 0 | "Runtime audit PASS"; hooks e patches de título desativados |
| 11 | `python run.py --vulkan-smoke` | 0 | NVIDIA RTX 5060; submission + readback de 4096 bytes PASS |
| 12 | `python -m unittest discover -s runtime/tests` | 1 | Suíte herdada: falhas de expectativas GoW/MediEvil (não corrigida) |

Evidências brutas em `docs/evidence/bootstrap/`: `build.txt`, `build-test.txt`,
`python-tests.txt`, `help.txt`, `config.txt`, `missing-game.txt`, `missing-eboot.txt`,
`runtime-audit.txt`, `vulkan-smoke.txt`, `submodules.txt`, `upstream-tests.txt`.

## O que é reproduzível e o que não é

- Reproduzível: a sequência acima a partir de um checkout limpo com submódulos inicializados.
  Os patches de terceiros são aplicados de forma idempotente e o build falha fechado.
- **Não** é reprodutibilidade bit a bit: não há snapshot de pacotes congelado nem comparação
  binária entre máquinas. O SHA-256 dos executáveis desta sessão está em
  `docs/evidence/bootstrap/artifacts.json`.

## Correções de compilação aplicadas nesta etapa

1. **Patches nunca aplicavam em checkout limpo.** `build.sh` passava `$PWD` (estilo MSYS,
   `/c/...`) a um `git` nativo que não resolve esse caminho. O `apply --reverse --check`
   falhava por "can't open patch" e era lido como "já aplicado", pulando `apply`. Corrigido
   com `cygpath -m` e com um `apply --check` que interrompe o build quando o patch não casa
   em nenhuma direção.
2. **`windres` não criava arquivo temporário.** O ambiente herdava `TMPDIR=/tmp` (MSYS), que
   binários nativos do Windows não resolvem — o build quebrava ao recompilar o `.rc`.
   Corrigido exportando `TMP`/`TEMP`/`TMPDIR` para `runtime/out/tmp`.
3. **`services-test` e `pad-map-test` não linkavam.** `compat_win.c` chama `timeBeginPeriod`
   e os alvos não ligavam `winmm`. `winmm` adicionado apenas a esses alvos e a
   `mp3/videodec/services`, sem alterar o runtime.
4. **`.gitattributes` não versionado.** Com `core.autocrlf=true`, os `.patch` eram convertidos
   para CRLF embora os alvos sejam LF, o que os tornava inaplicáveis. O arquivo (com
   `*.patch text eol=lf`) passou a ser rastreado.

Nenhuma correção usou `--reject`, filtro de teste, supressão de exit code ou relaxamento de
`-Werror`.
