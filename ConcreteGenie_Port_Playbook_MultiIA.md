# Concrete Genie — Playbook de port nativo PS4 → Windows (multi-IA)

**Alvo inicial:** Concrete Genie (2019), PS4, Unreal Engine 4. O identificador `CUSA11834` corresponde à edição americana exibida na PlayStation Store; o projeto só deve aceitar como build suportada uma versão cujo `param.sfo`, `eboot.bin` e hashes tenham sido realmente inspecionados. Não pressupor APP_VER nem offsets.

**Base principal:** https://github.com/bc160201983/medievil_2019_pc_port

**Referência complementar (mesmo autor e ecossistema, não copiar sem revisar):** https://github.com/bc160201983/Matterfall-PC-port

**Outras referências arquiteturais:** https://github.com/FelipePrado0/gow3_pc e https://github.com/shadps4-emu/shadPS4.

**Objetivo:** runtime que executa o código x86-64 original do jogo em Windows, substituindo serviços do PS4 e traduzindo gráficos para Vulkan; código de jogo e ativos comerciais não fazem parte do repositório. Compatibilidade, estabilidade, correção visual e gameplay real têm prioridade sobre presets, menu elaborado ou marketing de FPS.

**Ambiente principal de teste:** Windows 11, Intel Core i7-14650HX, RTX 5060 Laptop, 32 GB de RAM; documentar versão do driver, Vulkan, CPU, GPU e sistema obtidos da máquina, não presumidos. O suporte a outras GPUs permanece objetivo de regressão, não conclusão antecipada.

---

## Protocolo universal entre Codex / Claude / Gemini / DeepSeek / GLM / outras IAs

Cada agente deve trabalhar somente sobre o estado do repositório, sem depender de conversa anterior ou de memória do provedor. Ao iniciar:

