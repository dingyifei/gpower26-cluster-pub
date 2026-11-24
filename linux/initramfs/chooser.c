// vegas boot chooser: /init of init_boot_a, runs before Android's (KernelSU's) init.
//
// Default: Android. Linux only when ALL of: normal boot (bootconfig force_normal_boot=1, mode=normal), the mtk-kpd
// keypad driver loads, and Vol-up (KEY_VOLUMEUP on "mtk-kpd") is pressed during a 4 s window (tap it after lk's
// orange screen; holding it during lk's screens makes lk enter fastboot). Every error -> Android.
// Vol-up kept DOWN for 2 s after it was detected (a hold, not taps) -> Linux with /force_rescue: init.linux then
// boots the rescue root (super partition "linux") and does not map the main root. Repeated taps (the normal way to
// hit the window) always release within that time, so they boot the main root; the wait ends at the first release.
// Only mtk-kpd is read: on #5 it carries Vol-up alone (Vol-down/Power are on mtk-pmic-keys, not loaded this early).
// Android path: /proc /sys /dev unmounted (mtk-kpd stays loaded, see cleanup()), rename /init.next (the base
// ramdisk's own init: ksuinit, or stock init for state E) over /init and exec it, as if there were no chooser. Logs "<3>chooser: ..." to kmsg -> pstore.
// Build: aarch64-linux-gnu-gcc -static -Os -o chooser chooser.c   (-DDRY: always Android, still logs the key state)
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>

#define KPD_KO "/lib/modules/mtk-kpd.ko"
#define KPD_NAME "mtk-kpd"
#define WINDOW_MS 4000   // the user TAPS Vol-up after lk's orange screen: kpd reports edges only, not a key held since before probe

static int kmsg = -1;
static void logf_(const char *fmt, ...) {
  char b[256]; va_list ap; va_start(ap, fmt);
  int n = snprintf(b, sizeof b, "<3>chooser: ");
  n += vsnprintf(b + n, sizeof b - n, fmt, ap); va_end(ap);
  if (n > (int)sizeof b - 2) n = sizeof b - 2;
  b[n++] = '\n';
  if (kmsg >= 0) (void)!write(kmsg, b, n);
}

static long now_ms(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1000 + t.tv_nsec / 1000000; }

static int bootconfig_is(const char *key, const char *val) {  // line: key = "val"
  char buf[8192]; int fd = open("/proc/bootconfig", O_RDONLY);
  if (fd < 0) return 0;
  ssize_t n = read(fd, buf, sizeof buf - 1); close(fd);
  if (n <= 0) return 0;
  buf[n] = 0;
  char want[160]; snprintf(want, sizeof want, "%s = \"%s\"\n", key, val);
  return strstr(buf, want) != NULL;
}

static int find_event(char *devname, size_t len) {  // /sys/class/input/eventN whose device name is mtk-kpd
  DIR *d = opendir("/sys/class/input"); struct dirent *e; int found = 0;
  if (!d) return 0;
  while (!found && (e = readdir(d))) {
    if (strncmp(e->d_name, "event", 5)) continue;
    char p[256], name[64] = {0}; snprintf(p, sizeof p, "/sys/class/input/%s/device/name", e->d_name);
    int fd = open(p, O_RDONLY); if (fd < 0) continue;
    ssize_t n = read(fd, name, sizeof name - 1); close(fd);
    if (n > 0 && name[n - 1] == '\n') name[n - 1] = 0;
    if (!strcmp(name, KPD_NAME)) { snprintf(devname, len, "%s", e->d_name); found = 1; }
  }
  closedir(d);
  return found;
}

