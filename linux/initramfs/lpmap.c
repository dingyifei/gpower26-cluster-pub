// lpmap: map logical partitions of the Android `super` device with device-mapper (dm-linear), no Android tools.
//
//   lpmap [-n] <super blockdev> NAME[:ro] ...    creates /dev/mapper/NAME (read-only with :ro)
//   -n: dry run, print the dm tables only
//
// Reads LP metadata slot 0 (vegas boots slot a), verifies geometry + header + table SHA-256 like liblp, refuses any
// extent that is not linear on super, overlaps another extent of ANY partition, or leaves the device.
// Build: aarch64-linux-gnu-gcc -static -Os -o lpmap lpmap.c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/dm-ioctl.h>
#include <linux/fs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* ---- minimal SHA-256 ---- */
typedef struct { uint32_t h[8]; uint64_t len; uint8_t buf[64]; size_t n; } sha_t;
static const uint32_t K[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,
  0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
  0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
  0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,
  0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
  0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
static void sha_blk(sha_t *s, const uint8_t *p) {
  uint32_t w[64], a, b, c, d, e, f, g, h;
  for (int i = 0; i < 16; i++) w[i] = (uint32_t)p[4*i] << 24 | p[4*i+1] << 16 | p[4*i+2] << 8 | p[4*i+3];
  for (int i = 16; i < 64; i++) {
    uint32_t s0 = ROR(w[i-15], 7) ^ ROR(w[i-15], 18) ^ (w[i-15] >> 3), s1 = ROR(w[i-2], 17) ^ ROR(w[i-2], 19) ^ (w[i-2] >> 10);
    w[i] = w[i-16] + s0 + w[i-7] + s1;
  }
  a = s->h[0]; b = s->h[1]; c = s->h[2]; d = s->h[3]; e = s->h[4]; f = s->h[5]; g = s->h[6]; h = s->h[7];
  for (int i = 0; i < 64; i++) {
    uint32_t t1 = h + (ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
    uint32_t t2 = (ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
    h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
  }
  s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d; s->h[4] += e; s->h[5] += f; s->h[6] += g; s->h[7] += h;
}
static void sha256(const uint8_t *p, size_t n, uint8_t out[32]) {
  sha_t s = {{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}, 0, {0}, 0};
  s.len = (uint64_t)n * 8;
  for (; n >= 64; n -= 64, p += 64) sha_blk(&s, p);
  uint8_t t[128] = {0}; memcpy(t, p, n); t[n] = 0x80;
  size_t tl = n < 56 ? 64 : 128;
  for (int i = 0; i < 8; i++) t[tl - 1 - i] = (uint8_t)(s.len >> (8 * i));
  sha_blk(&s, t); if (tl == 128) sha_blk(&s, t + 64);
  for (int i = 0; i < 8; i++) { out[4*i] = s.h[i] >> 24; out[4*i+1] = s.h[i] >> 16; out[4*i+2] = s.h[i] >> 8; out[4*i+3] = s.h[i]; }
}

/* ---- LP metadata ---- */
#define GEOM_MAGIC 0x616C4467u
#define HDR_MAGIC 0x414C5030u
static uint8_t head[1 << 20];
static uint32_t u32(const uint8_t *p) { uint32_t v; memcpy(&v, p, 4); return v; }
static uint64_t u64(const uint8_t *p) { uint64_t v; memcpy(&v, p, 8); return v; }
static int die(const char *m) { fprintf(stderr, "lpmap: %s\n", m); exit(1); }

typedef struct { char name[37]; uint32_t first, n; } part_t;
typedef struct { uint64_t sectors, data; uint32_t type, src; } ext_t;
static part_t parts[64]; static ext_t exts[256]; static int nparts, nexts; static uint64_t lp_dev_bytes;

static void parse(void) {
  uint8_t c[32], z[32] = {0}, tmp[4096];
  uint32_t goff = 4096;
  if (u32(head + goff) != GEOM_MAGIC) goff = 8192;
  if (u32(head + goff) != GEOM_MAGIC) die("no geometry");
  uint32_t gsz = u32(head + goff + 4);
  if (gsz > sizeof tmp) die("geometry size");
  memcpy(tmp, head + goff, gsz); memcpy(tmp + 8, z, 32); sha256(tmp, gsz, c);
  if (memcmp(c, head + goff + 8, 32)) die("geometry checksum");
  uint32_t maxsz = u32(head + goff + 40);
  uint32_t off = 12288;  // slot 0 primary
  if (u32(head + off) != HDR_MAGIC) die("header magic");
  uint32_t hsz = u32(head + off + 8);
  if (hsz > sizeof tmp || off + maxsz > sizeof head) die("header size");
  memcpy(tmp, head + off, hsz); memcpy(tmp + 12, z, 32); sha256(tmp, hsz, c);
  if (memcmp(c, head + off + 12, 32)) die("header checksum");
  uint32_t tsz = u32(head + off + 44);
  const uint8_t *tab = head + off + hsz;
  if (hsz + tsz > maxsz) die("tables size");
  sha256(tab, tsz, c);
  if (memcmp(c, head + off + 48, 32)) die("tables checksum");
  uint32_t po = u32(head + off + 80), pn = u32(head + off + 84), ps = u32(head + off + 88);
  uint32_t eo = u32(head + off + 92), en = u32(head + off + 96), es = u32(head + off + 100);
  if (pn > 64 || en > 256) die("too many entries");
  uint32_t bo = u32(head + off + 116), bn = u32(head + off + 120);
  if (bn != 1) die("expected exactly one block device (super)");
  lp_dev_bytes = u64(tab + bo + 16);
  for (uint32_t i = 0; i < pn; i++) {
    const uint8_t *e = tab + po + i * ps;
    memcpy(parts[i].name, e, 36); parts[i].name[36] = 0;
    parts[i].first = u32(e + 40); parts[i].n = u32(e + 44);
    if (parts[i].first + parts[i].n > en) die("extent index out of range");
  }
  for (uint32_t i = 0; i < en; i++) {
    const uint8_t *e = tab + eo + i * es;
    exts[i].sectors = u64(e); exts[i].type = u32(e + 8); exts[i].data = u64(e + 12); exts[i].src = u32(e + 20);
  }
  nparts = pn; nexts = en;
}

static void check_overlaps(uint64_t dev_sectors) {
  for (int i = 0; i < nexts; i++) {
    if (exts[i].type != 0) continue;
    if (exts[i].data < 2048 || exts[i].data + exts[i].sectors > dev_sectors) die("extent outside super");
    for (int j = i + 1; j < nexts; j++) {
      if (exts[j].type != 0) continue;
      if (exts[i].data < exts[j].data + exts[j].sectors && exts[j].data < exts[i].data + exts[i].sectors) die("overlapping extents");
    }
  }
}

static int dm_map(const char *name, int ro, dev_t super, const part_t *p, int dry) {
  char buf[16384]; memset(buf, 0, sizeof buf);
  struct dm_ioctl *io = (struct dm_ioctl *)buf;
  size_t pos = sizeof *io; uint64_t start = 0;
  for (uint32_t k = 0; k < p->n; k++) {
    const ext_t *e = &exts[p->first + k];
    if (e->type != 0 || e->src != 0) die("non-linear extent");
    struct dm_target_spec *t = (struct dm_target_spec *)(buf + pos);
    t->sector_start = start; t->length = e->sectors; strcpy(t->target_type, "linear");
    char *params = (char *)(t + 1);
    int n = snprintf(params, 64, "%u:%u %llu", major(super), minor(super), (unsigned long long)e->data);
    size_t sz = sizeof *t + n + 1; sz = (sz + 7) & ~7UL;
    t->next = sz; pos += sz; start += e->sectors;
    printf("%s: %llu %llu linear %s\n", name, (unsigned long long)t->sector_start, (unsigned long long)t->length, params);
  }
  printf("%s: %llu sectors%s\n", name, (unsigned long long)start, ro ? " ro" : "");
  if (dry) return 0;
  int fd = open("/dev/mapper/control", O_RDWR);
  if (fd < 0) die("open /dev/mapper/control");
  struct dm_ioctl c; memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", name);
  if (ioctl(fd, DM_DEV_CREATE, &c)) die("DM_DEV_CREATE");
  io->version[0] = DM_VERSION_MAJOR; io->data_size = pos; io->data_start = sizeof *io;
  io->target_count = p->n; io->flags = ro ? DM_READONLY_FLAG : 0;
  snprintf(io->name, sizeof io->name, "%s", name);
  if (ioctl(fd, DM_TABLE_LOAD, io)) die("DM_TABLE_LOAD");
  memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", name);
  if (ioctl(fd, DM_DEV_SUSPEND, &c)) die("DM_DEV_SUSPEND (resume)");
  char node[96]; snprintf(node, sizeof node, "/dev/mapper/%s", name);
  mkdir("/dev/mapper", 0755); unlink(node);
  if (mknod(node, S_IFBLK | 0600, c.dev)) die("mknod mapper node");
  printf("%s -> %s (%u:%u)\n", name, node, major(c.dev), minor(c.dev));
  close(fd);
  return 0;
}

int main(int argc, char **argv) {
  int a = 1, dry = 0;
  if (a < argc && !strcmp(argv[a], "-n")) { dry = 1; a++; }
  if (argc - a < 2) die("usage: lpmap [-n] <super dev> NAME[:ro] ...");
  int fd = open(argv[a], O_RDONLY);
  if (fd < 0) die("open super");
  struct stat st; if (fstat(fd, &st)) die("stat super");
  uint64_t bytes = 0;
  if (S_ISBLK(st.st_mode)) { if (ioctl(fd, BLKGETSIZE64, &bytes)) die("BLKGETSIZE64"); } else bytes = st.st_size;
  if (pread(fd, head, sizeof head, 0) != (ssize_t)sizeof head) die("read head");
  close(fd);
  parse();
  if (S_ISBLK(st.st_mode) && lp_dev_bytes > bytes) die("metadata says super is larger than the device");
  check_overlaps(lp_dev_bytes / 512);
  for (int i = a + 1; i < argc; i++) {
    char name[40]; snprintf(name, sizeof name, "%s", argv[i]);
    int ro = 0; char *colon = strchr(name, ':');
    if (colon) { ro = !strcmp(colon, ":ro"); *colon = 0; }
    int found = 0;
    for (int k = 0; k < nparts; k++)
      if (!strcmp(parts[k].name, name)) { found = 1; if (!parts[k].n) die("empty partition"); dm_map(name, ro, st.st_rdev, &parts[k], dry); }
    if (!found) { fprintf(stderr, "lpmap: %s not found\n", name); return 1; }
  }
  return 0;
}
