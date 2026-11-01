/* 3D audio (libSceAudio3d) on a build with no positional-audio output device.
 *
 * Concrete Genie uses this for the spatial mix. PROMPT 04 asks for audio to be audited against
 * what THIS build actually uses, not against what other ports assumed, and for no service to
 * return a success it cannot back. With no 3D output port open, every object/port call reports
 * the failure that makes the game fall back to its ordinary stereo path.
 *
 * Identified from the audited aerolib table (runtime/tools/aerolib.inl), 14 imports in this
 * eboot: sceAudio3dInitialize/Terminate, PortOpen/Close/Advance/Push/SetAttribute/
 * GetAttributesSupported, and ObjectReserve/Unreserve/SetAttributes.
 */
#include "runtime.h"
#include <stdio.h>

/* libSceAudio3d error codes (0x80268xxx family used by the PS4 audio libraries). */
#define A3D_NOT_INITIALIZED ((int32_t)UINT32_C(0x80268001))
#define A3D_INVALID_ARG     ((int32_t)UINT32_C(0x80268002))
#define A3D_NO_PORT         ((int32_t)UINT32_C(0x80268003))
#define A3D_NO_OBJECT       ((int32_t)UINT32_C(0x80268004))

static int a3d_initialized;

static ABI int32_t audio3d_initialize(void *params) {
    (void)params;
    static int reported;
    if (!a3d_initialized) {
        a3d_initialized = 1;
        if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
            fprintf(stderr, "Audio3d: subsystem initialised; no 3D output port available\n");
    }
    return 0;
}

static ABI int32_t audio3d_terminate(void) {
    a3d_initialized = 0;
    return 0;
}

static ABI int32_t audio3d_port_open(void *params, int32_t *port) {
    (void)params;
    if (!port) return A3D_INVALID_ARG;
    if (!a3d_initialized) return A3D_NOT_INITIALIZED;
    /* No 3D output device, so no port is handed out. */
    return A3D_NO_PORT;
}

static ABI int32_t audio3d_needs_init(void) {
    return a3d_initialized ? A3D_NO_PORT : A3D_NOT_INITIALIZED;
}

static ABI int32_t audio3d_invalid_arg(int32_t handle, void *data) {
    (void)handle;
    if (!data) return A3D_INVALID_ARG;
    return a3d_initialized ? A3D_NO_PORT : A3D_NOT_INITIALIZED;
}

static ABI int32_t audio3d_object_reserve(void *params, int32_t *object) {
    (void)params;
    if (!object) return A3D_INVALID_ARG;
    if (!a3d_initialized) return A3D_NOT_INITIALIZED;
    return A3D_NO_OBJECT;
}

static ABI int32_t audio3d_object_release(int32_t object) {
    (void)object;
    if (!a3d_initialized) return A3D_NOT_INITIALIZED;
    return A3D_NO_OBJECT;
}

static const RuntimeExport exports[] = {
    {"sceAudio3dInitialize", audio3d_initialize},
    {"sceAudio3dTerminate", audio3d_terminate},
    {"sceAudio3dPortOpen", audio3d_port_open},
    {"sceAudio3dPortClose", audio3d_needs_init},
    {"sceAudio3dPortAdvance", audio3d_needs_init},
    {"sceAudio3dPortPush", audio3d_invalid_arg},
    {"sceAudio3dPortSetAttribute", audio3d_invalid_arg},
    {"sceAudio3dPortGetAttributesSupported", audio3d_invalid_arg},
    {"sceAudio3dObjectReserve", audio3d_object_reserve},
    {"sceAudio3dObjectUnreserve", audio3d_object_release},
    {"sceAudio3dObjectSetAttributes", audio3d_invalid_arg},
    {"sceAudio3dAudioOutOpen", audio3d_port_open},
    {"sceAudio3dAudioOutClose", audio3d_needs_init},
    {"sceAudio3dAudioOutOutputs", audio3d_invalid_arg},
};

uintptr_t runtime_audio3d_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
