#include "host/midi_fx_api_v1.h"
#include "host/plugin_api_v1.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "impressive_chords_data.h"
#include "impressive_chords_params.h"

#define MAX_PENDING 256
#define MAX_ACTIVE_PER_NOTE 32
#define RELEASE_STAGGER_SAMPLES 64   /* ~1.5ms @44.1kHz per voice */

static const host_api_v1_t *g_host = NULL;

typedef struct {
    uint8_t status;
    uint8_t note;
    uint8_t velocity;
    uint8_t input_note;    // Pad note that queued this event (for release cancel)
    int delay_samples;
} pending_note_t;

typedef struct {
    int preset_idx;
    int base_note;
    int transpose;
    int invert;
    int strum;
    int tilt;
    int articulate;
    int length;

    // Currently-audible voices per input note (populated when note-on actually fires)
    uint8_t active_notes[128][MAX_ACTIVE_PER_NOTE];
    int active_counts[128];

    // Pad currently held per input note — while held, length-timer note-offs
    // are suppressed so the chord sustains for the full hold duration.
    uint8_t pad_held[128];

    pending_note_t pending[MAX_PENDING];
    int pending_count;
} ic_instance_t;

static void* ic_create_instance(const char *module_dir, const char *config_json) {
    ic_instance_t *inst = calloc(1, sizeof(ic_instance_t));
    if (!inst) return NULL;

    inst->preset_idx = 0;
    inst->base_note = 48; // Default to C2
    inst->transpose = 0;
    inst->invert = 0;
    inst->strum = 0;
    inst->tilt = 0;
    inst->articulate = 1;
    inst->length = 200; // Default 200ms
    inst->pending_count = 0;

    return inst;
}

static void ic_destroy_instance(void *instance) {
    free(instance);
}

static int queue_note(ic_instance_t *inst, uint8_t status, uint8_t note,
                      uint8_t velocity, uint8_t input_note, int delay_samples) {
    if (inst->pending_count >= MAX_PENDING) return 0;
    pending_note_t *p = &inst->pending[inst->pending_count++];
    p->status = status;
    p->note = note;
    p->velocity = velocity;
    p->input_note = input_note;
    p->delay_samples = delay_samples;
    return 1;
}

static inline void active_append(ic_instance_t *inst, uint8_t input_note, uint8_t voice_note) {
    if (input_note >= 128) return;
    int n = inst->active_counts[input_note];
    if (n < MAX_ACTIVE_PER_NOTE) {
        inst->active_notes[input_note][n] = voice_note;
        inst->active_counts[input_note] = n + 1;
    }
}

// Remove first matching voice from active_notes[input_note]; return 1 if found.
static inline int active_remove_one(ic_instance_t *inst, uint8_t input_note, uint8_t voice_note) {
    if (input_note >= 128) return 0;
    int n = inst->active_counts[input_note];
    for (int i = 0; i < n; i++) {
        if (inst->active_notes[input_note][i] == voice_note) {
            for (int j = i; j < n - 1; j++) {
                inst->active_notes[input_note][j] = inst->active_notes[input_note][j + 1];
            }
            inst->active_counts[input_note] = n - 1;
            return 1;
        }
    }
    return 0;
}

