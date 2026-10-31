# Estado do projeto

Atualizado: 2026-10-31 UTC. **PROMPT 01 concluído como auditoria; base original compila, baseline de testes não está verde.** Não existe port Concrete Genie funcional nesta árvore.

- Raiz começou com apenas o playbook do usuário, sem Git e sem documentos de continuidade. Foi criado repositório documental, branch audit/base; upstreams preservados em references/.
- Base MediEvil fixada em 424f3ea8dbdcb02754a31e5225ef42e2f77f8e94; Matterfall afaa2b7e212437f04baff709f983a121477ffcdf. Submódulos/linhas/fontes em BASE_AUDIT e anexos.
- Build Windows CLANG64 original concluído (exit 0), sem personalização de fonte. Única mutação no checkout upstream: patches FSR próprios do build, pré-validados; submódulo dirty esperado, SHA preservado.
- Vulkan smoke NVIDIA e quatro testes GPU sem dump passaram. Suíte Python: 112, 6 failures, 7 errors, 29 skips. Dois alvos de testes Windows não linkam timeBeginPeriod. Runtime --help retorna erro de arquivo de boot, não ajuda. Resultados completos em TEST_MATRIX e evidence/.
- Build alvo Concrete Genie: TITLE_ID/APP_VER/eboot SHA-256 NÃO VALIDADOS; CUSA11834 é apenas candidato do playbook. Nenhum dump fornecido/inspecionado. Loader do jogo, imports do jogo, menu, gameplay, áudio e GPU visual: NÃO EXECUTADOS.
- Riscos prioritários: patches SSE4a fixos sem gate de build; NpToolkit2 no-op global; gyro sem preenchimento real; UE4 pak/Blueprint/layouts de MediEvil não transferíveis; configuração/atualizador/saves com nomes e políticas herdados.
- Auditoria entregue: BASE_AUDIT.md, RUNTIME_AUDIT.md, MATTERFALL_COMPARISON.md, protocolo AGENTS/CLAUDE/GEMINI, DECISIONS, ROADMAP, TEST_MATRIX e HANDOFF. Nenhum código comercial ou ativo de jogo adicionado.

Próxima intervenção: correção mínima do link dos alvos services-test/pad-map-test em checkout de desenvolvimento, preservando esta referência original, antes de adaptar perfil Concrete Genie. Critério e comando em HANDOFF.
