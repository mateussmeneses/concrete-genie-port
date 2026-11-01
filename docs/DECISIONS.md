# Decisões

Registro append-only. Cada entrada: data, decisão, motivo, reversão.

## 2026-10-31 — PROMPT 01 (auditoria)

- Executar somente a auditoria do playbook. As etapas futuras do texto não autorizam pular
  o baseline. Reversão: nenhuma alteração de fonte.
- Manter bases em `references/medievil` e `references/matterfall`; raiz é repositório
  documental. Nenhum runtime de Concrete Genie criado nessa etapa.
- Fixar MediEvil em `424f3ea8dbdcb02754a31e5225ef42e2f77f8e94` e Matterfall em
  `afaa2b7e212437f04baff709f983a121477ffcdf`. Reutilização é candidata, não compatibilidade.
- Build pode aplicar os patches FSR fornecidos pelo próprio upstream após `git apply --check`.
  Essa mutação esperada de submódulo é registrada e não é adaptação de jogo.

## 2026-10-31 — PROMPT 02 (bootstrap)

- **Branch `bootstrap/windows`, sem merge automático.** O milestone tem branch própria para
  que a revisão do diff seja possível antes de qualquer integração.
- **Runtime vendorizado, não reorganizado.** `runtime/` continua com a estrutura do upstream;
  a adaptação foi mínima e localizada (nomes de artefato, config, perfil, limpeza de hooks).
  Reversão: `git checkout <commit> -- runtime/`.
- **Perfis fail-closed por TITLE_ID + SHA-256.** `CUSA11834`/`CUSA11875` entram como
  candidatos com `builds: {}`; qualquer build não registrada é rejeitada com o hash calculado
  na mensagem. Motivo: sem dump inspecionado, aceitar um título seria declarar suporte
  fictício. Reversão: remover a entrada de `PROFILES`.
- **Hooks e patches de outro jogo removidos do runtime genérico.** Cheats, multiplicadores,
  health bar, `apply_patches`, sites SSE4a fixos e `r.SetRes` de MediEvil saíram de
  `probe.c`/`runtime_extra.c`/`runtime_sse4a.c`/`gow3_overlay.cpp`. Motivo: a regra "não
  promover artefato de outro jogo a genérico"; deixar o código inerte ainda seria herança
  enganosa. Emulação SSE4a por fault handler permanece (genérica, sem offsets de título).
- **`--patches` passa a falhar explicitamente.** Antes aceitava um arquivo de patch sem
  gate de build. Agora retorna erro porque nenhuma build está validada. Reversão: reintroduzir
  o parser junto do gate de hash/bytes exigido por AGENTS.md.
- **Config `CG_*` e dados isolados.** Prefixo do projeto, JSON validado, `.cg/` como padrão,
  saves por `TITLE_ID` e cache por SHA-256. Motivo: separar save (durável) de cache (derivado)
  e impedir que dados caiam em `runtime/` ou `references/`. Reversão: `--data-dir` explícito.
- **Entrada neutra = `Launch Concrete Genie.cmd` → `run.py`.** O alvo `medievil-play`
  ("Play MediEvil.exe", com ícone de MediEvil) e seus `.rc`/`play.c`/manifest de MediEvil
  foram removidos; o manifest virou `runtime.manifest` e a identidade `cg.runtime`. Motivo:
  o ponto de entrada não pode depender de branding/assets de outro jogo.
- **`build.sh` corrigido em dois bugs reais.** (1) `$PWD` era passado a um git nativo, que não
  resolve `/c/...`; o `--reverse --check` falhava e o script reportava "already applied" mesmo
  em checkout limpo — patches nunca eram aplicados de fato. Agora usa `cygpath -m` e, se o
  patch não aplica nem em reverso, o build **falha com exit 1** (nunca `--reject`).
  (2) `windres` não criava arquivo temporário porque herdava `TMPDIR=/tmp`; o build agora
  aponta `TMP`/`TEMP`/`TMPDIR` para `runtime/out/tmp`. Reversão: reverter `build.sh`.
