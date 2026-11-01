# Auditoria do dump — CUSA11875

Data: 2026-10-31 UTC. Dump local `gamedump/CUSA11875` (25 GB), inspecionado em modo somente
leitura. Nenhum binário comercial entrou no índice do Git.

**Resultado: a build foi identificada e o código guest executou; nenhum frame foi produzido.**
O primeiro bloqueio observável é `abort()` da libc, que contém o gate de syscall PS4
`INT 0x44` — instrução que o runtime não intercepta.

## Identificação verificada

| Campo | Valor | Fonte |
|---|---|---|
| `TITLE_ID` | `CUSA11875` | `sce_sys/param.sfo` |
| `TITLE` | `Concrete Genie` | `sce_sys/param.sfo` |
| `APP_VER` | `01.07` | `sce_sys/param.sfo` |
| `VERSION` | `01.00` | `sce_sys/param.sfo` |
| `CONTENT_ID` | `EP9000-CUSA11875_00-CONCRETEGENIE000` | `sce_sys/param.sfo` |
| `CATEGORY` | `gp` | `sce_sys/param.sfo` |
| `eboot.bin` | 108.601.759 bytes | `stat` |
| `eboot.bin` SHA-256 | `06f143de47f23a3ba0506e642148e2a553465bcf1e604d986ba246e5fb133e51` | `sha256sum` |
| Header SELF | `0x0480` (**não** cifrado, **não** comprimido) | header SELF |
| Entry point | `0x37d58d0` | `prepare.py` |
| Imagem mapeada | 103.382.639 bytes, 9–10 segmentos | `analysis.json` |

O dump é a **edição europeia**. `CUSA11834` (US), citada no playbook, nunca foi vista em
dump e permanece apenas candidata documental.

## Engine e middleware — pelos arquivos do dump

| Sinal | Evidência |
|---|---|
| Unreal Engine 4 | `ue4commandline.txt` → `../../../ConcreteGenie/ConcreteGenie.uproject` |
| Conteúdo empacotado | `concretegenie/content/paks/concretegenie-ps4.pak` |
| Bink 2 (vídeo) | `prx/bink2ps4.prx`, `prx/binkpluginps4.prx`, `movies/*.bk2` |
| Áudio | `libSceAjm` (17 imports), `libSceAudioOut`, `libSceAudio3d`, `libSceNgs2` |
| Módulos em `sce_module/` | 12 arquivos; `libc`, `libSceFios2`, `libSceNpToolkit2`, `libSceJobManager`, `libSceAudioLatencyEstimation`, `libSceS3DConversion`, `libSceSmart` e os quatro de rastreamento (`Face`, `FaceTracker`, `Hand`, `HandTracker`, `HeadTracker`) |

## Imports — medidos, não estimados

988 imports em 58 bibliotecas (tabela completa em `evidence/prompt03/manifest.json`).

| Biblioteca | Imports | Resolvido pelo runtime? |
|---|---|---|
| `libSceGnmDriver` | 113 | sim, pelo shim GPU (Vulkan) |
| `libSceNpToolkit2` | 79 | **não** |
| `libScePosix` | 64 | sim (canonicalizado para `libkernel`) |
| `libSceNet` | 37 | sim |
| `libSceFios2` | 33 | sim |
| `libSceHmd` | 22 | **não** |
| `libSceHttp` | 22 | sim |
| `libSceVideoOut` | 19 | sim |
| `libc` | 154 | sim (parcial) |
| `libkernel` | 89 | sim |

Cobertura real, medida com `--check-imports` no runtime de verdade:

| Modo | Resolvidos | Faltando | Exit |
|---|---|---|---|
| `--cpu-only` | 679 / 988 | 309 | 1 |
| com shim GPU | **811 / 988** | **177** | 1 |

Os 177 restantes concentram-se em: `libSceNpToolkit2` (79), `libSceHmd` (22),
`libSceAudio3d` (14), `libSceVrTracker` (11), `libSceSocialScreen` (7), `libSceCamera` (7),
`libSceHmdSetupDialog` (6), `libSceVrServiceDialog` (5), `libSceMove` (5).
Tabela completa em `evidence/prompt03/imports-gpu-by-library.txt`.

## Primeiro boot — o que realmente aconteceu

Comando:

```bash
cg-runtime.exe .cg/audit/prepared/boot-linked.bin \
  --app0 C:/projetos/concrete-genie-port/gamedump/CUSA11875 \
  --user .cg/audit/run/user --timeout 25
```

Estágios atingidos, na ordem em que o log os mostra (`evidence/prompt03/boot-01-first-fault.txt`):

1. Host + Vulkan: NVIDIA RTX 5060, Vulkan 1.4.357, swapchain Fifo, janela criada.
2. GPU: 327 HLE symbols, "window and Vulkan presenter ready", FSR 3.1 disponível.
3. Preparação: 106.136.876 bytes mapeados, 9 segmentos, **465.785 relocations aplicadas**.
4. Módulos: `libc.prx@0x62a0000`, `libSceFios2.prx@0x63b0000`, 209 native bindings.
5. Memória guest: pools de 128 MiB e 5.161.025.536 bytes criados com sucesso.
6. **Falha**: `read access to ffffffffffffffff at guest offset 0x62c1264`.

### Ponto de falha e causa raiz

`0x62c1264 − 0x62a0000` = offset `0x21264` em `libc.prx`, dentro do símbolo
`L1SBTkC+Cvw#D#A`, cujo nome semântico é **`abort`**. Os bytes reais são:

```
55            push rbp
4889e5        mov rbp, rsp
cd44          int 0x44          <- gate de syscall PS4
ba cccccccc   mov edx, 0xcccccccc
b9 0b0002a0   mov ecx, 0xa002000b
90            nop
0f0b          ud2               <- aqui o guest faulta
```

`abort` está marcado como **exportado por libc** (não é um import pendente), então o linker
o ligou ao código real da libc. O `INT 0x44` é o mecanismo de syscall do PS4: o runtime não
o intercepta, a execução segue para `ud2` e o handler de fault reporta o endereço inválido
em vez da causa.

Duas consequências, ambas verificadas:

- **Não sabemos ainda por que `abort` foi chamado.** O `ecx=0xa002000b` é o código de erro do
  PS4 guardado como argumento, não a razão original — essa informação foi perdida quando o
  programa abortou.
- `rax=0x8002000c` no registro de fault, `rsi=0x200000000`, `rdi=0x19fe8a8` no momento.

Reprodutibilidade: duas execuções independentes produziram o **mesmo offset** `0x62c1264` e
o mesmo exit code 3 (`boot_rep1`, `boot_rep2`).

## Ausência de evidência (não inferir)

| Item | Estado |
|---|---|
| Primeiro frame renderizado | **NÃO EXECUTADO** |
| Menu, intro, gameplay | **NÃO EXECUTADO** |
| Uso real de câmera / gyro / PS Move / PSVR | **NÃO EXECUTADO** — apenas imports presentes |
| Formato de save | **DESCONHECIDO** — nenhum arquivo de save inspecionado |
| Áudio reproduzido | **NÃO EXECUTADO** |
| Flicker, iluminação, VRAM, frame pacing | **NÃO EXECUTADO** |

## Ferramenta de auditoria

`scripts/audit_game.py` gera o manifesto JSON (`--out`, `--no-tree`). Somente leitura: não
copia binários e não escreve no dump. Sem dump, os testes rodam contra fixtures sintéticas.
Testes: `tests/test_audit_game.py` (16 casos). Manifesto real: `evidence/prompt03/manifest.json`.
