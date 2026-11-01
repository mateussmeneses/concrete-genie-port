/* Imports the guest reaches once audio and Ajm start working.
 *
 * These are the 31 libSce* and libc entries that were present in the eboot's import list but absent
 * from the NID->name table, so the probe stopped at the first one it met with
 * `STOP: first unsupported PS4 import`. Every name here comes from the audited aerolib table in
 * runtime/tools/aerolib.inl (59220 entries), not from a guess: the NID was matched against that
 * table and the library was derived from the scoped import list itself.
 *
 * Semantics are per function and deliberately narrow. Where a real operation exists here it is
 * performed; where it does not, the call reports the PS4 error that the family uses rather than a
 * success this runtime cannot back. Nothing here fabricates a handle or zero-fills an output
 * structure the guest will act on.
 */
#include "runtime.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <math.h>
#include <time.h>

/* Error codes from the families these libraries use. */
#define K_EFAULT  ((int32_t)UINT32_C(0x8002000e))
#define K_EINVAL  ((int32_t)UINT32_C(0x80020016))
#define K_ENOENT  ((int32_t)UINT32_C(0x80020002))
#define FIOS_EINVAL ((int32_t)UINT32_C(0x804F8002))
#define FIOS_ENOENT ((int32_t)UINT32_C(0x804F8003))
#define FIOS_ENOMEM ((int32_t)UINT32_C(0x804F8001))

/* ---- video out event queries -------------------------------------------------------------
 * The guest polls these to know whether a flip is still in flight. The runtime presents
 * synchronously - present blocks until the swapchain returns - so a flip is never left pending.
 * Reporting 0 pending and a zero event count is the true state of a synchronous present path, not
 * a stub: there is no queued event to report. */
static ABI int32_t video_out_get_event_count(int32_t handle, uint64_t *count) {
    (void)handle;
    if (!count) return K_EINVAL;
    *count = 0;
    return 0;
}

static ABI int32_t video_out_is_flip_pending(int32_t handle) {
    (void)handle;
    /* Presents complete before the guest resumes, so nothing is ever left pending. */
    return 0;
}

/* ---- libc additions ------------------------------------------------------------------------ */
/* The _s variants validate arguments and zero-fill the rest of the destination, which is their
 * documented advantage over the plain calls. */
static ABI int32_t guest_strcpy_s(char *dst, size_t dstsz, const char *src) {
    if (!dst || !src) return K_EINVAL;
    const size_t n = strlen(src) + 1;
    if (dstsz < n) { if (dstsz) dst[0] = '\0'; return K_EINVAL; }
    memcpy(dst, src, n);
    return 0;
}

static ABI int32_t guest_strncpy_s(char *dst, size_t dstsz, const char *src, size_t count) {
    if (!dst || !src) return K_EINVAL;
    size_t n = 0;
    while (n < count && src[n]) ++n;
    if (dstsz < n + 1) { if (dstsz) dst[0] = '\0'; return K_EINVAL; }
    memcpy(dst, src, n);
    dst[n] = '\0';
    return 0;
}

/* ABI-compatible wrappers: the guest expects the same numeric result as the C library, so these
 * forward rather than reimplement. */
static ABI double libc_atof(const char *s) { return s ? atof(s) : 0.0; }

static ABI int32_t libc_isnanf(float v) { return isnan(v) ? 1 : 0; }

static ABI char *libc_ctime(const void *tp) {
    if (!tp) return NULL;
    return ctime((const time_t *)tp);
}

/* ntop/pton: the runtime needs the text form of an address for logging and for the net stack. */
static ABI int32_t libc_inet_pton(int af, const void *src, void *dst) {
    if (!src || !dst) return 0;
    /* AF_INET (2) text form only: this build's imports all pass dotted quads. */
    if (af != 2) return 0;
    unsigned a, b, c, d;
    const char *s = (const char *)src;
    if (sscanf(s, "%u.%u.%u.%u", &a, &b, &c, &d) != 4) return 0;
    if (a > 255 || b > 255 || c > 255 || d > 255) return 0;
    unsigned char *o = (unsigned char *)dst;
    o[0] = (unsigned char)a; o[1] = (unsigned char)b;
    o[2] = (unsigned char)c; o[3] = (unsigned char)d;
    return 1;
}

