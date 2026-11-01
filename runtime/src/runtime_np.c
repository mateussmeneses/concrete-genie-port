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

/* sizeof(sce::Toolkit2::NP::V2::Core::Request::InitParams) for CUSA11875 (APP_VER 01.07),
 * measured from the caller's frame layout at eboot 0x40c762a. */
#define NP_INIT_PARAMS_SIZE 312

static ABI void np_init_params_ctor(void *self) {
    /* A default-constructed InitParams is all-zero in every observed use: the guest writes the
     * fields it cares about after this call. If `self` is not a guest pointer the write would
     * fault, so reject obviously invalid pointers instead of corrupting host memory. */
    if (!self) return;
    memset(self, 0, NP_INIT_PARAMS_SIZE);
}

static const RuntimeExport exports[] = {
    /* sce::Toolkit2::NP::V2::Core::Request::InitParams::InitParams() */
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsC1Ev", np_init_params_ctor},
    /* The complete-object and base-object variants share the same layout. */
    {"_ZN3sce7Toolkit2NP2V24Core7Request10InitParamsC2Ev", np_init_params_ctor},
};

uintptr_t runtime_np_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
