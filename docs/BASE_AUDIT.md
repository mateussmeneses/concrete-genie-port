# Auditoria da base — Concrete Genie

Data: 2026-10-31 UTC. Escopo: PROMPT 01 do texto fornecido; auditoria de fontes e reprodução do build original, sem personalizar runtime. Conclusão arquitetural: **base aproveitável com separação obrigatória de comportamento por jogo; compatibilidade Concrete Genie NÃO VALIDADA**. Build original reproduzido nesta máquina (exit 0); smoke Vulkan e quatro unitários GPU passaram. A suíte completa tem falhas e dois alvos Windows não linkam; o baseline não está verde. O estado final de execução está em PROJECT_STATE e TEST_MATRIX.

## Fontes e rastreabilidade

MediEvil: `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94`, [árvore fixada](https://github.com/bc160201983/medievil_2019_pc_port/tree/424f3ea8dbdcb02754a31e5225ef42e2f77f8e94), checkout `references/medievil`. Histórico recente: 424f3ea (1.3.8), bb28370 (1.3.7), 2c20e99 (merge Linux), 1ae17cd (scan r.SetRes), be3491a (merge native output). A árvore começou limpa.

Matterfall: `afaa2b7e212437f04baff709f983a121477ffcdf`, [árvore fixada](https://github.com/bc160201983/Matterfall-PC-port/tree/afaa2b7e212437f04baff709f983a121477ffcdf). Comparação baseada em código em [MATTERFALL_COMPARISON.md](MATTERFALL_COMPARISON.md). Loader/runtime/GPU detalhados em [RUNTIME_AUDIT.md](RUNTIME_AUDIT.md). Referências abaixo são relativas à árvore MediEvil nesse SHA; linhas e símbolos identificam evidência, não promessas upstream.

## Matriz de reuso

| Componente | Origem | Portabilidade | Modificações necessárias antes do novo jogo | Evidência | Risco |
|---|---|---|---|---|---|
| SELF/ELF e SFO | infraestrutura GoW herdada | alta, condicional aos formatos | validar segmentos, relocations e módulos reais | scripts/prepare.py: parse_self, span, unpack; tests/test_prepare.py | SELF cifrado/comprimido é rejeitado; não equivale a loader universal |
| Link de módulos | infraestrutura compartilhada | alta com limites | lista proveniente do dump; preservar identidade NID/biblioteca/módulo e TLS | scripts/link_modules.py:30 module, :97 link, :132 limite 512 MiB, saída G3PROBE5 | relocations/layouts não suportados bloqueiam boot; testes link_libc exercitam predecessor, não todo link_modules |
| Nomes de imports | shadPS4 aerolib + runtime | ferramenta reutilizável | gerar a partir de imports efetivos e revisar contratos implementados | scripts/gen_import_names.py:19 main; src/import_names.inc | nome resolvido não implementa semântica; script altera fonte |
| Perfil | MediEvil/GoW | mecanismo simples reutilizável | perfil explícito e rejeição de build desconhecida; nenhuma build candidata promovida | scripts/game_profiles.py: MEDIEVIL, PROFILES, DEFAULT, profile | unknown usa libc/Fios2; conhecidos filtram módulos ausentes silenciosamente |
| Orquestração | run.py MediEvil | parcial | isolar config, out, saves, env e hooks; remover defaults de título anterior | run.py:80 main, :138 profile, :172 override, :205 linker, :238 patches | --help não é interface independente: preparação/config ocorre antes do runtime |
| ABI/loader/TLS | GoW + compatibilidade Windows | núcleo candidato | auditar instruções, System V/Win64, TLS, validação de imagem | src/probe.c; src/compat_win.c; RUNTIME_AUDIT | corrupção/exception em guest sem unwind; FS→GS por padrões não é análise completa de instruções |
| Memória e threads | runtime PS4/Windows | candidato | testar reserva, aliasing, unmap/proteções, concorrência e stacks | runtime_memory.c, runtime_thread.c, runtime_mutex.c; RUNTIME_AUDIT | ordem de inicialização e limites são parte do contrato; stubs não comprovam semântica |
| Serviços offline e áudio/input/saves | runtime com extensões UE4/MediEvil | por contrato | implementar apenas lacunas observadas; saída de erro e buffers válidos | runtime_extra.c, runtime_audio.c, runtime_savedata.c, runtime_pad.c | NpToolkit2 no-op de sucesso; HTTP/Json incompletos; gyro/câmera/VR não verificados |
| SSE4a e hooks de jogo | MediEvil/GoW | não copiar sites | gate de build e evidência de disassembly antes de qualquer patch | runtime_sse4a.c:26-37, probe.c:859; RUNTIME_AUDIT | offsets fixos chamados sem gate de hash/título; comparação de bytes é insuficiente |
| UE4 pak/config | MediEvil | primitives candidatos; política específica | descobrir versão, mount, caminhos e schemas do jogo | ue4_override.py:64 paks_dir (overbite), :68 read_index (v7), :139 write_pak, :395 apply | edita diretório do dump; Blueprints, cheats e voice são particulares |
| r.SetRes/pool 4K | MediEvil | não transferível sem prova | nenhum offset/assinatura herdado | ue4_override.py:47 setres_slot; patches/MediEvil.xml; patches.py:73 GAMES | scan único não comprova assinatura/ABI para outro título |
| Patches | XML GoldHEN/shadPS4 + seleção local | parser candidato | exigir build/hash/bytes anteriores; manter patches MediEvil desligados | patches.py:50 compile_patches, :98 eboot_matches, :211 FORCE | eboot_matches(None) retorna True; chamador deve exigir perfil; FORCE remove proteção; bounds não validam bytes antigos |
| Tradução GPU/Vulkan | shadPS4 vendorizado e mudanças GoW/MediEvil | núcleo candidato com regressão | conferir formatos, barriers, caches, readback, memória e políticas por título | gpu/VENDOR.txt; gpu/shadps4; RUNTIME_AUDIT | compilar não prova shaders/imagem; defaults podem esconder erro visual |
| Launcher | MediEvil | utilitários parciais | launcher neutro, namespaces e endpoint próprios somente depois do baseline | launcher/medievil_launcher.py:36 DATA_DIR, :54 RELEASES_API, :171 APP_DEFAULTS | updater aponta para outro produto; tema/fontes, configuração e controles específicos |
| Build/distribuição | MSYS2/CMake/PyInstaller | reutilizável com correções documentais | preservar dependências/licenças, confirmar DLLs em máquina limpa | build.sh; gpu/CMakeLists.txt:197-233; packaging/windows/package.sh | README Windows tem nomes/caminhos GoW obsoletos; pip sem versões fixas; DLLs locais não provam distribuição completa |
| Testes | suíte herdada GoW/MediEvil | cobertura parcial | separar fixtures portáveis de testes Linux e defaults obsoletos | tests/paths.py; test_probe.py EXE=out/gow3-probe; evidence/python-tests.txt | suíte não verde; skips podem mascarar ausência de loader tests no Windows |

## Dependências críticas de boot

1. Dump local validado e descriptografado, SFO/eboot/módulos e imports reais. Nenhum foi fornecido ou inspecionado nesta sessão.
2. Preparação SELF→ELF e imagem G3PROBE, identidade de imports, relocations e inicializadores/TLS dos PRX.
3. NIDs mapeados a contratos de runtime corretos, sem declarar sucesso silencioso em serviço necessário.
4. Reserva de memória guest, stack comprometida, compatibilidade System V/Win64, exceções e instruções SSE4a no Intel.
5. GPU bridge/Vulkan/SDL e bibliotecas de áudio disponíveis; shaders e layouts corretos só serão demonstrados executando conteúdo.

## O que não copiar

Offsets, XML MediEvil, setres signature, pools 4K, cheats, Blueprint edits, overbite/Turrigun, configurações de qualidade/resolução, limites de heap Matterfall, namespaces de save/cache, branding e updater. Não copiar no-ops NpToolkit2 como implementação genérica de PSN nem tomar uma lista de NIDs como cobertura funcional. Correções GPU citadas como transferidas em Matterfall são candidatas individuais, não autorização para mesclar árvores.

## Build Windows 11 / MSYS2 CLANG64

O build é o original, com os forced includes recomendados no README. `packaging/windows/README.md` lista pacotes úteis mas conserva exemplos GoW antigos; nomes efetivos vêm de build.sh e package.sh. Na shell CLANG64:

```bash
pacman -S --needed git patch \
  mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python} \
  mingw-w64-clang-x86_64-{vulkan-headers,vulkan-loader,vulkan-memory-allocator,glslang} \
  mingw-w64-clang-x86_64-{sdl3,fmt,boost,robin-map,xxhash,ffmpeg,zydis} \
  mingw-w64-clang-x86_64-{spirv-tools,spirv-headers,spirv-cross}
git clone https://github.com/bc160201983/medievil_2019_pc_port.git references/medievil
git -C references/medievil checkout --detach 424f3ea8dbdcb02754a31e5225ef42e2f77f8e94
cd references/medievil
git submodule update --init --recursive
git ls-files --eol build.sh gpu/patches/fsr-vulkan
for p in gpu/patches/fsr-vulkan/*.patch; do
  git -C gpu/third_party/fsr-vulkan apply --check "$PWD/$p" || exit 1
done
CXXFLAGS="-include cstdlib -include cstdio -include cwchar -include cmath -include new" bash build.sh
```

Os checks acima são para checkout virgem; numa repetição, verificar `apply --reverse --check` para patches já aplicados em vez de reaplicá-los. Foram observados i/lf e w/crlf; checks passaram e build.sh aplicou os dois patches FSR próprios do upstream. Não houve patch de jogo. As versões locais de todos os pacotes estão em evidence/msys-packages.txt; o comando pacman acima documenta instalação, não foi executado nesta sessão. Sem snapshot de pacotes e comparação binária, não alegar reprodutibilidade bit a bit.

Submódulos exatos: [evidence/medievil-submodules.txt](evidence/medievil-submodules.txt). São seis: fsr-vulkan c64f093404125e960813f95f1996c14780f0dd69; imgui f1cc2ae15e53a861a874c3034aae6798fde194ab; magic_enum e046b69a3736d314fad813e159b1c192eaef92cd; miniz 2948eebafc5b9f1c69bebed80333e403a09bd62d; xbyak cd6bad3cad2e07a3e277c23d2b1f065320024717; LibAtrac9 efca2e3af35562a09a9bb6deed90e45b4b824dc4. O submódulo FSR fica dirty pelos patches de build; SHA base preservado.

Distribuição futura: Python Windows com Pillow/cryptography, PyInstaller pelo package.sh, `WINPYTHON` explícito se instalação não for descoberta. `bash packaging/windows/package.sh` não foi executado. Revisar staging/deleções antes da execução, licenças de dependências e testar pacote sem MSYS2/Python instalado. O bloqueio de arquivos comerciais no script é útil, mas não substitui inspeção do artefato.

## Licenças e limites da evidência

README e SPDX do código declaram GPL-2.0-or-later; LICENSE contém GPL v2. Preservar LICENSE, avisos de autoria e licenças das dependências; não tratar a licença do runtime como licença dos ativos do jogo. Esta é identificação de arquivos de licença, não auditoria jurídica de redistribuição. Nenhum ativo comercial foi adicionado.

Hardware e execução estão documentados por medições locais em TEST_MATRIX. Boot, menu, gameplay, áudio do jogo e correção visual permanecem NÃO EXECUTADOS. Próxima ação única está em HANDOFF.
