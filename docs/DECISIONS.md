# Decisões

- 2026-10-31: executar somente a auditoria PROMPT 01 do attachment. O playbook completo preservado na raiz contém etapas futuras; elas não são autorização para pular o baseline.
- Manter bases em `references/medievil` e `references/matterfall`; raiz é repositório documental na branch `audit/base`. Nenhum runtime Concrete Genie criado nesta etapa.
- Fixar MediEvil em 424f3ea8dbdcb02754a31e5225ef42e2f77f8e94 e Matterfall em afaa2b7e212437f04baff709f983a121477ffcdf. Reutilização é candidata, não compatibilidade comprovada.
- Hipótese: a base contém infraestrutura reutilizável, mas exige separar políticas e alterações binárias de jogos antes de admitir Concrete Genie. Observáveis: gates no código, build original e testes sintéticos. Aceitação: matriz rastreável, build documentado, riscos explícitos. Reversão: nenhuma personalização de fonte; preservar checkouts e revisar documentação por Git.
- Build pode aplicar os patches FSR que o próprio upstream fornece, após pré-check. Essa mutação esperada de submódulo é registrada e não é adaptação de jogo.
