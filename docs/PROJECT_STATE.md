# Estado do projeto

Atualizado: 2026-11-01 UTC, sessão de instrumentação de estado por frame. **O PROMPT 04 não atingiu
o critério: não existe primeira cena jogável demonstrada.** A cena 3D renderiza, é estável e
responde a input de câmera, mas pintura, áudio e save/load não foram observados. Este documento
descreve o que foi medido, não o que se espera.

## Onde o port está

- Branch `bootstrap/windows`, runtime do MediEvil vendorizado (base `424f3ea`). Sem merge.
- Build reproduzível: `bash build.sh` e `bash build.sh --test`, ambos exit 0.
- **86 testes Python**, exit 0. Smoke sem dump funcionando.
- Dump `CUSA11875` (EU, APP_VER 01.07) identificado e auditado; pipeline executado até o boot.

## Estágios comprovadamente atingidos

| Estágio | Evidência |
|---|---|
| SELF → ELF | 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos |
| Módulos ligados | 209 native bindings (libc, Fios2) |
| Cobertura de imports | 811/988 (com shim GPU) |
| Vulkan / janela | RTX 5060, Vulkan 1.4.357, swapchain, 327 HLE symbols |
| Imagem mapeada | 106.136.876 bytes, 9 segmentos, 465.785 relocations aplicadas |
| Memória guest | pools de 6 MiB + 128 MiB + 5.161.025.536 bytes |
| Cadeia de apresentação | `Flip` → `PrepareFrame` → `vkQueuePresentKHR` = `Success` |
| **Cena 3D renderizada** | **sim, estável a 30 FPS, 9.600+ frames** |
| Áudio audível | **não** — runtime correto em todas as camadas; o guest entrega zeros |
| Pintura | **não** — negativa por três caminhos de input |
| Save/load | **não executado** |

## Estado do jogo, medido por frame

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
**entre execuções não é determinístico**: com a mesma entrada `cross`, uma execução terminou em
`bright` (`boot-140`) em vez de `scene`. A tela `bright` é idêntica à observada com `options`, e
aparece **sem nenhum input**, então não pode ser atribuída ao OPTIONS. Isso corrige pela metade a
hipótese de "instabilidade" de sessões anteriores: o ponto de parada importa, mas nem toda execução
chega à cena.

Custo da instrumentação: **3,09 ms por amostra**, com o jogo mantendo 30 FPS. Não altera o estado.

## O que funciona, e o que não

**Funciona:** boot completo sem `STOP` de import; cena 3D a 30 FPS; input de gamepad move a câmera
(99,94% dos pixels diferem do controle no mesmo frame); frame pacing estável (mediana 33,34 ms,
p99 34,38 ms); menu principal alcançado (medido por contagem de draws).

**Não funciona / não observado:** pintura (R2, stick e sensor, todos negativos); áudio; save/load;
mouse como eixo direito; pausa.

## O que NÃO foi feito e por quê

Shaders cold/warm, flicker, iluminação, VRAM e distribuição Windows continuam sem auditoria
completa. Frame pacing tem uma medição única; flicker e iluminação exigem comparação visual que
ainda não existe. Registrar isso como "feito" seria inflação de progresso.

## Estado de verificação

| Item | Estado |
|---|---|
| Build + testes nativos | PASSA, exit 0 |
| Suíte Python | PASSA, 86 testes, exit 0 |
| Boot | exit 124 (timeout), sem fault e sem `STOP` de import |
| Frame / cena 3D | **EXECUTADO, estável a 30 FPS** |
| Menu principal | Alcançado por draws; **não navegado** |
| Pintura, áudio, save/load | **NÃO VERIFICADO** |
| Suíte herdada `runtime/tests` | vermelha por expectativas de GoW/MediEvil, não corrigida |

## Próxima ação

Ancorar os testes de gameplay ao mapa de estado: rodar com `GOW3_FRAME_MAP=1`, ler a faixa `scene`
com `python scripts/frame_states.py <log>`, e escolher os frames de captura **dentro** dela, na
mesma execução. Critério completo em `docs/HANDOFF.md`.
