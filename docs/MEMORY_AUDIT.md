# Auditoria da memória — conflito de reserva no boot

Data: 2026-11-01 UTC. Dump `CUSA11875`. Este documento registra o bloqueio atual do
primeiro frame, medido com instrumentação própria. **Nenhum frame foi renderizado.**

## Resumo

O código guest executa, o GPU/Vulkan inicializa, 465.785 relocations são aplicadas e os
módulos ligam. A execução para quando o guest pede a reserva do pool de memória virtual:

```
Runtime: pool_reserve(address=0000001000000000, size=8589934592, align=0x0, flags=0x90) -> 0x8002000c
Runtime: reserve_range refused 0000001000000000+8589934592 (flags 0x90);
         VMA at 0000001000000000+6291456 kind=2 prot=0x2
```

- `size` = 8.589.934.592 = **8 GiB**
- `flags` = `0x90` = `MAP_FIXED (0x10) | MAP_NO_OVERWRITE (0x80)`
- `kind=2` = `KIND_DIRECT`; `prot=0x2` = leitura
- `0x8002000c` = `NO_MEMORY`

## Cadeia causal completa (verificada no disassembly)

1. `libc+0x21264` (`abort`, NID `L1SBTkC+Cvw`) executa `INT 0x44`.
2. O chamador é `libc+0x2240b`, que faz `call *GOT` e valida o retorno:
   `testl %eax,%eax; jne <abort path>`.
3. O valor observado em `rax` no fault é `0x8002000c` = `NO_MEMORY`.
4. Quem retorna esse código é `pool_reserve` → `reserve_range` → `overlaps(..., 0)`.

O `INT 0x44` continua não atendido pelo runtime; o que mudou nesta etapa é que a causa
passou a ser nomeada em vez de aparecer como "read access to ffffffff".

## O conflito de layout

O runtime reserva todo `[USER_MIN, USER_MAX)` com placeholders antes de qualquer outra
coisa (`runtime_memory_reserve`, `runtime_memory.c:155`). `USER_MIN = 0x1000000000`.

Antes da reserva do pool, um mapeamento direto de 6 MiB já ocupa exatamente o início desse
endereço:

```
Runtime: mapped direct memory 0000001000000000, size=6291456, prot=0x2
```

Como o pedido do guest é **fixo** (`MAP_FIXED`) e **sem sobrescrita** (`MAP_NO_OVERWRITE`),
`overlaps()` encontra o mapeamento de 6 MiB e recusa. Não é falta de memória física: é
colisão de endereço entre a reserva do pool e um mapeamento anterior na mesma base.

## O que foi testado e refutado

| Hipótese | Teste | Resultado |
|---|---|---|
| Pool de memória esgotado | `GOW3_DMEM_MB=8192` | **Refutada** — mesmo bloqueio, zero falhas de alocação |
| Canário de pilha corrompido | comparação no frame do chamador | **Refutada** — canário íntegro (`MATCH`) |
| Mapeamento indireto (sem `MAP_FIXED`) | log em `place()` | **Refutada** — retorna antes, no `reserve_range` |
| `MAP_NO_OVERWRITE` sobre reserva | log em `place()` | **Refutada** — mesma razão |
| Conflito `MAP_FIXED` × memória direta | log em `reserve_range` | **Confirmada** |

Reprodutibilidade: três execuções independentes, mesmo endereço, mesmo VMA ocupante, exit 3.

## Por que não corrigi ainda

Duas correções possíveis, ambas com consequência não medida:

1. **Reservar o pool antes do primeiro mapeamento direto.** Exige saber se o guest espera o
   pool em `USER_MIN` ou se aceita qualquer endereço — a build real não foi observada além
   deste ponto.
2. **Realocar o bloco de 6 MiB** quando o guest reserva por cima. Exige provar que nenhum
   ponteiro guest já guardado aponta para o endereço antigo.

Escolher sem evidência seria trocar um bloqueio nomeado por uma corrupção silenciosa. A
próxima sessão deve medir qual das duas o guest realmente espera — por exemplo, registrando
se algum ponteiro guest em `[0x1000000000, 0x1000600000)` é lido depois da reserva.

## Instrumentação deixada no código

- `is_ps4_syscall_gate()` — nomeia o gate `INT 0x44` no relatório de falha.
- verificação de canário no frame do chamador, com as duas fontes lado a lado.
- `runtime_canary_address()` — expõe o valor para o reporter.
- logs de falha em `place()`, `reserve_range()` e `pool_reserve()`.
- `Logs` de sucesso permanecem silenciosos para não poluir a linha de base.

## Estado de verificação

| Item | Resultado |
|---|---|
| `bash build.sh` | exit 0 |
| `bash build.sh --test` | exit 0 |
| `python -m unittest discover -s tests` | exit 0, 29 testes |
| Boot até o bloqueio | exit 3, causa nomeada |
| **Primeiro frame / menu / gameplay** | **NÃO EXECUTADO** |

## Evidências

`docs/evidence/prompt04/`: `boot-03-canary-check.txt` (canário íntegro),
`boot-05-dmem-8192.txt` (pool refutado), `boot-08..12` (progressão do diagnóstico),
`boot-12-conflict-named.txt` (VMA conflitante nomeado), `build-test.txt`.