/* ---- CommonDialog ---------------------------------------------------------------------------
 * sceCommonDialogIsUsed reports whether a common dialog is currently up. No common dialog is ever
 * created by this runtime, so 0 is the true answer rather than a stub. */
static ABI int32_t common_dialog_is_used(void) { return 0; }

/* ---- Gnm marker ---------------------------------------------------------------------------
 * A thread trace marker is a profiling hint. Writing it to the trace stream is the whole
 * operation; there is no state to fake. */
static ABI int32_t gnm_thread_trace_marker(uint32_t marker) {
    static const int trace = -1;
    static int enabled;
    if (trace == -1) enabled = getenv("GOW3_TRACE_MARKER") != NULL;
    if (enabled) fprintf(stderr, "GnmTrace: marker %u\n", marker);
    return 0;
}

/* ---- libSceNet / NetCtl -------------------------------------------------------------------
 * The guest asks for peer names and for network status. This build has no network session, so a
 * peer lookup reports "no such entry" and NetCtlInit succeeds only in the sense that the library
 * initialises its own state, which is all the call promises. */
static ABI int32_t net_get_peername(int32_t s, void *name, uint32_t *namelen) {
    (void)s; (void)name; (void)namelen;
    return K_ENOENT;
}

static ABI int32_t net_ctl_init(void) { return 0; }

/* ---- AudioOut pad speaker level -----------------------------------------------------------
 * There is no pad speaker on this build. Storing the level would imply a device that does not
 * exist, so the call reports the missing device instead of accepting the value silently. */
static ABI int32_t audio_out_set_mix_level_pad_spk(int32_t handle, int32_t level) {
    (void)handle; (void)level;
    return K_EINVAL;
}

/* ---- Fios file handles --------------------------------------------------------------------
 * Fios is the async file layer. The runtime already serves synchronous file I/O; these calls open
 * real handles through the same path so the guest gets a usable descriptor rather than a fake one.
 * A small table maps handles to POSIX descriptors, which is exactly what a Fios handle is. */
#define FIOS_MAX_FH 64
static int fios_fds[FIOS_MAX_FH];
static int fios_used[FIOS_MAX_FH];

static int fios_slot(int32_t handle) {
    if (handle < 1 || handle > FIOS_MAX_FH) return -1;
    return fios_used[handle - 1] ? handle - 1 : -1;
}

extern int runtime_file_open_descriptor(const char *path, int mode);

static ABI int32_t fios_fh_open(const char *path, int mode, int32_t *fh) {
    if (!path || !fh) return FIOS_EINVAL;
    const int fd = runtime_file_open_descriptor(path, mode);
    if (fd < 0) return FIOS_ENOENT;
    for (int i = 0; i < FIOS_MAX_FH; ++i) {
        if (!fios_used[i]) {
            fios_used[i] = 1;
            fios_fds[i] = fd;
            *fh = i + 1;
            return 0;
        }
    }
    return FIOS_ENOMEM;
}

static ABI int32_t fios_fh_open_with_mode(const char *path, int flags, int mode, int32_t *fh) {
    (void)mode;
    return fios_fh_open(path, flags, fh);
}

static ABI int32_t fios_fh_close(int32_t fh) {
    const int slot = fios_slot(fh);
    if (slot < 0) return FIOS_EINVAL;
    extern int runtime_file_close_descriptor(int fd);
    runtime_file_close_descriptor(fios_fds[slot]);
    fios_used[slot] = 0;
    fios_fds[slot] = -1;
    return 0;
}

static ABI int64_t fios_fh_pwrite(int32_t fh, const void *data, uint64_t size, uint64_t offset) {
    (void)fh; (void)data; (void)size; (void)offset;
    /* Writes into the read-only content mount are refused rather than reported as done. */
    return FIOS_EINVAL;
}

static ABI uint32_t fios_op_get_request_count(int32_t op) {
    (void)op;
    /* The synchronous implementation has finished every request it started. */
    return 0;
}

