# Roadmap

Etapa atual: **PROMPT 02 concluído; PROMPT 03 bloqueado por insumo (AGUARDANDO DUMP REAL).**

1. **PROMPT 01 — auditoria do upstream. CONCLUÍDO.**
   SHAs fixados, comparação Matterfall, baseline original e evidências.
   Ver `docs/BASE_AUDIT.md` e `docs/RUNTIME_AUDIT.md`.

2. **PROMPT 02 — bootstrap independente e primeiro build. CONCLUÍDO.**
   Branch `bootstrap/windows`; runtime vendorizado com nomes genéricos; perfis por TITLE_ID
   fail-closed; config `CG_*`; `--help`/`--check-config`/falta-de-jogo/`--audit-runtime`
   sem dump; build MSYS2 CLANG64 reproduzível com patches idempotentes e falha explícita.
   Critério atendido: compila, pipeline inicial dá feedback válido sem jogo, governança
   multi-IA preenchida, upstream rastreável. Ver `docs/BASELINE.md`.

3. **PROMPT 03 — análise do dump, loader, imports e primeiro boot. BLOQUEADO.**
   Requer dump local do operador. Entregáveis sem dump (permitidos):
   `scripts/audit_game.py` + fixtures sintéticas + testes de parsing, declarando
   **AGUARDANDO DUMP REAL**. Com dump: `TITLE_ID`, `APP_VER`, `CONTENT_ID`, SHA-256 de
   `eboot.bin`, imports/NIDs, `sce_module/`, codecs, formato de save, uso de câmera/gyro/VR
   e sinais de UE4. Registrar a build real em `PROFILES` apenas após inspeção.
   Critério: maior avanço comprovado entre manifesto → eboot carregado → imports resolvidos
   → primeiro frame → menu, com ponto de falha observável.

4. **PROMPT 04 — primeira cena jogável.** Qualidade funcional antes de FPS. Pintura por
   analógico direito/mouse como fallback antes de sensores; PSVR/câmera/PS Move fora do
   primeiro gate jogável, mas com imports registrados.

5. **PROMPT 05 — estabilização, performance e pacote Windows.** Frametime, VRAM/RAM,
   cold/warm cache, distribuição limpa, patches com gate de hash.

Cada etapa exige revisão da anterior. Nenhuma etapa autoriza presets ou otimização
especulativa, nem declarar sucesso sem artefato reproduzível.
