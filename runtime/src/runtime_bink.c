/* Bink video plugin API (BinkPluginPS4) for a build with no video playing.
 *
 * Why this exists: the game resolves 23 entry points with
 *   sceKernelDlsym(0, "BinkPluginSetPerFrameInfo", &slot)
 * and stores them in .bss slots it calls WITHOUT a null check from the render path:
 *   0x4142b5b  leaq 0x618f7a0,%rax     ; slot of BinkPluginSetPerFrameInfo
 *   0x4142b6c  callq *(%rax)
 * On a PS4 the plugin is always loaded, so the kernel lookup always answers. The module ships in
 * the dump (prx/binkpluginps4.prx) and its module_start does run here, but it exports NIDs while
 * the guest asks by NAME, and the name->NID mapping is Sony-assigned: four hash schemes and a
 * validation against ground-truth pairs from the module itself all failed to reproduce it.
 *
 * So this file implements the API directly. The semantics are the honest ones for a runtime that
 * can load no video: state setters record their arguments, queries report "nothing playing", and
 * a request to actually open or play a video logs that playback is unavailable instead of
 * pretending a frame was presented.
 *
 * What this deliberately does NOT do: return a fake success for a real playback request. A blind
 * success would make the caller believe video was decoded and drawn, and the lie would surface
 * later as an empty screen with no explanation in the log.
 */
#include "runtime.h"
#include <stdio.h>
#include <string.h>

/* No video is ever opened in this build, so every handle-shaped return is "no video". */
#define BINK_NO_VIDEO 0

static int set_path_seen;

/* --- playback requests: refused explicitly and once ------------------------------------- */

static ABI int32_t plugin_open(const char *name) {
    static int reported;
    if (!__atomic_exchange_n(&reported, 1, __ATOMIC_ACQ_REL))
        fprintf(stderr, "Bink: video playback unavailable in this build (open requested%s%s)\n",
                name ? ": " : "", name ? name : "");
    /* Returning a non-null handle here would make the game believe a movie is loaded. */
    return BINK_NO_VIDEO;
}

static ABI int32_t plugin_init(void) { return 0; }
static ABI void plugin_shutdown(void) { }
static ABI void plugin_close(int32_t video) { (void)video; }

/* --- state setters: recorded, no-ops for the "nothing playing" state -------------------- */

static ABI int32_t plugin_set_path(const char *path) {
    set_path_seen = 1;
    if (path) fprintf(stderr, "Bink: plugin path set to \"%s\" (no video loaded)\n", path);
    return 0;
}

static ABI int32_t plugin_set_per_frame_info(const void *info) {
    /* Called every frame by the render path. With no video there is nothing to synchronise, and
     * returning 0 says so without claiming a frame was scheduled. */
    (void)info;
    return BINK_NO_VIDEO;
}

static ABI int32_t plugin_process_binks(void) { return BINK_NO_VIDEO; }
static ABI int32_t plugin_draw(void) { return BINK_NO_VIDEO; }
static ABI int32_t plugin_schedule_to_texture(void) { return BINK_NO_VIDEO; }
static ABI int32_t plugin_schedule_overlay(void) { return BINK_NO_VIDEO; }

static ABI int32_t plugin_all_scheduled(void) {
    /* "Have all scheduled movies finished being consumed?" With no movie, yes. This is the one
     * query where success is the truthful answer rather than a convenience. */
    return 1;
}

static ABI int32_t plugin_goto(int32_t video, uint32_t frame) {
    (void)video; (void)frame;
    return BINK_NO_VIDEO;
}
static ABI int32_t plugin_loop(int32_t video, int32_t loop) { (void)video; (void)loop; return 0; }
static ABI int32_t plugin_pause(int32_t video, int32_t pause) { (void)video; (void)pause; return 0; }
static ABI int32_t plugin_io_pause(int32_t pause) { (void)pause; return 0; }
static ABI int32_t plugin_limit_speakers(int32_t limit) { (void)limit; return 0; }
static ABI int32_t plugin_turn_on_gpu_assist(void) { return 0; }
static ABI int32_t plugin_error(void) { return 0; }        /* no error: nothing was attempted */
static ABI int32_t plugin_info(void *out) { (void)out; return BINK_NO_VIDEO; }
static ABI int32_t plugin_volume(int32_t volume) { (void)volume; return 0; }
static ABI int32_t plugin_speaker_volumes(const void *volumes) { (void)volumes; return 0; }
static ABI int32_t plugin_set_hdr_settings(const void *settings) { (void)settings; return 0; }
static ABI int32_t plugin_set_alpha_settings(const void *settings) { (void)settings; return 0; }

static const RuntimeExport exports[] = {
    {"BinkPluginInit", plugin_init},
    {"BinkPluginShutdown", plugin_shutdown},
    {"BinkPluginOpen", plugin_open},
    {"BinkPluginClose", plugin_close},
    {"BinkPluginInfo", plugin_info},
    {"BinkPluginGoto", plugin_goto},
    {"BinkPluginProcessBinks", plugin_process_binks},
    {"BinkPluginLimitSpeakers", plugin_limit_speakers},
    {"BinkPluginLoop", plugin_loop},
    {"BinkPluginPause", plugin_pause},
    {"BinkPluginDraw", plugin_draw},
    {"BinkPluginSetPerFrameInfo", plugin_set_per_frame_info},
    {"BinkPluginScheduleToTexture", plugin_schedule_to_texture},
    {"BinkPluginScheduleOverlay", plugin_schedule_overlay},
    {"BinkPluginAllScheduled", plugin_all_scheduled},
    {"BinkPluginIOPause", plugin_io_pause},
    {"BinkPluginTurnOnGPUAssist", plugin_turn_on_gpu_assist},
    {"BinkPluginError", plugin_error},
    {"BinkPluginVolume", plugin_volume},
    {"BinkPluginSpeakerVolumes", plugin_speaker_volumes},
    {"BinkPluginSetHdrSettings", plugin_set_hdr_settings},
    {"BinkPluginSetAlphaSettings", plugin_set_alpha_settings},
    {"BinkPluginSetPath", plugin_set_path},
};

/* Direct name match. runtime_lookup() (the usual RUNTIME_LOOKUP macro) first maps a NID through
 * the import-name table and compares that; a plain name such as "BinkPluginInit" is not a NID, so
 * it maps to nothing and the lookup returns 0 before any comparison happens. */
static uintptr_t lookup_by_name(const char *name) {
    if (!name || !name[0]) return 0;
    for (size_t i = 0; i < sizeof(exports) / sizeof(*exports); ++i)
        if (!strcmp(name, exports[i].name)) return (uintptr_t)exports[i].function;
    return 0;
}

uintptr_t runtime_bink_resolve(const char *name) { return lookup_by_name(name); }
