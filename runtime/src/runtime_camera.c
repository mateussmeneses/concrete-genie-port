/* PlayStation Camera (libSceCamera) on a build with no camera attached.
 *
 * Concrete Genie can paint using camera-tracked gestures. PROMPT 04 keeps camera and PS Move /
 * PSVR outside the first playable gate while requiring their imports to be registered, so this
 * answers with the truthful state: the library loads, no device is present.
 *
 * The key function is sceCameraIsAttached: a caller that asks "is there a camera?" must get a
 * real "no" so the game takes its analog-stick / no-gesture path. Every other call reports the
 * same absence rather than pretending to have produced a frame.
 *
 * Identified from the audited aerolib table (runtime/tools/aerolib.inl), 7 imports in this
 * eboot: GetFrameData, IsAttached, Open, SetConfig, SetVideoSync, Start, Stop.
 */
#include "runtime.h"
#include <stdio.h>

/* libSceCamera error codes (0x80258xxx family used by the PS4 camera library). */
#define CAM_NOT_INITIALIZED ((int32_t)UINT32_C(0x80258001))
#define CAM_INVALID_ARG     ((int32_t)UINT32_C(0x80258002))
#define CAM_DEVICE_NOT_FOUND ((int32_t)UINT32_C(0x80258003))

static ABI int32_t camera_is_attached(int32_t user_id) {
    (void)user_id;
    /* There is no camera. This is the answer that lets the game disable gesture painting and
     * use the controller path instead. */
    static int reported;
    if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
        fprintf(stderr, "Camera: no camera attached\n");
    return 0;
}

static ABI int32_t camera_open(int32_t user_id, void *params) {
    (void)user_id; (void)params;
    if (!params) return CAM_INVALID_ARG;
    return CAM_DEVICE_NOT_FOUND;
}

static ABI int32_t camera_needs_device(int32_t handle, void *data) {
    (void)handle;
    if (!data) return CAM_INVALID_ARG;
    return CAM_DEVICE_NOT_FOUND;
}

static ABI int32_t camera_set_config(int32_t handle, void *config) {
    (void)handle;
    if (!config) return CAM_INVALID_ARG;
    return CAM_DEVICE_NOT_FOUND;
}

static ABI int32_t camera_get_frame_data(int32_t handle, void *frame) {
    (void)handle;
    if (!frame) return CAM_INVALID_ARG;
    /* No frame exists. Returning success here would hand the caller an uninitialised buffer
     * that looks like a valid capture. */
    return CAM_DEVICE_NOT_FOUND;
}

static const RuntimeExport exports[] = {
    {"sceCameraIsAttached", camera_is_attached},
    {"sceCameraOpen", camera_open},
    {"sceCameraStart", camera_needs_device},
    {"sceCameraStop", camera_needs_device},
    {"sceCameraGetFrameData", camera_get_frame_data},
    {"sceCameraSetConfig", camera_set_config},
    {"sceCameraSetVideoSync", camera_needs_device},
};

uintptr_t runtime_camera_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