1. Ler `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `docs/TEST_MATRIX.md`, `docs/HANDOFF.md`, além de `git status --short`, branch ativa e histórico recente.
2. Conferir o estado real da árvore antes de escrever; não descartar alterações de outra IA, não fazer reset, rebase ou merge sem comando explícito.
3. Escolher uma única hipótese técnica por intervenção e definir observáveis, critérios de aceitação e reversão. Priorizar bugs de boot, integridade de memória, correção de GPU e gameplay; não iniciar otimização especulativa.
4. Se faltar dump ou ambiente executável, realizar auditorias e testes estáticos, deixando qualquer teste in-game como **NÃO EXECUTADO**, jamais como aprovado.
5. Não inventar offsets, SHA-256, Title ID, APP_VER, NIDs, assinatura de função ou resultados de testes. Para alterações binárias, registrar build exata, arquivo, hash, RVA/VA, bytes antigos e novos, localização no disassembly e verificação antes de aplicar.
6. Manter os patches de MediEvil desativados para Concrete Genie até um mapeamento específico e verificado. Nunca aplicar patches pelo simples fato de ambos serem UE4.
7. Tratar como prioritários os problemas já conhecidos em outros ports: micro-stutter, cache de shaders, flickering, sombras/iluminação, uso excessivo de VRAM/RAM, input de mouse, menus que capturam input e distribuição Windows incompleta.
8. Manter builds reproduzíveis; preservar submódulos, licenças e a árvore original; revisar CRLF/LF antes de aplicar patches e usar `git apply --check` antes de qualquer patch legado.
9. Criar branches pequenas, testes adequados e commits descritivos. Nunca realizar merge automático na principal.
10. Antes de terminar, atualizar obrigatoriamente `docs/PROJECT_STATE.md` e `docs/HANDOFF.md` com evidências, comandos executados, resultados, limitações e **o próximo passo exato para outra IA**.

Criar `CLAUDE.md` e `GEMINI.md` como apontadores curtos para `AGENTS.md` (e.g. 'Leia AGENTS.md e os docs/ antes de qualquer ação'). Outros modelos recebem este playbook como contexto e também leem esses arquivos.

**Formato mínimo de `docs/HANDOFF.md`:**

```markdown
# Handoff entre IAs
- Data (UTC):
- IA/sessão: (se conhecido)
- Branch / HEAD SHA / dirty files:
- Base upstream SHA / submodule SHAs:
- Build alvo do jogo: TITLE_ID, APP_VER, eboot SHA-256 (ou NÃO VALIDADO):
- Estado atual: código compila? loader inicia? importa? menu? gameplay? áudio? GPU?
- Última alteração com justificativa:
- Comandos executados e resultados observados:
- Evidência: logs, traces, screenshots, testes, caminhos:
- Hipótese ativa e como confirmá-la ou refutá-la:
- Falhas e riscos conhecidos:
- Próxima ação única, executável e verificável:
- Critério de conclusão da próxima ação:
```

---

## PROMPT 01 — Auditoria de arquitetura e adequação da base (executar primeiro)

> Você atuará como engenheiro principal de runtime PS4→PC, RE x86-64, Vulkan, Unreal Engine 4 e QA. A tarefa é auditar o repositório de referência `bc160201983/medievil_2019_pc_port` para planejar um novo port de **Concrete Genie (2019)**. O desenvolvimento será conduzido por múltiplas IAs em sessões independentes. **Não dependa do histórico deste chat.**
>
> Examine o código real, inclusive `README.md`, `scripts/game_profiles.py`, `run.py`, `src/probe.c`, `src/runtime_*.c`, `scripts/link_modules.py`, `scripts/gen_import_names.py`, `scripts/ue4_override.py`, `gpu/`, `patches/`, `launcher/`, `tests/`, `.gitmodules` e `packaging/`. Identifique classes de componentes: runtime PS4 genérico, adaptações UE4 potencialmente reaproveitáveis, hacks exclusivos de MediEvil, configuração de build, testes, recursos de GPU, ABI e loader.
>
> Compare de forma seletiva com `bc160201983/Matterfall-PC-port` para descobrir o que o mesmo autor transferiu entre jogos; indique SHAs/linhas ou símbolos que sustentem cada descoberta. Não inferir funcionamento do Concrete Genie apenas por compartilhar UE4.
>
> Apresente uma **matriz** (componente, origem, portabilidade, modificações necessárias, evidência e risco), uma lista curta de dependências críticas de boot, e um conjunto de testes iniciais que não dependam de dump. Confirme que o build original pode ser reproduzido **antes** da personalização; não altere arquivos nesta etapa, salvo documentação expressamente necessária.
>
> Registre a revisão em `docs/BASE_AUDIT.md`; documente upstream commit, submódulos, licença GPL e instruções de Windows 11/MSYS2 CLANG64. Informe o que NÃO deve ser copiado. Termine com o próximo passo exato para outra IA, escrito em `docs/HANDOFF.md`. Não declare testes aprovados sem executá-los.

**Critério de aprovação:** matriz de reuso baseada no código, upstream fixado por SHA, comandos reproduzíveis e riscos concretos.

---

## PROMPT 02 — Bootstrap do repositório multi-IA e primeiro build

> O alvo é um **novo** port de Concrete Genie, baseado no repositório auditado de MediEvil, sem sobrescrever o upstream. Leia os documentos de continuidade e `docs/BASE_AUDIT.md`; escolha uma branch específica para este milestone.
>
> Faça a adaptação mínima para uma estrutura independente do jogo: nomes genéricos onde fizer sentido, perfis por `TITLE_ID`, prefixo de configuração específico do projeto, diretórios de cache e saves isolados e ponto de entrada de launcher que não dependa de assets comerciais. Não promova hooks/patches exclusivos de MediEvil a genéricos. A edição americana `CUSA11834` pode entrar como candidato documental, **não** como versão verificada; a confirmação vem de `sce_sys/param.sfo` e do SHA-256 de `eboot.bin` do dump local.
>
> Crie ou atualize `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `docs/TEST_MATRIX.md`, `docs/HANDOFF.md`, `docs/BASELINE.md` e `.gitignore` com regras de exclusão de dados comerciais, logs grandes e caches. Use nomes de pastas claros; não reorganize todo o runtime de uma vez.
>
> Garanta um build Windows reproduzível em MSYS2 CLANG64: inicialização de submódulos, dependências documentadas, tratamento idempotente de patches, falha explícita se houver erro. Corrija erros reais de compilação; não silencie retorno nem force patch com `--reject` como solução padrão. Inclua um smoke test independente de dump: `--help`, validação de configuração, mensagens claras quando faltar o jogo e auditoria de runtime.
>
> Execute os testes possíveis, capture comandos/exit codes e registre `docs/BASELINE.md`. Se o jogo não estiver disponível, não diga que deu boot. Produza um relatório com arquivos modificados, diff revisado, evidência e próximo passo. Sem merge automático.