#define HOLD_MS 2000
static int rescue_key;      // Vol-up stayed down for HOLD_MS after detection
static int key_held(void) {  // 1 = Vol-up seen during the window
  int fd = open(KPD_KO, O_RDONLY | O_CLOEXEC);
  if (fd < 0) { logf_("no %s", KPD_KO); return 0; }
  int r = syscall(SYS_finit_module, fd, "", 0); int err = errno; close(fd);
  if (r && err != EEXIST) { logf_("finit_module mtk-kpd: %s", strerror(err)); return 0; }
  char ev[32] = {0}; long t0 = now_ms();
  while (!find_event(ev, sizeof ev) && now_ms() - t0 < 500) usleep(20000);
  if (!ev[0]) { logf_("no %s event device", KPD_NAME); return 0; }
  char p[96], dev[32] = {0}; unsigned ma, mi;
  snprintf(p, sizeof p, "/sys/class/input/%s/dev", ev);
  int dfd = open(p, O_RDONLY); if (dfd < 0) return 0;
  (void)!read(dfd, dev, sizeof dev - 1); close(dfd);
  if (sscanf(dev, "%u:%u", &ma, &mi) != 2 || mknod("/dev/chooser-kpd", S_IFCHR | 0600, makedev(ma, mi))) { logf_("mknod failed"); return 0; }
  int efd = open("/dev/chooser-kpd", O_RDONLY | O_NONBLOCK | O_CLOEXEC);
  if (efd < 0) { logf_("open event: %s", strerror(errno)); return 0; }
  int held = 0; long start = now_ms();
  while (!held && now_ms() - start < WINDOW_MS) {
    unsigned char keys[KEY_MAX / 8 + 1] = {0};
    if (ioctl(efd, EVIOCGKEY(sizeof keys), keys) >= 0 && (keys[KEY_VOLUMEUP / 8] & (1 << (KEY_VOLUMEUP % 8)))) held = 1;
    struct pollfd pf = {efd, POLLIN, 0};
    if (!held && poll(&pf, 1, 50) > 0) {
      struct input_event ie;
      while (read(efd, &ie, sizeof ie) == sizeof ie)
        if (ie.type == EV_KEY) {
          logf_("key event code %u value %d at %ld ms", ie.code, ie.value, now_ms() - start);
          if (ie.code == KEY_VOLUMEUP && ie.value) held = 1;
        }
    }
  }
  long t_up = now_ms();
  if (held) {   // a hold? no release event for HOLD_MS, and the key state still says down at the end
    int released = 0;
    while (!released && now_ms() - t_up < HOLD_MS) {
      struct pollfd pf = {efd, POLLIN, 0};
      if (poll(&pf, 1, 50) <= 0) continue;
      struct input_event ie;
      while (read(efd, &ie, sizeof ie) == sizeof ie)
        if (ie.type == EV_KEY && ie.code == KEY_VOLUMEUP && ie.value == 0) released = 1;
    }
    unsigned char keys[KEY_MAX / 8 + 1] = {0};
    if (!released && ioctl(efd, EVIOCGKEY(sizeof keys), keys) >= 0 && (keys[KEY_VOLUMEUP / 8] & (1 << (KEY_VOLUMEUP % 8))))
      rescue_key = 1;
  }
  close(efd); unlink("/dev/chooser-kpd");
  logf_("%s %s, Vol-up %s after %ld ms%s", KPD_NAME, ev, held ? "HELD" : "not held", t_up - start,
        rescue_key ? ", held 2 s: rescue root" : "");
  return held;
}

static void cleanup(void) {
  // mtk-kpd stays loaded: unloading it while a key interrupt is pending panics the kernel (CFI failure in the IRQ
  // handler, seen 2026-11-22 on a Vol-up release). Android's first stage gets EEXIST for it, which libmodprobe accepts.
  if (kmsg >= 0) { close(kmsg); kmsg = -1; }
  umount2("/dev", MNT_DETACH); umount2("/sys", MNT_DETACH); umount2("/proc", MNT_DETACH);
}

static void exec_android(char **argv) {
  // /init.next = the base ramdisk's own /init: KernelSU's ksuinit (rooted build) or Android's stock init (state E).
  // It is renamed over /init first, so it runs exactly as it would without the chooser.
  if (access("/init.next", X_OK) == 0 && rename("/init.next", "/init") == 0) execv("/init", argv);
  execv("/init.next", argv);  // rename failed: run it from where it is
  // older chooser images named it /init.ksu
  if (access("/init.ksu", X_OK) == 0 && rename("/init.ksu", "/init") == 0) execv("/init", argv);
  execv("/init.ksu", argv);
  execv("/init.real", argv);
}

int main(int argc, char **argv) {
  (void)argc;
  int golinux = 0;
  if (getpid() == 1 && !mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL)) {
    mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL);
    mount("tmpfs", "/dev", "tmpfs", MS_NOSUID, "mode=0755,size=64k");
    mknod("/dev/kmsg", S_IFCHR | 0600, makedev(1, 11));
    kmsg = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    int normal = bootconfig_is("androidboot.force_normal_boot", "1") && bootconfig_is("androidboot.mode", "normal");
    logf_("start; normal boot: %s", normal ? "yes" : "no -> Android");
    if (normal) golinux = key_held();
#ifdef DRY
    if (golinux) logf_("DRY build: Linux would be chosen; booting Android");
    golinux = 0;
#endif
    if (golinux && access("/linux/init.linux", X_OK)) { logf_("no /linux/init.linux -> Android"); golinux = 0; }
    if (!golinux) { logf_("-> Android"); cleanup(); }
    else {
      logf_("-> Linux%s", rescue_key ? " (Vol-up held: rescue root)" : "");
      if (rescue_key) { int f = open("/force_rescue", O_WRONLY | O_CREAT | O_CLOEXEC, 0600); if (f >= 0) close(f); }
      // Linux keeps /proc /sys and the keypad module; init.linux mounts the rest itself.
      umount2("/dev", MNT_DETACH);
      if (kmsg >= 0) close(kmsg);
      char *la[] = {"/linux/busybox", "sh", "/linux/init.linux", NULL};
      execv("/linux/busybox", la);
      // exec failed: back to Android (proc/sys still mounted, clean them)
      umount2("/sys", MNT_DETACH); umount2("/proc", MNT_DETACH);
    }
  }
  exec_android(argv);
  return 127;  // nothing to exec: the kernel panics, lk/pstore show it
}
