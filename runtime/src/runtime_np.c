/* NpToolkit2 (PSN) C++ object constructors that a UE4 title calls during startup even when
 * playing offline. Only constructors are provided: they initialise a caller-owned struct to
 * its zero/empty state and return nothing. No PSN service is stubbed here -- a call that
 * would need a network answer still reaches the unresolved trap.
 *
 * The struct size is measured from this build, not assumed: the guest passes rbp-0x398 to
 * InitParams and immediately reuses rbp-0x260 for the next object, so the constructor must
 * initialise 0x138 (312) bytes. That range ends 560 bytes below the stack canary at
 * rbp-0x30, so zeroing it cannot touch the canary.
 *
 * Evidence: docs/MEMORY_AUDIT.md, docs/evidence/prompt04/boot-16-content-profile.txt.
 */
#include "runtime.h"
#include <stdio.h>
#include <string.h>

/* sizeof(sce::Toolkit2::NP::V2::Core::Request::InitParams) for CUSA11875 (APP_VER 01.07).
 *
 * Measured from the caller's frame, not from a single gap: the object is placed at rbp-0x398,
 * the guest fills fields down to rbp-0x320, and the NEXT object it constructs starts at
 * rbp-0x238 (leaq -0x238(%rbp),%rdi at 0x40c782d). 0x398 - 0x238 = 0x160 = 352 bytes.
 *
 * An earlier reading took rbp-0x260 for the next object, which would have under-sized the
 * struct by 40 bytes and left guest-written fields uninitialised. The canary sits at rbp-0x30,
 * so 352 bytes from the base still ends 520 bytes clear of it. */
#define NP_INIT_PARAMS_SIZE 352

static ABI void np_init_params_ctor(void *self) {
    /* A default-constructed InitParams is all-zero in every observed use: the guest writes the
     * fields it cares about after this call. If `self` is not a guest pointer the write would
     * fault, so reject obviously invalid pointers instead of corrupting host memory. */
    if (!self) return;
    memset(self, 0, NP_INIT_PARAMS_SIZE);
}

/* SCE NpToolkit2 "not initialized" failure. The subsystem was never brought up, so this is the
 * truthful code; a zero here would make the remaining imports believe PSN is live. */
#define NP_NOT_INITIALIZED ((int32_t)UINT32_C(0x80550003))

static ABI int32_t np_core_init_refused(const void *params) {
    (void)params;
    /* The guest call site does `testl %eax,%eax; je <continue>` and its failure branch destroys
     * the object, re-checks the stack canary and returns cleanly, so refusing is handled. */
    static int reported;
    if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
        fprintf(stderr, "NpToolkit2: Core::init refused (0x%08x); no local PSN in this build\n",
                (unsigned)NP_NOT_INITIALIZED);
    return NP_NOT_INITIALIZED;
}

static ABI void np_init_params_dtor(void *self) {
    /* The matching destructor. InitParams owns no resources in this build (the constructor
     * zeroes a plain aggregate and the guest only stores scalars), so the destructor has
     * nothing to release; it must still exist or the guest stops at the import trap. */
    (void)self;
}

static const RuntimeExport exports[] = {
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsC1Ev", np_init_params_ctor},
    /* The complete-object and base-object variants share the same layout. */
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsC2Ev", np_init_params_ctor},
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsD1Ev", np_init_params_dtor},
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsD2Ev", np_init_params_dtor},
    /* Core::init(const InitParams&) is a SERVICE: it would have to bring PSN up. */
    {"_ZN3sce7Toolkit2NP2V24Core4initERKNS3_7Request10InitParamsE", np_core_init_refused},
};

uintptr_t runtime_np_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