static int ic_process_midi(void *instance,
                        const uint8_t *in_msg, int in_len,
                        uint8_t out_msgs[][3], int out_lens[],
                        int max_out) {
    ic_instance_t *inst = (ic_instance_t *)instance;
    if (!inst || in_len < 3) return 0;

    uint8_t status = in_msg[0];
    uint8_t note = in_msg[1];
    uint8_t vel = in_msg[2];

    uint8_t type = status & 0xF0;
    uint8_t chan = status & 0x0F;

    if (type == 0x90 && vel > 0) { // Note On
        inst->pad_held[note] = 1;
        int chord_idx = note - inst->base_note;
        if (chord_idx >= 0 && chord_idx < 48) {
            const preset_def_t *preset = &g_presets[inst->preset_idx];
            const chord_def_t *chord = &preset->chords[chord_idx];

            int out_count = 0;
            // Don't reset active_counts[note] — accumulate across overlapping presses
            // so a release can emit note-offs for every audible voice.

            int N = chord->count;
            int order[12];
            for (int i = 0; i < N; i++) order[i] = i;

            // Articulate implies different strum order
            if (inst->articulate == 2) { // Outside-In
                int left = 0;
                int right = N - 1;
                for (int i = 0; i < N; i++) {
                    if (i % 2 == 0) order[i] = left++;
                    else order[i] = right--;
                }
            } else if (inst->articulate == 3) { // High to Low
                for (int i = 0; i < N; i++) order[i] = N - 1 - i;
            } else if (inst->articulate == 4) { // Even/Odd
                int idx = 0;
                for (int i = 0; i < N; i += 2) order[idx++] = i;
                for (int i = 1; i < N; i += 2) order[idx++] = i;
            } else if (inst->articulate == 5) { // Inside-Out
                int left = (N - 1) / 2;
                int right = left + 1;
                for (int i = 0; i < N; i++) {
                    if (i % 2 == 0) {
                        if (left >= 0) order[i] = left--;
                        else order[i] = right++;
                    } else {
                        if (right < N) order[i] = right++;
                        else order[i] = left--;
                    }
                }
            } else if (inst->articulate == 6) { // Odd/Even
                int idx = 0;
                for (int i = 1; i < N; i += 2) order[idx++] = i;
                for (int i = 0; i < N; i += 2) order[idx++] = i;
            }

            int sample_rate = g_host ? g_host->sample_rate : 44100;
            int strum_samples = (inst->strum * sample_rate) / 1000;

            for (int i = 0; i < N; i++) {
                int idx = order[i]; // Play order index
                int out_note = chord->notes[idx] + inst->transpose;

                // Inversion
                if (inst->invert > 0 && idx < inst->invert) {
                    out_note += 12;
                } else if (inst->invert < 0 && idx >= N + inst->invert) {
                    out_note -= 12;
                }

                // Tilt implies velocity ramp
                int new_vel = vel;
                if (inst->tilt != 0 && N > 1) {
                    float pos = (2.0f * idx / (N - 1)) - 1.0f;
                    new_vel = vel + (int)(vel * (inst->tilt / 100.0f) * pos);
                    if (new_vel < 1) new_vel = 1;
                    if (new_vel > 127) new_vel = 127;
                }

                int delay = i * strum_samples; // Use play order for delay

                if (out_note >= 0 && out_note <= 127) {
                    if (delay == 0 || strum_samples == 0) {
                        if (out_count < max_out) {
                            out_msgs[out_count][0] = status;
                            out_msgs[out_count][1] = out_note;
                            out_msgs[out_count][2] = new_vel;
                            out_lens[out_count] = 3;
                            // Voice fires immediately — track as audible
                            active_append(inst, note, (uint8_t)out_note);
                            out_count++;
                        }
                    } else {
                        queue_note(inst, status, out_note, new_vel, note, delay);
                        // Don't append to active_notes yet — tick adds on fire
                    }
                    // No paired note-off queued here: pad release emits offs
                    // for all currently-audible voices; for strum voices that
                    // fire post-release, tick queues a note-off at length_samples
                    // when the note-on actually fires (so length is only applied
                    // to voices that would otherwise have no release signal).
                }
            }
            return out_count;
        }
    }
    else if (type == 0x80 || (type == 0x90 && vel == 0)) { // Note Off
        // Pad release: mark unheld. Emit the first voice's note-off now
        // for low-latency release; stagger the rest across ticks so a
        // thick chord doesn't burst the downstream inject buffer in one
        // frame (which can drop events and strand voices on Move's track).
        // Voices that fail to queue (queue full) fall back to direct emit.
        // Voices emitted directly are removed from active_notes so the
        // tick-path doesn't double-release them; voices queued stay in
        // active_notes until tick fires their note-off.
        inst->pad_held[note] = 0;
        int n_active = inst->active_counts[note];
        if (n_active == 0) return 0;

        uint8_t direct_emit[MAX_ACTIVE_PER_NOTE];
        int n_direct = 0;

        for (int i = 0; i < n_active; i++) {
            uint8_t voice = inst->active_notes[note][i];
            int ok = 0;
            if (i > 0) {
                ok = queue_note(inst, 0x80 | chan, voice, 0, note,
                                i * RELEASE_STAGGER_SAMPLES);
            }
            if (!ok) {
                if (n_direct < MAX_ACTIVE_PER_NOTE) {
                    direct_emit[n_direct++] = voice;
                }
            }
        }

        int out_count = 0;
        for (int i = 0; i < n_direct && out_count < max_out; i++) {
            out_msgs[out_count][0] = 0x80 | chan;
            out_msgs[out_count][1] = direct_emit[i];
            out_msgs[out_count][2] = 0;
            out_lens[out_count] = 3;
            out_count++;
            active_remove_one(inst, note, direct_emit[i]);
        }
        return out_count;
    }

    // Pass through for everything else
    if (max_out > 0) {
        memcpy(out_msgs[0], in_msg, in_len);
        out_lens[0] = in_len;
        return 1;
    }

    return 0;
}

