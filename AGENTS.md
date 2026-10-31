# Protocolo do projeto

Antes de qualquer intervenção, leia `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `docs/TEST_MATRIX.md` e `docs/HANDOFF.md`; confira `git status --short`, branch e histórico recente. O playbook fornecido está em `ConcreteGenie_Port_Playbook_MultiIA.md`; a etapa atual é PROMPT 01, auditoria sem personalizar código.

Trabalhe com uma hipótese por intervenção: registre observáveis, aceitação e reversão. Preserve alterações existentes e upstream; reset, rebase e merge exigem comando explícito. Use branches pequenas e commits descritivos, sem merge automático.

Build de jogo só é suportada após inspecionar param.sfo, eboot.bin e SHA-256. CUSA11834 é candidato documental. Registre testes sem dump separadamente; gameplay sem execução é NÃO EXECUTADO. Patches de outros jogos permanecem desativados para Concrete Genie. Cada alteração binária exige build, arquivo/hash, RVA/VA, bytes antigos/novos, disassembly e verificação anterior à aplicação.

Preserve árvore, submódulos e licenças. Confira CRLF/LF e execute git apply --check antes de patches legados. Priorize boot, memória, GPU e gameplay, incluindo stutter, caches, flickering, iluminação, VRAM/RAM, mouse, captura de input e distribuição Windows.

Ao encerrar, atualize PROJECT_STATE e HANDOFF com comandos, resultados, limitações e uma próxima ação verificável. Dados comerciais, saves e caches derivados do jogo ficam fora de commits. `references/` contém checkouts de inspeção, não o port personalizado; não os adicione por engano ao índice da raiz.