- **`.gitattributes` passa a ser versionado.** Sem ele, `core.autocrlf=true` converteu os
  `.patch` para CRLF e eles nunca aplicariam (os alvos são LF). Motivo: build reproduzível.
- **`winmm` ligado só nos alvos de teste.** `compat_win.c` chama `timeBeginPeriod`;
  `services-test` e `pad-map-test` não linkavam. Correção mínima e documentada em BASELINE.
- **Suíte herdada não foi "consertada".** `runtime/tests` segue vermelha; alterar expectativas
  de GoW/MediEvil para ficar verde mascararia regressões. Só `test_probe.py` recebeu o caminho
  do novo executável e o gate de `--patches`.

## 2026-10-31 — dump local recebido (pós-bootstrap)

- **O dump é `CUSA11875` (EU), não `CUSA11834` (US).** O playbook citava a edição americana
  como candidata; o operador forneceu a europeia. Verificado por `sce_sys/param.sfo`
  (`TITLE_ID`, `APP_VER=01.07`, `CONTENT_ID=EP9000-CUSA11875_00-CONCRETEGENIE000`) e SHA-256
  de `eboot.bin` (`06f143de…33e51`, 108.601.759 bytes). As duas entram como candidatas
  documentais; nenhuma é versão verificada.
- **Identificar não é validar.** `CUSA11875` foi adicionada a `CANDIDATES` com `builds: {}`.
  Motivo: um título reconhecido não pode liberar preparação, patches ou qualquer escrita sem
  auditoria de imports/módulos. O pipeline recusa a build real com exit 1 e o hash na mensagem.
  Reversão: remover a entrada; o comportamento fail-closed permanece.
- **Dump nunca entra no índice.** `gamedump/` foi adicionado ao `.gitignore` junto de
  `*.self`, `sce_module/`, `sce_sys/`, `*.pak`/`*.uasset`/`*.utoc` e padrões de save. Motivo:
  25 GB de conteúdo comercial e risco de vazamento. Verificado com `git status --short`.
- **`CANDIDATES` é o nome canônico; `PROFILES` fica como alias.** Motivo: o termo deixou de
  ser "perfil de jogo suportado" e passou a ser "título candidato"; manter o alias evita
  quebrar a suíte existente sem renomear tudo de uma vez.

## 2026-11-01 — PROMPT 03: AI Workbench e auditoria do dump

- **AI Workbench entra como ferramenta externa, não dependência do runtime.** `aiwh init`
  anexa um bloco gerenciado por marcadores (`<!-- AIWH:BEGIN -->`) e copia skills para
  `.agents/`, `.claude/`, `.openclaude/`. O conteúdo do Prompt 02 foi preservado (verificado
  por diff semântico). `.ai-workbench/` fica no `.gitignore`. Nenhum MCP/plugin instalado e
  nenhuma automação global ativada. Reversão: remover `.agents`, `.claude`, `.openclaude`,
  `AI-WORKBENCH.md` e o bloco marcado em `AGENTS.md`/`CLAUDE.md`.
- **O dry-run foi inspecionado antes de aplicar**, porque ele indicava `update` em `AGENTS.md`
  e `CLAUDE.md`. Ler `src/aiwh/workbench.py:managed_text` mostrou que a escrita é restrita à
  seção marcada e idempotente, o que tornou a aplicação segura. Sem essa leitura o `update`
  teria sido recusado.
- **`CUSA11875` é registrada como auditada, não como suportada.** O bloco `audited` guarda
  fatos verificados (APP_VER, SHA-256, contagem de imports, primeiro bloqueio), mas `builds`
  continua vazio. Motivo: registrar a build desbloquearia preparação e saves para um dump que
  nunca chegou ao menu. Reversão: remover o bloco; o comportamento fail-closed não muda.
- **Não se cria stub para `abort` nem para o `INT 0x44`.** O gate de syscall não tem
  semântica conhecida nesta build, e devolver sucesso cego esconderia a causa. A escolha foi
  **diagnosticar** (`is_ps4_syscall_gate()` em `probe.c`) e registrar a investigação como
  próxima ação. Reversão: remover a função e a mensagem.