static int ic_tick(void *instance, int frames, int sample_rate, uint8_t out_msgs[][3], int out_lens[], int max_out) {
    ic_instance_t *inst = (ic_instance_t *)instance;
    if (!inst || inst->pending_count == 0) return 0;

    int count = 0;
    int i = 0;
    while (i < inst->pending_count) {
        pending_note_t *p = &inst->pending[i];
        p->delay_samples -= frames;

        if (p->delay_samples <= 0) {
            uint8_t ptype = p->status & 0xF0;
            int is_off = (ptype == 0x80) || (ptype == 0x90 && p->velocity == 0);

            int emit = 0;
            if (is_off) {
                // Suppress length-timer note-off while pad is still held —
                // pad release is what ends the voice. If pad is released,
                // only emit if the voice is actually audible (i.e., its
                // note-on already fired and the pad-release handler didn't
                // already release it).
                if (!inst->pad_held[p->input_note]) {
                    emit = active_remove_one(inst, p->input_note, p->note);
                }
            } else {
                // Strum note-on: always fire (even if pad already released —
                // strum completes). Track as audible so release can emit off.
                emit = 1;
                active_append(inst, p->input_note, p->note);

                // If pad is already released at the moment this strum voice
                // fires, its only release signal is the length timer, so
                // queue a paired note-off at length_samples. For voices that
                // fire while pad is held, release-handler emits the note-off
                // on pad release — no pending entry needed.
                if (!inst->pad_held[p->input_note]) {
                    int length_samples = (inst->length * sample_rate) / 1000;
                    queue_note(inst, 0x80 | (p->status & 0x0F),
                               p->note, 0, p->input_note, length_samples);
                }
            }

            if (emit && count < max_out) {
                out_msgs[count][0] = p->status;
                out_msgs[count][1] = p->note;
                out_msgs[count][2] = p->velocity;
                out_lens[count] = 3;
                count++;
            } else if (emit) {
                // out buffer full — leave in queue for next tick
                i++;
                continue;
            }

            // Remove from queue
            for (int j = i; j < inst->pending_count - 1; j++) {
                inst->pending[j] = inst->pending[j + 1];
            }
            inst->pending_count--;
        } else {
            i++;
        }
    }

    return count;
}

static void ic_set_param(void *instance, const char *key, const char *val) {
    ic_instance_t *inst = (ic_instance_t *)instance;
    if (!inst || !key || !val) return;

    if (strcmp(key, "preset") == 0) {
        for (int i = 0; i < NUM_PRESETS; i++) {
            if (strcmp(g_presets[i].name, val) == 0) {
                inst->preset_idx = i;
                break;
            }
        }
    }
    else if (strcmp(key, "base_note") == 0) {
        inst->base_note = atoi(val);
    }
    else if (strcmp(key, "transpose") == 0) {
        inst->transpose = atoi(val);
    }
    else if (strcmp(key, "invert") == 0) {
        inst->invert = atoi(val);
    }
    else if (strcmp(key, "strum") == 0) {
        inst->strum = atoi(val);
    }
    else if (strcmp(key, "tilt") == 0) {
        inst->tilt = atoi(val);
    }
    else if (strcmp(key, "articulate") == 0) {
        inst->articulate = atoi(val);
    }
    else if (strcmp(key, "length") == 0) {
        inst->length = atoi(val);
    }
}

static int ic_get_param(void *instance, const char *key, char *buf, int buf_len) {
    ic_instance_t *inst = (ic_instance_t *)instance;
    if (!inst || !key || !buf || buf_len < 1) return -1;

    if (strcmp(key, "preset") == 0) {
        return snprintf(buf, buf_len, "%s", g_presets[inst->preset_idx].name);
    }
    else if (strcmp(key, "base_note") == 0) {
        return snprintf(buf, buf_len, "%d", inst->base_note);
    }
    else if (strcmp(key, "transpose") == 0) {
        return snprintf(buf, buf_len, "%d", inst->transpose);
    }
    else if (strcmp(key, "invert") == 0) {
        return snprintf(buf, buf_len, "%d", inst->invert);
    }
    else if (strcmp(key, "strum") == 0) {
        return snprintf(buf, buf_len, "%d", inst->strum);
    }
    else if (strcmp(key, "tilt") == 0) {
        return snprintf(buf, buf_len, "%d", inst->tilt);
    }
    else if (strcmp(key, "articulate") == 0) {
        return snprintf(buf, buf_len, "%d", inst->articulate);
    }
    else if (strcmp(key, "length") == 0) {
        return snprintf(buf, buf_len, "%d", inst->length);
    }
    else if (strcmp(key, "chain_params") == 0) {
        return snprintf(buf, buf_len, "%s", g_chain_params);
    }
    return -1;
}

static midi_fx_api_v1_t g_api = {
    .api_version = MIDI_FX_API_VERSION,
    .create_instance = ic_create_instance,
    .destroy_instance = ic_destroy_instance,
    .process_midi = ic_process_midi,
    .tick = ic_tick,
    .set_param = ic_set_param,
    .get_param = ic_get_param
};

midi_fx_api_v1_t* move_midi_fx_init(const host_api_v1_t *host) {
    g_host = host;
    return &g_api;
}
