# Comparação seletiva: Matterfall e MediEvil

Inspeção estática em 2026-10-31. Nenhum runtime, jogo ou teste foi executado nesta comparação; nenhum código das referências foi alterado. Não existe build Concrete Genie validada nesta evidência.

## Fontes fixadas

- Matterfall: `afaa2b7e212437f04baff709f983a121477ffcdf`, checkout `references/matterfall`, [árvore](https://github.com/bc160201983/Matterfall-PC-port/tree/afaa2b7e212437f04baff709f983a121477ffcdf).
- MediEvil: `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94`, checkout `references/medievil`, [árvore](https://github.com/bc160201983/medievil_2019_pc_port/tree/424f3ea8dbdcb02754a31e5225ef42e2f77f8e94).
- Prefixo `M/` abaixo: `references/matterfall/gow3_pc/`; prefixo `E/`: `references/medievil/`. Linhas correspondem aos SHAs acima.
- `M/gpu/VENDOR.txt:1` registra shadPS4 `b4e7ae776071ceb1dd35004577a8719481e1d258` e GPL-2.0-or-later. O diretório `gow3_pc` de Matterfall é código versionado no próprio repositório, não um submódulo do runtime.

## O que foi compartilhado, e os limites

| Componente | Evidência no código | Adequação para Concrete Genie / risco |
|---|---|---|
| Nomes de imports | `scripts/gen_import_names.py` tem blob Git idêntico nos dois projetos: `f40c752abf7ca6767f3e61db1d3648fffd83ea4a` | Ferramenta reutilizável; identidade do arquivo não prova cobertura de imports do novo jogo nem a direção da transferência. |
| Loader/linker SELF/ELF | Ambos têm `scripts/prepare.py:27` (`parse_self`) e `scripts/link_modules.py:97` (`link`), módulos padrão libc/Fios2 na linha 21. Matterfall acrescenta argumento `executable` a `link` | Arquitetura compartilhada, arquivos diferentes. Revalidar relocations, TLS e módulos do dump alvo; não substituir arquivos integralmente. |
| Retirada adiada de mutexes/conditions | `M/src/runtime_mutex.c:105` atribui explicitamente a MediEvil; `retire` na linha 112 e `mutex_destroy` na 120. `E/src/runtime_mutex.c:104` contém ring equivalente, com implementação diferente | Candidato genérico de estabilidade; ring adia liberação, não prova ausência de races. Regressão de concorrência necessária. |
| CMask expandido | `M/gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp:4131` preenche metadados; comentário em 4138 atribui a MediEvil. Contraparte `E/.../buffer_cache.cpp:636` | Candidato de correção GPU, dependente do modelo de memória expandida do renderer. Não constitui prova visual do novo jogo. |
| Views/clears 3D como slices 2D | `M/.../texture_cache/texture_cache.cpp:919` e `M/.../renderer_vulkan/vk_runtime.cpp:745` atribuem a MediEvil; `E/.../renderer_vulkan/vk_runtime.cpp:717` | Correção potencialmente genérica de Vulkan; testar formatos, depth slices e clears. |
| Barriers em lotes menores | `M/.../renderer_vulkan/vk_runtime.cpp:999` / `FlushBarriers`, contraparte `E/.../vk_runtime.cpp:926`; comentários atribuem a MediEvil e limitam os lotes | Candidato para estabilidade de drivers. Relatos de crashes no comentário são evidência upstream, não resultados medidos nesta máquina. |
| Subalocação de imagens | `M/.../texture_cache/image.cpp:395` aceita `GOW3_IMAGE_SUBALLOC`; `E/.../image.cpp:261` mantém default condicionado ao fabricante | Há divergência de política: Matterfall usa subalocação por padrão para todas as GPUs. Não transportar a conclusão sobre AMD sem regressão própria. |
| Serviços UE4/offline | `M/src/runtime_extra.c:574` registra helpers URI reais; `E/src/runtime_extra.c:465` ainda mapeia Parse/Build/Escape para `http_bad_url`. Ambos registram Json2 (M:662, E:553) | Compartilham conjunto de serviços, mas comportamento diverge. Matterfall demonstra por que um stub de erro pode deixar parâmetros de saída inadequados; conferir ABI e contratos antes de portar helpers. Json2 continua majoritariamente stub. |

`references/matterfall/CHANGELOG.md:38` e `:43` atribuem serviços UE4 e correções gráficas a MediEvil; as linhas de código acima sustentam transferências específicas. Sem rastreamento de commits ancestrais, a comparação não estabelece que todos os arquivos vieram diretamente de MediEvil. `src/runtime_file.c`, `runtime_mutex.c`, `runtime_thread.c`, `runtime_extra.c`, `runtime_audio.c`, `runtime_savedata.c`, `scripts/prepare.py` e `scripts/link_modules.py` possuem blobs diferentes nos dois SHAs.

## Melhorias de Matterfall que merecem investigação separada

- **Readback de sky light:** `M/gpu/shadps4/video_core/texture_cache/texture_cache.cpp:214`, `IsSmallMacroTiledTarget`, seleciona alvos macro-tiled de largura 9–64, altura até 8, um layer/mip/sample e até 1 MiB. `RecordTiledDownload` preserva layout tiled. `:1413`, merge de subimagens, é condicionado a `GOW3_MERGE_SUBIMAGES`. Os comentários citam commits de bahamutfan64/shadPS4. Isso explica uma solução de Matterfall; não prova que os mesmos limites descrevem Concrete Genie.
- **Red zone por RBP:** `M/src/runtime_redzone.c:147`, `scan_function`, segue prólogo após `mov rbp,rsp` e reconhece locais abaixo de RSP; habilitado por `GOW3_RED_ZONE_RBP`. Esse arquivo não existe no SHA MediEvil inspecionado. É uma mudança na transformação de código/ABI, a exigir testes próprios antes de reutilização.
- **Uploads maiores que chunk:** `M/gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.h:816` registra diretamente dados grandes. Inspecionar caso sintético de cube-array upload antes de transplantar para outro scheduler.
- **Cache quente:** `M/scripts/matterfall_settings.py`, `environment`, configura `GOW3_BACKGROUND_WARMUP=0` por padrão; o changelog 1.0.4 relata device loss AMD com cache quente. Incluir cold/warm cache e concorrência no plano, sem tomar o relato como teste local aprovado.

## O que não copiar

1. `M/scripts/matterfall_settings.py`, `OUTPUT_PATCHES`: duas assinaturas que alteram clamp ProMode e resolução de Matterfall. Os comentários dizem 1.00/1.01, mas esta auditoria não inspecionou eboots nem hashes. Não são patches autorizados para Concrete Genie.
2. Estimativas `GPU_HEAP_PS4_MB`, `GPU_HEAP_MAX_MB`, `MAX_RENDER_PIXELS`, `gpu_heap_extra_mb`: derivam de heaps e cenas de Matterfall. Aumentar memória direta isoladamente pode alterar cálculos de heap guest; não copiar os números.
3. `M/scripts/ue4_override.py:31`: pak v3, projeto Turrigun, caminho de config e dois Blueprints próprios. `E/scripts/ue4_override.py:23` usa pakchunk99, config Engine e pasta overbite; `setres_slot` usa assinatura específica. Compartilhar UE4 não torna esses nomes, layouts ou padrões intercambiáveis.
4. Defaults de `references/matterfall/tools/run_matterfall.py:32`: o script desliga hooks de jogos anteriores e upscalers temporais e habilita readback/merge/red-zone selecionados. O comando na linha 227 inclui `--no-game-hooks`. Reaproveitar a separação de políticas, nunca presumir que esse conjunto é seguro para o novo jogo.
5. Launcher, título CUSA02475, branding, resolução, presets e caminhos de saves/cache. `tools/package_matterfall.sh:35` copia executável, `:37` descobre DLLs com ldd e `:58` reúne licenças: estudar a distribuição completa, sem renomeação mecânica.

## Submódulos Matterfall registrados

`git submodule status` retornou todos com prefixo `-` (não inicializados); a leitura acima não dependeu deles:

| Caminho sob gow3_pc | SHA |
|---|---|
| gpu/third_party/fsr-vulkan | c64f093404125e960813f95f1996c14780f0dd69 |
| gpu/third_party/imgui | f1cc2ae15e53a861a874c3034aae6798fde194ab |
| gpu/third_party/magic_enum | e046b69a3736d314fad813e159b1c192eaef92cd |
| gpu/third_party/miniz | 2948eebafc5b9f1c69bebed80333e403a09bd62d |
| gpu/third_party/xbyak | cd6bad3cad2e07a3e277c23d2b1f065320024717 |
| third_party/LibAtrac9 | efca2e3af35562a09a9bb6deed90e45b4b824dc4 |

## Reprodução da comparação

Executados: `git -C references/matterfall rev-parse HEAD`, `status --short` (limpo), `submodule status`, `log -6 --oneline`; equivalentes de SHA e consultas `git rev-parse HEAD:<arquivo>` em MediEvil; `rg -n` por símbolos acima e leitura dos corpos de funções. Uma consulta a `HEAD:src/runtime_redzone.c` no MediEvil falhou porque o arquivo inexiste; a comparação dos demais blobs foi retomada separadamente. Nenhum build ou teste in-game foi executado por esta subauditoria.

Para repetir uma descoberta: `git -C references/matterfall show afaa2b7e212437f04baff709f983a121477ffcdf:gow3_pc/src/runtime_mutex.c` e comparar com `git -C references/medievil show 424f3ea8dbdcb02754a31e5225ef42e2f77f8e94:src/runtime_mutex.c`.

Próximo passo da comparação: após reproduzir o build original MediEvil, selecionar uma única lacuna comprovada por teste sintético ou trace de Concrete Genie; confrontar a implementação Matterfall correspondente e testar o contrato, preservando os patches de jogo desativados.