**Critério de aprovação:** código compila, pipeline inicial não necessita de jogo para dar feedback válido, estrutura de governança multi-IA está preenchida, upstream rastreável.

---

## PROMPT 03 — Análise do dump, loader, imports e primeiro boot

> Trabalhe no repositório Concrete Genie e leia todos os documentos de continuidade. Audite **somente o dump local fornecido pelo operador**; nunca crie dados inventados. Extraia `TITLE_ID`, `APP_VER`, `CONTENT_ID`, hash SHA-256 do `eboot.bin`, imports/NIDs, módulos em `sce_module/`, bibliotecas de vídeo/áudio, formato de saves, uso de recursos de câmera/gyro/VR e sinais de personalização de Unreal Engine 4.
>
> Escreva `scripts/audit_game.py` para produzir um manifesto JSON local, com campos verificados, hashes e import table, sem distribuir binários do jogo. Se não houver dump, entregue apenas o analisador, fixtures sintéticas e testes de parsing; indique **AGUARDANDO DUMP REAL**.
>
> Ajuste `scripts/game_profiles.py`, seleção e ligação de módulos, `run.py` e loader para a build realmente identificada. Reutilize os serviços PS4 genéricos já auditados. Trace a primeira importação ou falha bloqueante em vez de adicionar dezenas de stubs cegos. Para cada nova função, implementar semântica real ou registrar explicitamente o stub com hipóteses e testes. Proteja leituras inválidas, endereçamento, mapeamento de memória, lifetime de objetos e chamadas de API.
>
> Itere com logs de boot e instrumentation controlada: registrar estágio alcançado, chamada bloqueante, stack/rastreamento quando possível, impacto e regressões. Não importar offsets de MediEvil, Matterfall ou outros jogos. Para patch binário, exigir SHA-256 e prova no disassembly da build local.
>
> A entrega da etapa é o maior avanço **comprovado** entre: `manifesto → eboot carregado → imports resolvidos → primeiro frame → menu → interação`. Documente com artefatos reproduzíveis, sem inventar avanço.

**Critério de aprovação:** estágio efetivamente alcançado e ponto de falha observável, com testes automatizados para correções feitas.

---

## PROMPT 04 — GPU, áudio, controles e primeira cena jogável

> Continue exclusivamente do estado documentado em `docs/HANDOFF.md`. Priorize qualidade funcional da cena antes de FPS ou opções cosméticas. Inspecione o pipeline Gnm/GCN→Vulkan e o que o jogo realmente usa de UE4: texturas, RTs, sincronização, formatos, shader stages, depth, sampling, barriers, iluminação, partículas, pós-processamento e caminhos de readback. Trace bugs com capturas de frames, logs por draw/dispatch e comparação visual com screenshots legítimas do PS4 quando disponíveis.
>
> Para cada bug visual, formule hipóteses verificáveis e adicione uma reprodução/telemetria pequena. Preserve caminhos de rendering corretos; não resolva flicker desativando efeitos globalmente sem prova e alternativa configurável.
>
> Audite o áudio e os codecs usados **pela build local**, não assuma que Wwise no MediEvil implica o mesmo conjunto aqui. Garanta reprodução, pausas e dispositivos. Para controles, implementar via SDL3 gamepad e teclado/mouse, com captura de cursor apenas em gameplay. Concrete Genie usa sensor de movimento para pintar e também oferece controle de pintura pelo analógico direito: valide o mapeamento real e priorize um fallback utilizável de mouse → eixo direito antes de sensores avançados. Não deixar overlay receber R3/L2 quando fechado, nem bloquear o input de jogo por engano.
>
> Os modos PlayStation VR, câmera e PS Move ficam fora do primeiro gate jogável, mas seus imports devem ser registrados; funções obrigatórias para boot não podem ser ignoradas sem evidência.
>
> Teste: boot, intro, menus, primeira cena visível, movimentação, pintura funcional, pausa, áudio e save/load. Registre o que foi observado, condições de reprodução e bugs P0/P1/P2 no `docs/TEST_MATRIX.md`.

**Critério de aprovação:** primeira cena funcional demonstrada e comprovada com logs e testes; não confundir 'jogo inicializa' com 'jogo é jogável'.

---

