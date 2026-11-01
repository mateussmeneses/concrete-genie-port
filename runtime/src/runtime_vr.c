/* VR tracking, social screen and VR service dialogs (libSceVrTracker, libSceSocialScreen,
 * libSceVr) on a build with no headset.
 *
 * These remain outside the first playable gate (PROMPT 04), but the imports must be registered
 * so the boot can reach the non-VR path instead of stopping at an unresolved trap.
 *
 * sceVrTrackerQueryMemory is what first blocks here (index 423). It is a capacity query: with no
 * tracker it reports zero bytes needed, which is a truthful answer, and the caller then skips
 * allocating tracker memory rather than reserving space for a tracker that will never run.
 *
 * Identified from the audited aerolib table (runtime/tools/aerolib.inl).
 */
#include "runtime.h"
#include <stdio.h>

/* libSceVrTracker / libSceVr error codes (0x80B0xxxx family used by the PS4 VR libraries). */
#define VR_NOT_INITIALIZED   ((int32_t)UINT32_C(0x80B00001))
#define VR_INVALID_ARG       ((int32_t)UINT32_C(0x80B00002))
#define VR_NOT_AVAILABLE     ((int32_t)UINT32_C(0x80B00003))

static int vr_tracker_initialized;

/* --- libSceVrTracker ------------------------------------------------------------------- */

static ABI int32_t vrtracker_init(void *params) {
    (void)params;
    static int reported;
    vr_tracker_initialized = 1;
    if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
        fprintf(stderr, "VrTracker: disabled; no headset or tracked controller\n");
    return 0;   /* the library loads; tracking itself has nothing to observe */
}

static ABI int32_t vrtracker_term(void) {
    vr_tracker_initialized = 0;
    return 0;
}

static ABI int32_t vrtracker_query_memory(void *query) {
    (void)query;
    /* A capacity query without a tracker: zero bytes are required. The caller must not
     * reserve memory for a subsystem it will never run, and must not receive a fabricated
     * size that would look like a working tracker. */
    return 0;
}

static ABI int32_t vrtracker_no_tracking(int32_t handle, void *out) {
    (void)handle; (void)out;
    if (!vr_tracker_initialized) return VR_NOT_INITIALIZED;
    return VR_NOT_AVAILABLE;
}

static ABI int32_t vrtracker_register_device(int32_t handle, void *device) {
    (void)handle;
    if (!device) return VR_INVALID_ARG;
    /* No headset means no device can be registered. */
    return VR_NOT_AVAILABLE;
}

/* --- libSceSocialScreen ---------------------------------------------------------------- */

static int social_screen_initialized;

static ABI int32_t socialscreen_initialize(void *params) {
    (void)params;
    static int reported;
    social_screen_initialized = 1;
    if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
        fprintf(stderr, "SocialScreen: disabled; non-VR output path\n");
    return 0;
}

static ABI int32_t socialscreen_terminate(void) {
    social_screen_initialized = 0;
    return 0;
}

static ABI int32_t socialscreen_set_mode(int32_t mode) {
    (void)mode;
    /* Separate-mode output only exists alongside a VR display. Refusing keeps the game on its
     * ordinary single-screen path instead of configuring a second, absent display. */
    return social_screen_initialized ? VR_NOT_AVAILABLE : VR_NOT_INITIALIZED;
}

static ABI int32_t socialscreen_separate_mode(int32_t handle, void *params) {
    (void)handle;
    if (!params) return VR_INVALID_ARG;
    return social_screen_initialized ? VR_NOT_AVAILABLE : VR_NOT_INITIALIZED;
}

/* --- libSceVr --------------------------------------------------------------------------- */

static ABI int32_t vr_service_dialog(int32_t handle, void *params) {
    (void)handle;
    if (!params) return VR_INVALID_ARG;
    return VR_NOT_AVAILABLE;
}

static const RuntimeExport exports[] = {
    /* libSceVrTracker */
    {"sceVrTrackerInit", vrtracker_init},
    {"sceVrTrackerTerm", vrtracker_term},
    {"sceVrTrackerQueryMemory", vrtracker_query_memory},
    {"sceVrTrackerGetResult", vrtracker_no_tracking},
    {"sceVrTrackerGetTime", vrtracker_no_tracking},
    {"sceVrTrackerUpdateMotionSensorData", vrtracker_no_tracking},
    {"sceVrTrackerRecalibrate", vrtracker_no_tracking},
    {"sceVrTrackerGpuSubmit", vrtracker_no_tracking},
    {"sceVrTrackerGpuWaitAndCpuProcess", vrtracker_no_tracking},
    {"sceVrTrackerRegisterDevice", vrtracker_register_device},
    {"sceVrTrackerUnregisterDevice", vrtracker_register_device},
    /* libSceSocialScreen */
    {"sceSocialScreenInitialize", socialscreen_initialize},
    {"sceSocialScreenTerminate", socialscreen_terminate},
    {"sceSocialScreenSetMode", socialscreen_set_mode},
    {"sceSocialScreenInitializeSeparateModeParameter", socialscreen_separate_mode},
    {"sceSocialScreenOpenSeparateMode", socialscreen_separate_mode},
    {"sceSocialScreenConfigureSeparateMode", socialscreen_separate_mode},
    {"sceSocialScreenCloseSeparateMode", socialscreen_separate_mode},
    {"sceSocialScreenDialogTerminate", socialscreen_separate_mode},
    /* libSceVr */
    {"sceVrServiceDialogInitialize", vr_service_dialog},
    {"sceVrServiceDialogOpen", vr_service_dialog},
    {"sceVrServiceDialogClose", vr_service_dialog},
    {"sceVrServiceDialogUpdateStatus", vr_service_dialog},
    {"sceVrServiceDialogTerminate", vr_service_dialog},
};

uintptr_t runtime_vr_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
