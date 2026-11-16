# Estado do projeto

Atualizado: 2026-11-09 UTC, sessão de diagnóstico da tela branca. **O PROMPT 04 não atingiu
o critério: não existe primeira cena jogável demonstrada.** A cena 3D renderiza quando o boot a
alcança, mas o estado branco intermitente foi identificado: é o **title screen** do jogo
("Press ✕"), renderizado pelo guest e apresentado fielmente — não é defeito de apresentação.
Pintura, áudio e save/load não foram observados. Este documento descreve o que foi medido, não o
que se espera.

## Onde o port está

- Branch `audit/base`, HEAD `6a3ba2a` + mudanças desta sessão não commitadas (`run.py`,
  `tests/test_native.py`, scripts novos). Sem merge. Runtime do MediEvil vendorizado (base
  `424f3ea`).
- Build reproduzível: `bash build.sh` e `bash build.sh --test` (exit 0 na sessão 2026-11-01).
  **Atenção de ambiente:** o msys2 atualizado quebrou o início do runtime (ffmpeg ABI 62 → 63);
  usar `python3 scripts/make_runtime_bundle.py` ou restaurar o ffmpeg 8.1.1 antes de recompilar.
- **102 testes Python**, exit 0 (inclui smoke nativo via bundle).
- Dump `CUSA11875` (EU, APP_VER 01.07) identificado e auditado; pipeline executado até o boot.

## Estágios comprovadamente atingidos

|| Estágio | Evidência |
||---|---|
|| SELF → ELF | 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos |
|| Módulos ligados | 209 native bindings (libc, Fios2) |
|| Cobertura de imports | 811/988 (com shim GPU) |
|| Vulkan / janela | RTX 5060, Vulkan 1.4.357, swapchain, 327 HLE symbols |
|| Imagem mapeada | 106.136.876 bytes, 9 segmentos, 465.785 relocations aplicadas |
|| Memória guest | pools de 6 MiB + 128 MiB + 5.161.025.536 bytes |
|| Cadeia de apresentação | `Flip` → `PrepareFrame` → `vkQueuePresentKHR` = `Success` |
|| **Cena 3D renderizada** | **sim, estável a 30 FPS, quando o boot a alcança** |
|| **Title screen capturado** | **sim — estado `bright` = tela "Press ✕", display==output byte-idênticos** |
|| Áudio audível | **não** — runtime correto em todas as camadas; o guest entrega zeros |
|| Pintura | **não** — negativa por três caminhos de input |
|| Save/load | **não executado** |

## A tela branca, agora com captura (2026-11-09)

O estado `bright` intermitente foi capturado dentro do próprio estado (runner
`scripts/capture_bright_run.py`, 1ª tentativa, perfil isolado):

- `display` e `output` são **byte-idênticos** entre si (`7aaff933c47fa13f…`) e iguais às capturas
  antigas `pbc`/`paintc`/`p2c` — a imagem é o **title screen** (logo + "Press ✕" + PixelOpus,
  confirmado por inspeção visual do PNG).
- `DisplayOverride`/upscaler nunca participam (`Display: host buffer`: 0 ocorrências).
- 7.230 draws/frame **normalizados** nos dois estados — é a animação do título, não a cena
  oculta. A leitura anterior ("a cena renderiza e não chega ao swapchain") está refutada.
- A intermitência real: **chegar ao título é não-determinístico** (3 execuções sem input:
  2 caíram no título, 1 foi direto à cena) e o **press de cross chega ao guest e não avança o
  título** (`try5`, `pad read: buttons=0x4000` confirmado).

## Estado do jogo, medido por frame (histórico da sessão 2026-11-01)

`GOW3_FRAME_MAP=1` grava a grade de luminância 3×3 da imagem final por frame, com a contagem de
draws. Quatro execuções independentes:

| Execução | Entrada | Estado |
|---|---|---|
| `boot-135` | `cross` | black 1..586 → fade 591..616 → **scene 621..9021** |
| `boot-137` | `cross` (repetição) | black 1..511 → fade 516..556 → **scene 561..9006** |
| `run5-verify` | `cross` (a cada 10) | black 1..431 → fade 441..461 → **scene 471..9601** |
| `boot-140` | `cross` (controle) | black 1..441 → fade 446..491 → **bright 496..9661** |
| `boot-139` | `cross`, `options` no frame 461 | black 1..421 → fade 426..456 → **scene 461..24181** |
| `boot-136` | `cross`+`options` | black 1..411 → fade 416..461 → **bright 466..9041** |

O estado **não alterna dentro de uma execução** — uma vez alcançada a cena, ela permanece. Mas
**entre execuções não é determinístico**, e a causa **não é loading**: medindo o trabalho de GPU,
a execução que mostra a tela clara executa **o mesmo** número de draws por frame (36.148 por
amostra de 20 frames) e produz **uma única imagem** repetida, enquanto a cena produz centenas.
**Leitura da época ("defeito de apresentação") refutada em 2026-11-09:** a captura do estado
branco mostra que a imagem única é o **title screen** e que ele chega ao swapchain byte-idêntico
— ver "A tela branca, agora com captura" acima. Ver `scripts/frame_workload.py` e
`docs/MEMORY_AUDIT.md`.

Custo da instrumentação: **3,09 ms por amostra**, com o jogo mantendo 30 FPS. Não altera o estado.

## O que funciona, e o que não

**Funciona:** boot completo sem `STOP` de import; cena 3D a 30 FPS (quando alcançada); input de
gamepad move a câmera (99,94% dos pixels diferem do controle no mesmo frame); frame pacing
estável (mediana 33,34 ms, p99 34,38 ms); title screen e menu alcançados.

**Não funciona / não observado:** sair do title screen por input scriptado (cross entregue e
confirmado no pad, sem avanço — `try5`); pintura (R2, stick e sensor, todos negativos); áudio;
save/load; mouse como eixo direito; pausa.

## O que NÃO foi feito e por quê

Shaders cold/warm, flicker, iluminação, VRAM e distribuição Windows continuam sem auditoria
completa. Frame pacing tem uma medição única; flicker e iluminação exigem comparação visual que
ainda não existe. Registrar isso como "feito" seria inflação de progresso.

## Estado de verificação

| Item | Estado |
|---|---|
| Build + testes nativos | PASSA, exit 0 (sessão 2026-11-01; msys2 atualizado exige o bundle de DLLs) |
| Suíte Python | PASSA, **102 testes**, exit 0 (2026-11-09) |
| Boot | exit 124 (timeout), sem fault e sem `STOP` de import |
| Frame / cena 3D | **EXECUTADO, estável a 30 FPS quando alcançada** |
| Captura do estado `bright` | **EXECUTADO** — title screen, display==output byte-idênticos |
| Menu principal | Alcançado por draws; **não navegado** |
| Pintura, áudio, save/load | **NÃO VERIFICADO** |
| Suíte herdada `runtime/tests` | vermelha por expectativas de GoW/MediEvil, não corrigida |

## Próxima ação

Descobrir o que o title screen aceita para avançar: repetir o press ancorado com janela curta
(`title_press_test.py --settle 3`), depois auditar o caminho Bink (vídeo de abertura que nunca
carrega) e o sensor/PS Move como alternativas. Critério completo em `docs/HANDOFF.md`.