- **`scripts/audit_game.py` reaproveita os parsers do upstream** (`prepare.parse_self`,
  `prepare.sfo`, `link_modules.module`) em vez de duplicar SELF/ELF/SFO. Motivo: uma correção
  de parser serve os dois caminhos. Contrapartida: o script depende de `runtime/scripts` no
  `sys.path`, o que é intencional e está documentado no cabeçalho.
- **Manifesto somente leitura.** `audit_game.py` não copia binários e não escreve no dump;
  apenas lê e reporta. Verificado: SHA-256 do eboot recalculado depois da execução não mudou.
- **A avaliação automática do Workbench foi confrontada com a evidência.** `GAME_PORT_PLAN.md`
  afirma "No executable bytes inspected" e `CONTEXT.md` afirma "No TODO items located";
  ambas são falsas aqui. As recomendações foram tratadas como sugestão, não como resultado.

## 2026-11-01 — PROMPT 04: causa do bloqueio de boot

- **Diagnóstico antes de correção.** O bloqueio mudou de "abort sem causa" para
  `pool_reserve` recusado por conflito de endereço em `USER_MIN`. Trocar um sintoma obscuro
  por uma causa medida é o avanço da etapa; o boot continua bloqueado. Reversão: remover a
  instrumentação.
- **Duas hipóteses próprias foram refutadas por teste, não por argumento.** (1) canário
  corrompido: falso, eu lia o frame errado do `abort`; (2) pool esgotado: falso,
  `GOW3_DMEM_MB=8192` reproduz o mesmo bloqueio. Registro explícito para que a próxima sessão
  não repita as duas.
- **Não corrigi o conflito de layout.** As duas saídas (inverter a ordem de inicialização ou
  realocar o bloco de 6 MiB) mudam a semântica de memória do guest sem prova de qual ele
  espera. Escolher agora trocaria um bloqueio nomeado por corrupção silenciosa, o que viola a
  regra de exigir evidência antes de alterar. A próxima ação é medir.
- **Áudio, controles, shader cache e frame pacing não foram auditados.** Dependem de uma cena
  visível; sem frame, qualquer afirmação sobre eles seria descrição de código apresentada como
  observação. `tests/test_memory_layout.py` congela constantes e o conflito medido para que
  uma mudança futura confronte o achado em vez de contorná-lo.

## 2026-11-01 — PROMPT 04 (continuação): construtores NpToolkit2

- **Tamanho de struct vem do frame do guest, não de um palpite.** `InitParams` ocupa
  `rbp-0x398 .. rbp-0x260` = 312 bytes, medido em dois `leaq` no mesmo frame. Zeroing com
  tamanho errado atingiria o canário a `rbp-0x30`; o valor medido termina 560 bytes antes.
  Reversão: remover `runtime_np.c`.
- **Só construtores são respondidos.** `runtime_np.c` registra apenas símbolos `C1Ev`/`C2Ev`, e
  um teste rejeita qualquer entrada que não seja construtor. Motivo: um construtor inicializa
  memória do chamador (sem contrato de serviço), enquanto um serviço exige semântica real.
- **`Core::init` NÃO recebeu sucesso cego, apesar de o guest aceitar 0.** O call site faz
  `testl %eax,%eax; je <continua>`, então devolver 0 "funcionaria" — mas as 79 funções de
  `libSceNpToolkit2` passariam a operar sobre um subsistema nunca inicializado, e a falha
  apareceria longe da causa. A decisão de política offline (recusar com erro tratado vs.
  implementar PSN local com estado) precisa ser tomada e registrada antes de codificar.
- **Decisão tomada: recusar `Core::init` com `0x80550003`.** O ramo de falha do guest
  (`0x40c791f`) destrói o objeto, revalida o canário e retorna limpo — recusar é caminho
  tratado, e o jogo continuou (22 threads, 176 leituras). Escolha registrada para que a próxima
  sessão não "conserte" isso devolvendo zero.
