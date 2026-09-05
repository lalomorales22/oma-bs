/* OMA-BS private FLV -> RTMP(S) transport. No secrets in argv or raw logs. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <ctype.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <libavformat/avio.h>

static volatile sig_atomic_t stopped;
static const char *failure_message;
static void private_log(void *context, int level, const char *format, va_list args) {
    (void)context;
    if (level > AV_LOG_ERROR) return;
    char text[4096];
    vsnprintf(text, sizeof(text), format, args);
    for (size_t i = 0; text[i]; i++) text[i] = (char)tolower((unsigned char)text[i]);
    if (strstr(text, "certificate")) failure_message = "Certificate verify failed";
    else if (strstr(text, "authentication") || strstr(text, "unauthorized") || strstr(text, "badname") || strstr(text, "badauth"))
        failure_message = "Authentication failed";
    else if (!failure_message && (strstr(text, "resolve hostname") || strstr(text, "name or service not known")))
        failure_message = "Failed to resolve hostname";
    /* Raw text, including any credentials, is never printed or persisted. */
}
static void stop(int signal_number) { (void)signal_number; stopped = 1; }
static int interrupted(void *opaque) { (void)opaque; return stopped; }
static int64_t micros(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}
static int read_value(FILE *file, char *value, size_t size) {
    if (!fgets(value, size, file)) return -1;
    size_t length = strlen(value);
    if (!length || value[length - 1] != '\n') return -1;
    value[length - 1] = 0;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    char *end = NULL;
    long descriptor = strtol(argv[1], &end, 10);
    if (!end || *end || descriptor < 3 || descriptor > 1048576) return 2;
    FILE *credentials = fdopen((int)descriptor, "r");
    if (!credentials) return 2;
    char endpoint[4096] = {0}, app[4096] = {0}, key[4096] = {0}, tcurl[4096] = {0};
    int invalid = read_value(credentials, endpoint, sizeof(endpoint)) ||
                  read_value(credentials, app, sizeof(app)) ||
                  read_value(credentials, key, sizeof(key)) ||
                  read_value(credentials, tcurl, sizeof(tcurl));
    fclose(credentials);
    int secure = !strncmp(endpoint, "rtmps://", 8);
    if (invalid || (!secure && strncmp(endpoint, "rtmp://", 7)) || !*key) return 2;
    struct sigaction action = {0};
    action.sa_handler = stop;
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    signal(SIGPIPE, SIG_IGN);
    av_log_set_level(AV_LOG_ERROR);
    av_log_set_callback(private_log);
    AVIOContext *output = NULL;
    AVDictionary *options = NULL;
    av_dict_set(&options, "rtmp_app", app, 0);
    av_dict_set(&options, "rtmp_playpath", key, 0);
    av_dict_set(&options, "rtmp_tcurl", tcurl, 0);
    av_dict_set(&options, "rw_timeout", "8000000", 0);
    if (secure) av_dict_set(&options, "tls_verify", "1", 0);
    AVIOInterruptCB callback = {interrupted, NULL};
    int result = avio_open2(&output, endpoint, AVIO_FLAG_WRITE, &callback, &options);
    /* Refuse to send if the selected protocol did not consume the key. */
    if (result >= 0 && (av_dict_get(options, "rtmp_playpath", NULL, 0) ||
                       av_dict_get(options, "rtmp_app", NULL, 0) ||
                       (secure && av_dict_get(options, "tls_verify", NULL, 0)))) {
        fputs("Unrecognized option in streaming transport\n", stderr);
        result = -EINVAL;
    }
    av_dict_free(&options);
    unsigned char buffer[65536];
    int64_t total = 0, start = micros(), last = 0;
    while (result >= 0 && !stopped) {
        ssize_t count = read(STDIN_FILENO, buffer, sizeof(buffer));
        if (!count) break;
        if (count < 0) { if (errno == EINTR) continue; result = -errno; break; }
        avio_write(output, buffer, (int)count);
        avio_flush(output);
        if (output->error < 0) { result = output->error; break; }
        total += count;
        int64_t now = micros();
        if (now - last >= 500000) {
            printf("total_size=%lld\nout_time_us=%lld\nprogress=continue\n",
                   (long long)total, (long long)(now - start + 1));
            fflush(stdout);
            last = now;
        }
    }
    if (output) {
        int closed = avio_closep(&output);
        if (result >= 0) result = closed;
    }
    if (result < 0 && !stopped) {
        const char *message = failure_message ? failure_message : result == -ECONNREFUSED ? "Connection refused" :
                              result == -ETIMEDOUT ? "Connection timed out" : "Input/output error";
        fprintf(stderr, "%s (transport error %d)\n", message, result);
        return 1;
    }
    return 0;
}
