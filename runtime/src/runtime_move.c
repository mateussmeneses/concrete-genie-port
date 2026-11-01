/* PlayStation Move (libSceMove) for a build that runs with no motion controller attached.
 *
 * Concrete Genie paints with the Move controller or with the right analog stick; the port
 * keeps motion sensing outside the first playable gate (PROMPT 04), so this implements the
 * subsystem's real shape with the honest answer: "no device". Nothing here returns a fake
 * success, and no handle is invented.
 *
 * API identified from the audited aerolib table (runtime/tools/aerolib.inl) for the seven
 * libSceMove imports this eboot requests:
 *   j1ITE-EoJmE sceMoveInit          XX6wlxpHyeo sceMoveClose
 *   HzC60MfjJxU sceMoveOpen          ttU+JOhShl4 sceMoveReadStateLatest
 *   GWXTyxs4QbE sceMoveGetDeviceInfo IFQwtT2CeY0 sceMoveSetVibration
 *   tsZi60H4ypY sceMoveTerm
 *
 * The call site that first blocks is sceMoveInit (eboot 0x4132a25); its return value is stored
 * in r15 and later passed as `this` to a virtual call, so it must be a real status code, not a
 * fabricated pointer.
 */
#include "runtime.h"
#include <stdio.h>
#include <string.h>

/* libSceMove error codes (0x8093xxxx family, mirroring libScePad's 0x8092xxxx layout). */
#define MOVE_NOT_INITIALIZED ((int32_t)UINT32_C(0x80930000))
#define MOVE_INVALID_ARG     ((int32_t)UINT32_C(0x80930001))
#define MOVE_NO_DEVICE       ((int32_t)UINT32_C(0x80930002))

/* Handles are 0-based: the first connected controller is 0. With no hardware, every handle
 * lookup fails, so a non-negative handle never has to be invented. */
static int move_initialized;

static ABI int32_t move_init(void) {
    static int reported;
    if (!move_initialized) {
        move_initialized = 1;
        if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
            fprintf(stderr, "Move: subsystem initialised; no motion controller present\n");
    }
    return 0;   /* init succeeds: the subsystem exists, the device does not */
}

static ABI int32_t move_term(void) {
    move_initialized = 0;
    return 0;
}

static ABI int32_t move_open(int32_t user_id, int32_t *handle) {
    (void)user_id;
    if (!handle) return MOVE_INVALID_ARG;
    if (!move_initialized) return MOVE_NOT_INITIALIZED;
    /* No device is attached, so there is nothing to open. */
    return MOVE_NO_DEVICE;
}

static ABI int32_t move_close(int32_t handle) {
    (void)handle;
    if (!move_initialized) return MOVE_NOT_INITIALIZED;
    return MOVE_NO_DEVICE;
}

static ABI int32_t move_get_device_info(int32_t handle, void *info) {
    (void)handle;
    if (!info) return MOVE_INVALID_ARG;
    if (!move_initialized) return MOVE_NOT_INITIALIZED;
    return MOVE_NO_DEVICE;
}

static ABI int32_t move_read_state_latest(int32_t handle, void *data) {
    (void)handle;
    if (!data) return MOVE_INVALID_ARG;
    if (!move_initialized) return MOVE_NOT_INITIALIZED;
    /* No sampling happens without a device; the caller must handle "no data" rather than
     * receive a zeroed report that would look like a controller at rest. */
    return MOVE_NO_DEVICE;
}

static ABI int32_t move_set_vibration(int32_t handle, int32_t value) {
    (void)handle; (void)value;
    if (!move_initialized) return MOVE_NOT_INITIALIZED;
    return MOVE_NO_DEVICE;
}

static const RuntimeExport exports[] = {
    {"sceMoveInit", move_init},
    {"sceMoveTerm", move_term},
    {"sceMoveOpen", move_open},
    {"sceMoveClose", move_close},
    {"sceMoveGetDeviceInfo", move_get_device_info},
    {"sceMoveReadStateLatest", move_read_state_latest},
    {"sceMoveSetVibration", move_set_vibration},
};

uintptr_t runtime_move_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
