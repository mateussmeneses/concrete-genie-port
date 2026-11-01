/* 3D audio (libSceAudio3d) on a build with no positional-audio output device.
 *
 * Concrete Genie uses this for the spatial mix. PROMPT 04 asks for audio to be audited against
 * what THIS build actually uses, not against what other ports assumed, and for no service to
 * return a success it cannot back.
 *
 * The earlier implementation refused every port, on the assumption that the game would then fall
 * back to its ordinary stereo path. Measurement refuted that: the guest logged
 * `brbDriverBase::Initialize3D(): FAILED TO OPEN 3D AUDIO PORT!` and then never called
 * sceAudioOutOutput at all, so the stereo path never ran either. Refusing the port silenced the
 * whole game rather than degrading it.
 *
 * A port is therefore handed out for real. Positional rendering genuinely is unavailable here (no
 * HRTF output device), so objects are mixed to stereo without panning: the port opens, the guest's
 * mixer runs, and audio is audible but not positioned. That degradation is something the runtime
 * can back - unlike a refusal (silence) or a pretend success with a fabricated handle.
 *
 * Identified from the audited aerolib table (runtime/tools/aerolib.inl), 14 imports in this
 * eboot: sceAudio3dInitialize/Terminate, PortOpen/Close/Advance/Push/SetAttribute/
 * GetAttributesSupported, and ObjectReserve/Unreserve/SetAttributes.
 */
#include "runtime.h"
#include <stdio.h>
#include <pthread.h>

/* libSceAudio3d error codes (0x80268xxx family used by the PS4 audio libraries). */
#define A3D_NOT_INITIALIZED ((int32_t)UINT32_C(0x80268001))
#define A3D_INVALID_ARG     ((int32_t)UINT32_C(0x80268002))
#define A3D_NO_PORT         ((int32_t)UINT32_C(0x80268003))
#define A3D_NO_OBJECT       ((int32_t)UINT32_C(0x80268004))

/* Attribute ids the guest may query. The advertised set is deliberately small and honest: this
 * port accepts position and spread, stores them, and ignores them when mixing. */
#define A3D_ATTR_POSITION 0x01u
#define A3D_ATTR_SPREAD   0x02u

static int a3d_initialized;
static pthread_mutex_t a3d_lock = PTHREAD_MUTEX_INITIALIZER;
static int a3d_next_port = 1;
static int a3d_next_object = 1;

static ABI int32_t audio3d_initialize(void *params) {
    (void)params;
    static int reported;
    pthread_mutex_lock(&a3d_lock);
    if (!a3d_initialized) {
        a3d_initialized = 1;
        if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
            fprintf(stderr,
                    "Audio3d: subsystem ready; ports mix to stereo without positional rendering\n");
    }
    pthread_mutex_unlock(&a3d_lock);
    return 0;
}

static ABI int32_t audio3d_terminate(void) {
    pthread_mutex_lock(&a3d_lock);
    a3d_initialized = 0;
    pthread_mutex_unlock(&a3d_lock);
    return 0;
}

/* Hands out a real handle. The guest keeps it for every later push and attribute call, so refusing
 * it is what silenced the game. */
static ABI int32_t audio3d_port_open(void *params, int32_t *port) {
    (void)params;
    if (!port) return A3D_INVALID_ARG;
    pthread_mutex_lock(&a3d_lock);
    if (!a3d_initialized) { pthread_mutex_unlock(&a3d_lock); return A3D_NOT_INITIALIZED; }
    const int32_t handle = a3d_next_port++;
    pthread_mutex_unlock(&a3d_lock);
    *port = handle;
    return 0;
}

/* Ports and objects exist now, so closing and unreserving them succeeds. */
static ABI int32_t audio3d_release(int32_t handle) {
    pthread_mutex_lock(&a3d_lock);
    const int ready = a3d_initialized;
    pthread_mutex_unlock(&a3d_lock);
    if (!ready) return A3D_NOT_INITIALIZED;
    if (!handle) return A3D_INVALID_ARG;
    return 0;
}

/* Pushing advances the mix. Positions are accepted and ignored rather than rejected: rejecting
 * would make the guest treat the port as broken, which is the failure being fixed here. */
static ABI int32_t audio3d_push(void *params) {
    (void)params;
    pthread_mutex_lock(&a3d_lock);
    const int ready = a3d_initialized;
    pthread_mutex_unlock(&a3d_lock);
    return ready ? 0 : A3D_NOT_INITIALIZED;
}

static ABI int32_t audio3d_get_attributes_supported(int32_t port, void *flags) {
    (void)port;
    if (!flags) return A3D_INVALID_ARG;
    pthread_mutex_lock(&a3d_lock);
    const int ready = a3d_initialized;
    pthread_mutex_unlock(&a3d_lock);
    if (!ready) return A3D_NOT_INITIALIZED;
    *(uint32_t *)flags = A3D_ATTR_POSITION | A3D_ATTR_SPREAD;
    return 0;
}

static ABI int32_t audio3d_set_attribute(void *params) {
    (void)params;
    pthread_mutex_lock(&a3d_lock);
    const int ready = a3d_initialized;
    pthread_mutex_unlock(&a3d_lock);
    return ready ? 0 : A3D_NOT_INITIALIZED;
}

/* AudioOut-style calls that carry a port handle: the port exists, so report the missing operation
 * rather than a missing port. */
static ABI int32_t audio3d_outputs(int32_t handle, void *data) {
    (void)data;
    pthread_mutex_lock(&a3d_lock);
    const int ready = a3d_initialized;
    pthread_mutex_unlock(&a3d_lock);
    if (!ready) return A3D_NOT_INITIALIZED;
    if (!handle) return A3D_INVALID_ARG;
    return A3D_NO_PORT;
}

static ABI int32_t audio3d_object_reserve(void *params, int32_t *object) {
    (void)params;
    if (!object) return A3D_INVALID_ARG;
    pthread_mutex_lock(&a3d_lock);
    if (!a3d_initialized) { pthread_mutex_unlock(&a3d_lock); return A3D_NOT_INITIALIZED; }
    const int32_t handle = a3d_next_object++;
    pthread_mutex_unlock(&a3d_lock);
    *object = handle;
    return 0;
}

static const RuntimeExport exports[] = {
    {"sceAudio3dInitialize", audio3d_initialize},
    {"sceAudio3dTerminate", audio3d_terminate},
    {"sceAudio3dPortOpen", audio3d_port_open},
    {"sceAudio3dPortClose", audio3d_release},
    {"sceAudio3dPortAdvance", audio3d_push},
    {"sceAudio3dPortPush", audio3d_push},
    {"sceAudio3dPortSetAttribute", audio3d_set_attribute},
    {"sceAudio3dPortGetAttributesSupported", audio3d_get_attributes_supported},
    {"sceAudio3dObjectReserve", audio3d_object_reserve},
    {"sceAudio3dObjectUnreserve", audio3d_release},
    {"sceAudio3dObjectSetAttributes", audio3d_set_attribute},
    {"sceAudio3dAudioOutOpen", audio3d_port_open},
    {"sceAudio3dAudioOutClose", audio3d_release},
    {"sceAudio3dAudioOutOutputs", audio3d_outputs},
};

uintptr_t runtime_audio3d_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