- **Tamanho de `InitParams` corrigido de 312 para 352 bytes na mesma sessão.** A primeira
  medida confundiu `rbp-0x260` (um campo interno) com o início do objeto seguinte, que é
  `rbp-0x238`. Teste novo impede regressão. Lição: medir a extensão pelos campos que o guest
  escreve e pelo próximo objeto construído, não por um único `leaq` vizinho.

- **Subsistemas de sensor respondem "biblioteca carregada, dispositivo ausente".** PS Move,
  PSVR, áudio 3D, câmera e VR tracker não têm hardware nesta máquina. A escolha é distinta de
  "não implementado" e de "sucesso falso": a biblioteca inicializa, e cada operação que exigiria
  um dispositivo devolve o código de erro da própria família PS4. `sceCameraIsAttached` responde
  0 (não anexada) porque essa é a resposta que faz o jogo escolher o caminho sem gestos.
- **Não fabricar handle nem estrutura de saída.** `sceHmdOpen`/`sceMoveOpen` devolvem "sem
  dispositivo" em vez de um handle fictício, e `sceCameraGetFrameData` falha em vez de entregar
  buffer zeroado que pareceria captura válida.
- **`sceVrTrackerQueryMemory` devolve 0 — e isso é a hipótese principal do fault atual.**
  Registrado como suspeita, não como acerto: o guest testa o retorno (`0x36f3f56`) e, com 0,
  segue adiante. Se a falha em `RHIThread` vier daí, a correção é preencher a saída, não trocar o
  código de retorno.

## 2026-11-01 — instrumentação de estado por frame (GOW3_FRAME_MAP)

- **O teste passa a se ancorar no estado observado, não no índice de frame.** Duas conclusões
  anteriores foram mal interpretadas por capturar frames numa fase de UI. A instrumentação grava,
  por frame apresentado, a grade de luminância 3×3 da imagem final e a contagem de draws, e
  `scripts/frame_states.py` imprime as faixas. Motivo: um índice de frame não identifica estado
  quando o ponto de parada do boot varia entre execuções. Reversão: remover o bloco
  `FrameMap` de `vk_presenter.cpp`; nada mais depende dele.
- **A sonda é óptica, não semântica.** Ela lê a imagem que o swapchain apresenta; não consulta
  estado do motor nem infere nome de cena. `scene`/`bright`/`fade` são descrições da imagem, não
  rótulos de gameplay. Motivo: nomear "gameplay" a partir de luminância seria a mesma inferência
  não medida que já produziu erro. Reversão: idem.
- **`fade` e `scene` se separam por estrutura, não por brilho.** O fade de OPTIONS passa por 71,7
  de média — a mesma do cenário 3D — mas com spread de 1,3 entre células, contra >80 do cenário. A
  classificação checa luminância e depois spread, nessa ordem, porque a tela de UI é clara (≈248)
  e pouco estruturada (spread ≈35). Reversão: ajustar as constantes; os testes fixam os valores
  medidos.
- **O readback é síncrono de propósito.** Um readback diferido reportaria a grade de um frame
  antigo sob o número do frame atual, que é exatamente a confusão que a instrumentação existe para
  eliminar. Custo medido: 3,09 ms por amostra, com 30 FPS mantidos. Reversão: `GOW3_FRAME_MAP=0`
  desliga tudo, sem recompilar.
- **Amortecimento por `GOW3_FRAME_MAP_EVERY`.** Amostrar todo frame custaria ~3 ms/frame; a cada 10
  frames custa 0,3 ms/frame e ainda dá resolução suficiente para achar a fronteira de estado.
  Motivo: a sonda não pode perturbar o que mede. Reversão: variável de ambiente.
- **Os docs foram corrigidos, não reescritos por cima de outra IA.** `PROJECT_STATE.md`,
  `TEST_MATRIX.md` e `HANDOFF.md` afirmavam "nenhum frame renderizado" e "39/72 testes", o que
  contradizia evidência já commitada no mesmo branch. Corrigido com os números medidos; nenhuma
  conclusão alheia foi apagada, apenas atualizada contra a evidência.
