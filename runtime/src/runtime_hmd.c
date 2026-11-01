/* PlayStation VR (libSceHmd) on a build with no headset attached.
 *
 * PROMPT 04 keeps PSVR outside the first playable gate but requires its imports to be
 * registered, and "funções obrigatórias para boot não podem ser ignoradas sem evidência".
 *
 * Evidence for every answer here (eboot CUSA11875, APP_VER 01.07):
 *   - sceHmdInitialize315 is called at 0x41252b1 and its return value is DISCARDED: the guest
 *     goes straight to `movl $0x170,%edi` at 0x41252b6 with no `testl %eax`. So answering with
 *     an error is a handled path, not a crash -- the game continues into its non-VR branch.
 *   - sceHmdOpen is the call that would produce a handle; with no headset it fails, so no
 *     handle is ever invented and every subsequent call rejects the invalid handle.
 *
 * The design mirrors runtime_move.c: the subsystem can be "initialised" while the DEVICE is
 * absent. That distinction is what lets the game disable VR cleanly instead of believing it has
 * a headset it must render to.
 */
#include "runtime.h"
#include <stdio.h>

/* libSceHmd error codes (0x80AFxxxx family used by the PS4 HMD library). */
#define HMD_NOT_INITIALIZED ((int32_t)UINT32_C(0x80AF0000))
#define HMD_INVALID_ARG     ((int32_t)UINT32_C(0x80AF0001))
#define HMD_INVALID_HANDLE  ((int32_t)UINT32_C(0x80AF0002))
#define HMD_DEVICE_NOT_FOUND ((int32_t)UINT32_C(0x80AF0003))

static int hmd_initialized;

static ABI int32_t hmd_initialize(void *params) {
    (void)params;
    static int reported;
    if (!hmd_initialized) {
        hmd_initialized = 1;
        if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
            fprintf(stderr, "Hmd: subsystem initialised; no PSVR headset present\n");
    }
    /* Initialisation of the library succeeds; there is simply no device to open. */
    return 0;
}

static ABI int32_t hmd_terminate(void) {
    hmd_initialized = 0;
    return 0;
}

static ABI int32_t hmd_open(int32_t user_id, int32_t *handle) {
    (void)user_id;
    if (!handle) return HMD_INVALID_ARG;
    if (!hmd_initialized) return HMD_NOT_INITIALIZED;
    /* No headset: nothing to open, and no handle may be fabricated. */
    return HMD_DEVICE_NOT_FOUND;
}

static ABI int32_t hmd_close(int32_t handle) {
    (void)handle;
    if (!hmd_initialized) return HMD_NOT_INITIALIZED;
    return HMD_INVALID_HANDLE;
}

static ABI int32_t hmd_get_device_information(int32_t handle, void *info) {
    (void)handle;
    if (!info) return HMD_INVALID_ARG;
    if (!hmd_initialized) return HMD_NOT_INITIALIZED;
    return HMD_INVALID_HANDLE;
}

static ABI int32_t hmd_get_field_of_view(int32_t handle, void *fov) {
    (void)handle;
    if (!fov) return HMD_INVALID_ARG;
    if (!hmd_initialized) return HMD_NOT_INITIALIZED;
    return HMD_INVALID_HANDLE;
}

static ABI int32_t hmd_get_2d_eye_offset(int32_t handle, void *offset) {
    (void)handle;
    if (!offset) return HMD_INVALID_ARG;
    if (!hmd_initialized) return HMD_NOT_INITIALIZED;
    return HMD_INVALID_HANDLE;
}

/* Reprojection is the VR compositor path. With no headset it stays inert: start does not
 * pretend to have submitted frames, and the buffer-size queries report zero rather than
 * sizing buffers for a display that does not exist. */
static ABI int32_t hmd_reprojection_initialize(void *params) {
    (void)params;
    return hmd_initialized ? 0 : HMD_NOT_INITIALIZED;
}

static ABI int32_t hmd_reprojection_buffer_size(void **out) {
    if (!out) return HMD_INVALID_ARG;
    *out = 0;
    return 0;
}

static ABI int32_t hmd_reprojection_not_started(void) {
    return HMD_DEVICE_NOT_FOUND;
}

static ABI int32_t hmd_reprojection_set_output_min_color(void *color) {
    (void)color;
    return hmd_initialized ? 0 : HMD_NOT_INITIALIZED;
}

static const RuntimeExport exports[] = {
    {"sceHmdInitialize315", hmd_initialize},
    {"sceHmdTerminate", hmd_terminate},
    {"sceHmdOpen", hmd_open},
    {"sceHmdClose", hmd_close},
    {"sceHmdGetDeviceInformation", hmd_get_device_information},
    {"sceHmdGetDeviceInformationByHandle", hmd_get_device_information},
    {"sceHmdGetFieldOfView", hmd_get_field_of_view},
    {"sceHmdGet2DEyeOffset", hmd_get_2d_eye_offset},
    {"sceHmdReprojectionInitialize", hmd_reprojection_initialize},
    {"sceHmdReprojectionQueryGarlicBuffSize", hmd_reprojection_buffer_size},
    {"sceHmdReprojectionQueryOnionBuffSize", hmd_reprojection_buffer_size},
    {"sceHmdReprojectionSetOutputMinColor", hmd_reprojection_set_output_min_color},
    {"sceHmdReprojectionStart", hmd_reprojection_not_started},
    {"sceHmdReprojectionStart2dVr", hmd_reprojection_not_started},
    {"sceHmdReprojectionStartWideNear", hmd_reprojection_not_started},
    {"sceHmdReprojectionStartWideNearWithOverlay", hmd_reprojection_not_started},
    {"sceHmdReprojectionStartWithOverlay", hmd_reprojection_not_started},
    {"sceHmdReprojectionStop", hmd_reprojection_not_started},
    {"sceHmdReprojectionSetDisplayBuffers", hmd_reprojection_not_started},
    {"sceHmdReprojectionUnsetDisplayBuffers", hmd_reprojection_not_started},
    {"sceHmdReprojectionQueryGarlicBuffAlign", hmd_reprojection_buffer_size},
    {"sceHmdReprojectionQueryOnionBuffAlign", hmd_reprojection_buffer_size},
};

uintptr_t runtime_hmd_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
