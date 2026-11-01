# Estado do projeto

Atualizado: 2026-11-01 UTC. **PROMPT 04 não atingiu o critério: não existe primeira cena
jogável.** O código guest executa, o Vulkan inicializa e as relocations são aplicadas, mas a
execução para antes de qualquer frame, num conflito de reserva de memória.

## Onde o port está

- Branch `bootstrap/windows`, runtime do MediEvil vendorizado (base `424f3ea`). Sem merge.
- Build reproduzível: `bash build.sh` e `bash build.sh --test`, ambos exit 0.
- **39 testes Python**, exit 0. Smoke sem dump funcionando.
- Dump `CUSA11875` (EU, APP_VER 01.07) identificado e auditado; pipeline executado até o boot.

## Estágios comprovadamente atingidos

| Estágio | Evidência |
|---|---|
| SELF → ELF | 103.382.639 bytes, 988 imports, 463.753 relocations, 64 módulos |
| Módulos ligados | 209 native bindings (libc, Fios2) |
| Cobertura de imports | 811/988 (com shim GPU) |
| Vulkan / janela | RTX 5060, Vulkan 1.4.357, swapchain, 327 HLE symbols |
| Imagem mapeada | 106.136.876 bytes, 9 segmentos, 465.785 relocations aplicadas |
| Memória guest | pools de 6 MiB + 128 MiB + 5.161.025.536 bytes |
| **Primeiro frame** | **NÃO. Bloqueio abaixo.** |

## Bloqueio atual (P0)

```
pool_reserve(address=0x1000000000, size=8 GiB, flags=0x90) -> 0x8002000c (NO_MEMORY)
reserve_range refused; VMA at 0x1000000000+6291456 kind=2 (KIND_DIRECT)
```

O guest pede reserva fixa de 8 GiB em `0x1000000000`; um mapeamento direto de 6 MiB do
próprio runtime já ocupa essa base, porque `find_free` sempre começa em `USER_MIN`.
A `libc` trata o erro como fatal, chama `abort`, cujo `INT 0x44` não tem handler e cai em
`ud2`. Exit 3, determinístico em 3 execuções.

Detalhe e hipóteses refutadas: `docs/MEMORY_AUDIT.md`.

## Correções de diagnóstico aplicadas

- `is_ps4_syscall_gate()`: o gate `INT 0x44` passa a ser nomeado no relatório de falha, em vez
  de aparecer como "read access to ffffffff".
- Verificação de canário no frame do chamador, com as duas fontes lado a lado.
- Logs de falha em `place`, `reserve_range`, `pool_reserve` (sucesso permanece silencioso).

## O que NÃO foi feito e por quê

Os tópicos de áudio, controles, shader cache, frame pacing e captura de frame do Prompt 04
**não foram auditados**. Todos dependem de uma cena visível: auditar shaders ou reprodução de
áudio sem frame seria descrever código, não observar comportamento. Registrar isso como
"feito" seria a mesma inflação de progresso que as regras do projeto proíbem.

## Estado de verificação

| Item | Estado |
|---|---|
| Build + testes nativos | PASSA, exit 0 |
| Suíte Python | PASSA, 39 testes, exit 0 |
| Boot até o bloqueio | exit 3, causa nomeada |
| **Frame / menu / gameplay** | **NÃO EXECUTADO** |
| Áudio, controles, GPU visual | **NÃO AUDITADOS** |
| Suíte herdada `runtime/tests` | vermelha por expectativas de GoW/MediEvil, não corrigida |

## Próxima ação

Determinar se o guest depende de `USER_MIN` para o pool: registrar leituras guest em
`[0x1000000000, 0x1000600000)` após a chamada de `pool_reserve`. Sem leituras, o bloco de
6 MiB pode ser realocado com segurança; com leituras, a ordem de inicialização deve ser
invertida. Critério completo em `docs/HANDOFF.md`.
