# Handoff entre IAs

- Data (UTC): 2026-11-01, sessão PROMPT 04 (investigação do primeiro frame).
- Branch: `bootstrap/windows`. Nenhum merge, rebase ou reset executado.
- **Critério do PROMPT 04 NÃO atingido: não existe primeira cena jogável.** Não houve frame.

## Resultado da sessão

O bloqueio do Prompt 03 (`abort` → `INT 0x44`) foi **atribuído a uma causa nomeada e medida**.
O que mudou:

| Antes | Agora |
|---|---|
| `Fault: read access to ffffffff` (enganoso) | `Blocker: PS4 syscall gate (int 0x44)` |
| causa desconhecida | `pool_reserve` recusado por conflito de endereço |
| hipótese de canário corrompido | **refutada**: canário íntegro |
| hipótese de pool esgotado | **refutada**: `GOW3_DMEM_MB=8192` não muda nada |

Causa raiz, com evidência:

```
Runtime: pool_reserve(address=0000001000000000, size=8589934592, align=0x0, flags=0x90) -> 0x8002000c
Runtime: reserve_range refused 0000001000000000+8589934592 (flags 0x90);
         VMA at 0000001000000000+6291456 kind=2 prot=0x2
```

O guest pede reserva de **8 GiB em endereço fixo** (`MAP_FIXED|MAP_NO_OVERWRITE`) em
`0x1000000000`. Um mapeamento direto de **6 MiB** (`KIND_DIRECT`) já ocupa essa base, criado
pelo próprio runtime via `find_free`, que sempre começa em `USER_MIN`.

Detalhe completo em `docs/MEMORY_AUDIT.md`.

## Erro meu nesta sessão (registrado para não repetir)

Reportei "canário corrompido" na primeira instrumentação. Estava errado: li `rbp-0x30` do
frame do `abort`, não do chamador. Corrigido para ler o frame correto, o canário aparece
íntegro. A conclusão errada teria consumido a sessão inteira num overflow inexistente.

## Por que a correção não foi aplicada

Há duas saídas e **nenhuma foi medida**:

1. Reservar o pool do guest antes do primeiro mapeamento direto (mudar a ordem de
   inicialização). Risco: não se sabe se outro caminho depende do mapeamento em `USER_MIN`.
2. Realocar o bloco de 6 MiB quando o guest reserva por cima. Risco: se algum ponteiro guest
   já aponta para o endereço antigo, o resultado é corrupção silenciosa.

Escolher sem medir trocaria um bloqueio nomeado por um bug de corrupção. Isso viola a regra
de não resolver sintoma sem prova.

## Estado de verificação

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0 |
| `python -m unittest discover -s tests` | exit 0, **39 testes** |
| Boot até o bloqueio | exit 3, causa nomeada, determinístico (3 execuções) |
| **Primeiro frame / menu / gameplay** | **NÃO EXECUTADO** |
| Áudio, controles, shader cache, frame pacing | **NÃO AUDITADOS** — não há cena |

Os itens de áudio, controles e GPU do Prompt 04 não foram tocados porque dependem de uma cena
visível. Auditar shaders sem frame seria descrever código, não observar comportamento.

## Entregáveis desta sessão

- `docs/MEMORY_AUDIT.md` — cadeia causal completa, hipóteses testadas e refutadas.
- `tests/test_memory_layout.py` — 10 testes que congelam constantes e o conflito medido.
- Instrumentação em `probe.c` / `runtime.c` / `runtime_memory.c`: gate `INT 0x44` nomeado,
  verificação de canário, logs de falha em `place`, `reserve_range`, `pool_reserve`.
- `docs/evidence/prompt04/` — 10 logs de boot + build + testes.

## Próxima ação única, verificável

Determinar se o guest depende de `USER_MIN` para o pool. Com a instrumentação atual:

1. Registrar toda leitura guest que caia em `[0x1000000000, 0x1000600000)` (o bloco de 6 MiB)
   **depois** do ponto onde `pool_reserve` é chamado.
2. Se nenhuma leitura ocorrer, a opção 2 (realocar) é segura e testável.
3. Se houver leituras, a opção 1 (inverter a ordem) é a única, e exige reexecutar o pipeline
   do início para pegar os endereços corretos.

Critério de conclusão: o `0x8002000c` deixa de aparecer **e** o log mostra o boot avançando
para um novo estágio nomeado — não basta o erro sumir.

## Ferramentas

`aiwh resume` executado no início da sessão. `aiwh audit` não foi reexecutado no fim.
Workbench não executa testes nem substitui log; nenhuma recomendação dele foi usada como
evidência de funcionamento.
