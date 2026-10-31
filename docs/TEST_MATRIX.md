# Matriz de testes — baseline original

Executado em 2026-10-31 UTC, MediEvil 424f3ea8dbdcb02754a31e5225ef42e2f77f8e94. Nenhum teste com Concrete Genie. Evidências em `docs/evidence/` (caminhos abaixo relativos a este diretório).

## Ambiente medido

Windows 11 Home Single Language 10.0.26300 build 26300; Intel Core i7-14650HX; RAM física informada 33.937.809.408 bytes (31,61 GiB). NVIDIA GeForce RTX 5060 Laptop GPU: driverInfo Vulkan 621.01, API 1.4.357. Intel integrada: RaptorLake-S Mobile, driverInfo 101.7088, API 1.4.323. Consultas Win32 e Vulkan foram preservadas separadamente; não confundir o número Win32 do driver com driverInfo Vulkan. CLANG64 clang 22.1.7, headers/loader pkg-config Vulkan 1.4.350, SDL3 3.4.10, libavcodec 62.28.101, fmt 12.1.0; Python Windows 3.14. Evidência: os.json, cpu.json, ram.json, gpu.json, vulkan-summary.txt, msys-packages.txt. Versões de SDK e API do dispositivo são diferentes por definição.

| Verificação | Comando/entrada | Resultado observado | Evidência / limite |
|---|---|---|---|
| SHAs/submódulos | git rev-parse HEAD; submodule update --init --recursive; submodule status | PASS, seis submódulos inicializados | medievil-head.txt, medievil-submodules.txt; Matterfall não inicializado pois comparação só lê fontes vendorizadas |
| FSR patches | git ls-files --eol; git apply --check para cada patch antes do build | PASS; i/lf w/crlf, ambos aplicáveis | line-endings.txt; build original aplicou os patches esperados |
| Build runtime original | CXXFLAGS com forced includes; bash build.sh | PASS, exit 0; runtime, gpu-check e play produzidos | build.txt, gpu-build.log, build-artifacts.json; não é prova bit a bit nem jogo |
| Suíte Python upstream | python -m unittest discover -s tests -v | FAIL: 112 testes, 6 failures, 7 errors, 29 skips, exit 1 (70 passaram) | python-tests.txt; não corrigida nem filtrada para parecer verde |
| Build unitários nativos | ninja -C out/gpu services-test pad-map-test aliasing-test depth-stencil-state-test async-compiler-test warmup-inbox-test | FAIL, exit 1; services/pad-map não linkam timeBeginPeriod | native-tests.txt; compat_win.c chama função, alvos não linkam winmm; runtime principal linka |
| Unitários GPU independentes | ninja dos quatro últimos alvos, seguido de execução de cada .exe | PASS: aliasing, depth-stencil-state, async-compiler, warmup-inbox; quatro exits 0 | gpu-unit-tests.txt; CMake usa -UNDEBUG, confirmado; depth-test-compile.txt |
| Runtime --help | Start-Process medievil-runtime.exe --help, Wait/PassThru, stdout/stderr separados | FAIL como interface help, exit 1: cannot open boot file | runtime-help.*; flag não implementada como ajuda, não é crash de boot |
| Vulkan sem guest | Start-Process medievil-runtime.exe --vulkan-only, Wait/PassThru | PASS, exit 0; NVIDIA, command submission + 4096-byte readback | vulkan-smoke.*; não valida renderer/shaders reais |
| Capacidades GPU | medievil-gpu-check.exe | PASS, exit 0; supports live presets | gpu-check.txt; consulta blit formats, não gameplay |
| Loader sintético via test_probe | incluído na suíte Python | NÃO EXECUTADO: EXE out/gow3-probe inexistente | skips; não redirecionado ao runtime Windows nesta auditoria |
| Dump, imports e build alvo | nenhum dump fornecido/inspecionado | NÃO VALIDADO | TITLE_ID, APP_VER e SHA-256 reais ausentes |
| Boot/menu/gameplay/áudio/saves do jogo | — | NÃO EXECUTADO | sem dump, nenhuma aprovação inferida |
| Flicker/luz/sombras/VRAM/RAM/stutter/cache frio-quente/mouse/gyro/menu | — | NÃO EXECUTADO | prioridade para próximas etapas com conteúdo real |
| Outras GPUs | Intel enumerada somente | NÃO EXECUTADO | não extrapolar smoke NVIDIA |
| Pacote Windows limpo | package.sh não executado | NÃO EXECUTADO | build na máquina de desenvolvimento não prova DLL closure/distribuição |

## Classificação das falhas Python

Duas errors são WinError 1314 ao criar symlink (mods e fixture de driver Linux). Quatro errors são XML GoW ausente; uma é perfil GoW None indexado. Das seis failures: duas esperam 120 FPS onde baseline usa 60; uma espera versão GoW 2.1.3 em vez de MediEvil 1.3.8; uma é wrapper shell de mods com exit 1 em vez de 7; uma é descoberta de driver Linux; uma passa perfil GoW ausente a eboot_matches, que retorna True. Essas explicações vêm de mensagens e leitura dos testes; a falha de shell não foi diagnosticada além do observado. Nenhuma foi corrigida na auditoria.

## Comandos para repetir

No checkout MediEvil, com Python Windows: `python -m unittest discover -s tests -v`. No CLANG64, após build: `ninja -C out/gpu aliasing-test depth-stencil-state-test async-compiler-test warmup-inbox-test`, depois executar cada binário em out/gpu. Para smoke no PowerShell, adicionar C:\msys64\clang64\bin ao PATH e usar `Start-Process -FilePath <caminho absoluto do runtime> -ArgumentList '--vulkan-only' -WindowStyle Hidden -Wait -PassThru` com redirecionamento para capturar ExitCode. O executável GUI não foi observado de forma confiável com chamada direta do PowerShell; os resultados finais usam espera explícita.

Testes iniciais adicionais propostos (NÃO EXECUTADOS): novo harness do loader Windows com fixtures sintéticas; contratos de imports ausentes, TLS/ABI e memória; gates negativos de build/hash/SSE4a/NpToolkit2; fixtures link_modules (não só link_libc); input/gyro e saves em temporários. Primeiro resolver os dois targets de teste que não linkam, em intervenção separada.