## PROMPT 05 — Estabilização, performance e pacote Windows

> Atue sobre a build jogável documentada. A prioridade é resolver regressões de gameplay e correção de GPU, só depois performance. Meça `frametime p50/p95/p99`, hitches > 33,3 ms, tempo de compilação de shader, quantidade de pipelines, VRAM/RAM, page faults, tempo de loading e estabilidade de saves. Faça testes cold-cache/warm-cache com o mesmo trajeto de jogo e identifique se os travamentos vêm de compilation, alocação, sincronização ou thread scheduling; não atribua causalidade sem profiler/log.
>
> Use o histórico de problemas de outros ports como checklist: micro-stutter, flickering, iluminação e sombras, textura recriada a cada quadro, VRAM descontrolada, cursor travado no menu, diferenças de refresh-rate, falhas de builds com patch em contexto diferente, dependências DLL faltando e caminhos absolutos no pacote. Corrija com mudanças isoladas e A/B reversível. Não ative FSR, DLSS, frame generation ou 120 FPS sem estabilizar 30/60 FPS e validar os requisitos técnicos reais do backend.
>
> Prepare empacotamento `dist/` com launcher, runtime, DLLs/licenças e arquivo de orientação; sem dados comerciais. Smoke test o conteúdo extraído numa pasta limpa e verifique a inicialização e os erros de configuração. Confirme que os patches são específicos para hashes de build aceitos e que falham fechados em versões desconhecidas.
>
> Entregue histórico de testes (máquina e driver), comparativo antes/depois, bugs pendentes, SHAs, regressões, comandos de build e handoff da próxima sessão. Nunca marque a campanha como concluída sem full playthrough real.

**Critério de aprovação:** regressão reprodutível e artefato Windows validado, com desempenho medido e limites declarados.

---

## Prompt universal de retomada — colar em qualquer IA a cada troca

> Você vai CONTINUAR o projeto de port nativo **Concrete Genie PS4 → PC** a partir dos arquivos reais do repositório, não do histórico desta conversa. Antes de agir, leia `AGENTS.md`, `docs/HANDOFF.md`, `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/TEST_MATRIX.md`, `docs/BASELINE.md` e `git status`, além do commit atual e os últimos commits. Reconstituir a hipótese ativa, confirmar o que foi realmente testado e escolher a ação de maior prioridade que cabe em uma alteração verificável. Não repetir trabalho concluído sem razão, não alterar componentes não relacionados, não apagar alterações pendentes e não fazer merge automático. Execute testes adequados, documente evidências e atualize `docs/HANDOFF.md` com progresso, riscos e **próxima ação verificável** para a IA seguinte. Se algo é desconhecido, marque como não verificado. Se faltar dump, avance apenas no que é testável sem ele. Ao final, entregue diff resumido, comandos, resultados, riscos e branch/HEAD.

---

## Roteiro de aceitação (gates)

| Gate | Definição de pronto | Evidência obrigatória |
|---|---|---|
| G0 | Auditoria e build original reproduzível | SHA upstream, lista de dependências, comandos/exit codes |
| G1 | Novo port compila e inicia pipeline sem dump | executáveis, testes sintéticos, mensagens de erro corretas |
| G2 | Dump local identificado e eboot carregado | param.sfo, SHA-256, import list, log do loader |
| G3 | Primeiro frame e menu | logs Vulkan, captura validada e caminho reprodutível |
| G4 | Primeira cena com pintura, áudio e save | vídeo/capturas e matriz de gameplay |
| G5 | Campanha auditada | testes por área e regressões verificadas |
| G6 | Dist Windows e desempenho documentados | ZIP, hashes, smoke test, benchmark cold/warm cache |

## Referências verificadas (2026-10-31)

- MediEvil: https://github.com/bc160201983/medievil_2019_pc_port
- Matterfall: https://github.com/bc160201983/Matterfall-PC-port
- A Pixelopus confirma Unreal Engine 4: https://blog.br.playstation.com/2017/10/30/concrete-genie-da-equipe-de-entwined-chega-ao-ps4-em-2018/
- Edição americana CUSA11834 (PS Store): https://store.playstation.com/pt-br/product/UP9000-CUSA11834_00-CONCRETEGENIE000/
- Ausência de port registrado no catálogo (não prova absoluta de inexistência): https://recomphub.com/games/concrete-genie
