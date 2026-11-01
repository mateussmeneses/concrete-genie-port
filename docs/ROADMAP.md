# Roadmap

Etapa atual: **PROMPT 03 concluído (dump `CUSA11875` auditado e bootado); PROMPT 04 em andamento.**
Existe cena 3D estável com input de câmera; **não existe cena jogável verificada** (sem pintura,
áudio ou save/load).

1. **PROMPT 01 — auditoria do upstream. CONCLUÍDO.**
   SHAs fixados, comparação Matterfall, baseline original e evidências.
   Ver `docs/BASE_AUDIT.md` e `docs/RUNTIME_AUDIT.md`.

2. **PROMPT 02 — bootstrap independente e primeiro build. CONCLUÍDO.**
   Branch `bootstrap/windows`; runtime vendorizado com nomes genéricos; perfis por TITLE_ID
   fail-closed; config `CG_*`; `--help`/`--check-config`/falta-de-jogo/`--audit-runtime`
   sem dump; build MSYS2 CLANG64 reproduzível com patches idempotentes e falha explícita.
   Critério atendido: compila, pipeline inicial dá feedback válido sem jogo, governança
   multi-IA preenchida, upstream rastreável. Ver `docs/BASELINE.md`.

3. **PROMPT 03 — análise do dump, loader, imports e primeiro boot. CONCLUÍDO.**
   Dump `CUSA11875` (EU, APP_VER 01.07) auditado; `TITLE_ID`, `CONTENT_ID` e SHA-256 do
   `eboot.bin` registrados. Boot atravessa imports, PSN, sensores e liga os módulos; sem `STOP`.
   Critério (maior avanço comprovado entre manifesto → eboot carregado → imports resolvidos →
   primeiro frame → menu) atendido até o menu.

4. **PROMPT 04 — primeira cena jogável. EM ANDAMENTO.**
   Alcançado: cena 3D estável a 30 FPS, input de gamepad move a câmera, frame pacing medido.
   Falta: pintura (negativa por R2, stick e sensor), áudio (runtime correto, guest entrega zeros),
   save/load, mouse como eixo direito, pausa (não observada).
   Instrumentação nova: `GOW3_FRAME_MAP=1` + `scripts/frame_states.py` ancoram cada teste à faixa
   de estado observada, em vez de a um índice de frame fixo.

5. **PROMPT 05 — estabilização, performance e pacote Windows.** Frametime, VRAM/RAM,
   cold/warm cache, distribuição limpa, patches com gate de hash.

Cada etapa exige revisão da anterior. Nenhuma etapa autoriza presets ou otimização
especulativa, nem declarar sucesso sem artefato reproduzível.
