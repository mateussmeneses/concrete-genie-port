Leia `AGENTS.md` e os documentos de continuidade em `docs/` antes de qualquer ação;
`docs/PROJECT_STATE.md` e `docs/HANDOFF.md` são o estado corrente.

- Este repositório é um port independente de Concrete Genie. Nenhuma build de jogo está
  validada; CUSA11834 e CUSA11875 são apenas candidatos documentais.
- Confira `git status --short`, branch e `git log --oneline -10` antes de editar.
- Não promova offsets, patches, hooks ou cheats de MediEvil/GoW III/Matterfall a genéricos.
- Falha explícita: nunca silencie exit code nem use `--reject` para "resolver" um patch.
- Sem merge, rebase ou reset automático; sem merge automático no fim da etapa.
- Registre boot/menu/gameplay somente com log real; ausência de execução é NÃO EXECUTADO.