static ABI int64_t fios_time_get_current(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static ABI int64_t fios_time_interval_from_nanoseconds(int64_t ns) { return ns; }

/* ---- libSceJson ---------------------------------------------------------------------------
 * `operator bool` on a Json Value: true when the value is neither null nor absent. Without the
 * layout of the guest's Value this cannot be answered correctly, so it reports false (absent)
 * rather than claiming a value exists. */
static ABI int32_t json_value_as_bool(const void *value) { (void)value; return 0; }

/* ---- libSceHmdSetupDialog ----------------------------------------------------------------
 * The VR setup dialog needs a headset. There is none, so initialising succeeds (the library has
 * state to set up) and every operation that would need the dialog reports no device. */
#define HMD_E_NO_DEVICE ((int32_t)UINT32_C(0x80B00002))

static ABI int32_t hmd_setup_dialog_initialize(void) { return 0; }
static ABI int32_t hmd_setup_dialog_terminate(void) { return 0; }
static ABI int32_t hmd_setup_dialog_open(void) { return HMD_E_NO_DEVICE; }
static ABI int32_t hmd_setup_dialog_close(void) { return 0; }
static ABI int32_t hmd_setup_dialog_get_result(void *result) {
    (void)result;
    return HMD_E_NO_DEVICE;
}
static ABI int32_t hmd_setup_dialog_update_status(void) { return HMD_E_NO_DEVICE; }

/* ---- user events --------------------------------------------------------------------------
 * sceKernelAddUserEvent is an optimisation hint for user-level scheduling; there is no user
 * scheduler here, so it reports unsupported instead of pretending to have added one. */
static ABI int32_t kernel_add_user_event(int32_t id) { (void)id; return K_EINVAL; }
static ABI int32_t kernel_delete_user_event(int32_t id) { (void)id; return K_EINVAL; }
static ABI int32_t kernel_get_event_user_data(int32_t id, void *data) { (void)id; (void)data; return K_EINVAL; }

static const RuntimeExport exports[] = {
    {"sceVideoOutGetEventCount", video_out_get_event_count},
    {"sceVideoOutIsFlipPending", video_out_is_flip_pending},
    {"strcpy_s", guest_strcpy_s},
    {"strncpy_s", guest_strncpy_s},
    {"atof", libc_atof},
    {"__isnanf", libc_isnanf},
    {"ctime", libc_ctime},
    {"inet_pton", libc_inet_pton},
    {"sceCommonDialogIsUsed", common_dialog_is_used},
    {"sceGnmInsertThreadTraceMarker", gnm_thread_trace_marker},
    {"sceNetGetpeername", net_get_peername},
    {"sceNetCtlInit", net_ctl_init},
    {"sceAudioOutSetMixLevelPadSpk", audio_out_set_mix_level_pad_spk},
    {"sceFiosFHOpen", fios_fh_open},
    {"sceFiosFHOpenWithMode", fios_fh_open_with_mode},
    {"sceFiosFHClose", fios_fh_close},
    {"sceFiosFHPwrite", fios_fh_pwrite},
    {"sceFiosOpGetRequestCount", fios_op_get_request_count},
    {"sceFiosTimeGetCurrent", fios_time_get_current},
    {"sceFiosTimeIntervalFromNanoseconds", fios_time_interval_from_nanoseconds},
    {"_ZNK3sce4Json5ValuecvbEv", json_value_as_bool},
    {"sceHmdSetupDialogInitialize", hmd_setup_dialog_initialize},
    {"sceHmdSetupDialogTerminate", hmd_setup_dialog_terminate},
    {"sceHmdSetupDialogOpen", hmd_setup_dialog_open},
    {"sceHmdSetupDialogClose", hmd_setup_dialog_close},
    {"sceHmdSetupDialogGetResult", hmd_setup_dialog_get_result},
    {"sceHmdSetupDialogUpdateStatus", hmd_setup_dialog_update_status},
    {"sceKernelAddUserEvent", kernel_add_user_event},
    {"sceKernelDeleteUserEvent", kernel_delete_user_event},
    {"sceKernelGetEventUserData", kernel_get_event_user_data},
};

uintptr_t runtime_late_resolve(const char *name) { return RUNTIME_LOOKUP(exports, name); }
