// vegasdisk: a Linux disk made of pinned files inside Android's encrypted /data, used from Linux through the raw
// userdata partition (the same mechanism as Android's DSU / libfiemap; see docs/linux-on-vegas.md section 12).
//
// Android (root, /data mounted):
//   vegasdisk create <dir> <MiB> [--piece-mib N]   pieces <dir>/disk.NNNN: pin (F2FS_IOC_SET_PIN_FILE), fallocate,
//                                                 FIEMAP; writes the extent table + canaries to the RAW partition
//   vegasdisk grow   <dir> <MiB>                    add pieces up to <MiB> total; rewrites the table
//   vegasdisk verify <dir>                          FIEMAP + pin state + raw table + canaries all agree
//   vegasdisk info   <dir>                          print anchor/uuid/raw device (for /etc/vegas/vegasdisk.conf)
//   vegasdisk delete <dir> <uuid>                   zero the table + every canary on the raw partition, then unlink
//                                                 the pieces (only if the table's uuid matches)
// Linux (Android not running):
//   vegasdisk map [-n] [--ro] <rawdev> <anchor-bytes> <uuid> <dm-name>
//       reads the table at <anchor>, checks magic/version/CRCs/uuid/fsid/bounds/overlaps/every canary, then creates
//       dm-linear <dm-name> over the data ranges. -n: check only (print the table). Refuses on any mismatch.
//   vegasdisk unmap <dm-name>
// --test (first argument): allow a non-f2fs filesystem (zero-filled instead of pinned) and a raw device that is not
//   the "userdata" partition. For the offline tests only.
//
// Layout. Piece 0: [0, 1 MiB) table area (header + extent table), data, last 4 KiB tail canary.
//         Piece i>0: first 4 KiB head canary, data, last 4 KiB tail canary.
// The data ranges of all pieces, in order, form the disk. All offsets are bytes on the raw partition.
// Piece sizes are whole 2 MiB f2fs sections, so every pinned section stays fully valid and f2fs GC never picks it as a
// victim (only partly valid sections are victims); a pinned file is unpinned and moved only after
// gc_pin_file_thresh failed GC attempts on it, and verify refuses as soon as that count is above 0.
//
// fsid: the table stores raw bytes [1024, 1152) of the partition = the start of f2fs's superblock (magic, layout,
// block count, f2fs uuid). Under metadata encryption these are AES-XTS ciphertext; XTS encrypts each 16-byte chunk
// on its own, and f2fs never rewrites these fields (measured on #5: across reboots only the chunk at 3776 changes).
// A format / factory reset of /data (new f2fs uuid, new metadata key) changes them, so map and verify refuse a
// table left over from an earlier /data: its pieces no longer exist and f2fs may have reused their blocks.
// Build: aarch64-linux-gnu-gcc -static -Os -Wall -o vegasdisk vegasdisk.c
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/dm-ioctl.h>
#include <linux/fiemap.h>
#include <linux/fs.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>

#define BLK 4096u
#define TABLE_BYTES (1u << 20)
#define MAX_EXT ((TABLE_BYTES - BLK) / sizeof(ext_t))
#define MAX_PIECES 4096
#define SECTION (2u << 20)  // f2fs section (2 MiB on #5); piece sizes are multiples of it
#define FSID_OFF 1024
#define FSID_LEN 128
#define F2FS_MAGIC_ 0xF2F52010
#define F2FS_IOC_SET_PIN_FILE_ _IOW(0xf5, 13, uint32_t)
#define F2FS_IOC_GET_PIN_FILE_ _IOR(0xf5, 14, uint32_t)
#define FS_NOCOW_FL_ 0x00800000
#define BAD_FLAGS (FIEMAP_EXTENT_UNKNOWN | FIEMAP_EXTENT_DELALLOC | FIEMAP_EXTENT_ENCODED | FIEMAP_EXTENT_NOT_ALIGNED | \
                   FIEMAP_EXTENT_DATA_INLINE | FIEMAP_EXTENT_DATA_TAIL | FIEMAP_EXTENT_UNWRITTEN | FIEMAP_EXTENT_SHARED)

typedef struct { uint32_t piece, rsvd; uint64_t logical, phys, len; } ext_t;  // 32 bytes, little endian on disk
typedef struct {
  char magic[8];            // "VEGASDK1"
  uint32_t version, table_bytes;
  uint8_t uuid[16];
  uint64_t created, data_bytes;
  uint32_t npieces, nextents;
  uint8_t fsid[FSID_LEN];   // raw bytes [FSID_OFF, FSID_OFF + FSID_LEN) of the partition when the table was written
  uint32_t ext_crc, hdr_crc;  // crc32 of the extent array; of this struct with hdr_crc = 0
} hdr_t;
typedef struct {
  char magic[8];            // "VEGASCN1"
  uint8_t uuid[16];
  uint32_t piece, which;    // which: 0 head, 1 tail
  uint64_t self;            // raw byte offset of this block
  uint32_t crc, pad;
} canary_t;

static int test_mode;
static uint8_t *table;      // TABLE_BYTES, aligned
static hdr_t *H;
static ext_t *E;

static void (*on_die)(void);   // undo hook: removes what this run created before it became visible
static void die(const char *fmt, ...) {
  va_list ap; va_start(ap, fmt); fprintf(stderr, "vegasdisk: "); vfprintf(stderr, fmt, ap); va_end(ap);
  fprintf(stderr, "\n");
  void (*h)(void) = on_die; on_die = NULL; if (h) h();
  exit(1);
}
static uint32_t crc32(const void *p, size_t n) {
  const uint8_t *b = p; uint32_t c = 0xFFFFFFFFu;
  while (n--) { c ^= *b++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & -(c & 1)); }
  return ~c;
}
static void *ablk(size_t n) { void *p; if (posix_memalign(&p, BLK, n)) die("out of memory"); memset(p, 0, n); return p; }
static void hexuuid(const uint8_t *u, char *s) { for (int i = 0; i < 16; i++) sprintf(s + 2 * i, "%02x", u[i]); }
static int parseuuid(const char *s, uint8_t *u) {
  if (strlen(s) != 32) return -1;
  for (int i = 0; i < 16; i++) { unsigned v; if (sscanf(s + 2 * i, "%2x", &v) != 1) return -1; u[i] = v; }
  return 0;
}
static void rd(int fd, void *b, size_t n, uint64_t off) {
  if (pread(fd, b, n, off) != (ssize_t)n) die("raw read at %llu: %s", (unsigned long long)off, strerror(errno));
}
static void wr(int fd, const void *b, size_t n, uint64_t off) {
  if (pwrite(fd, b, n, off) != (ssize_t)n) die("raw write at %llu: %s", (unsigned long long)off, strerror(errno));
}

/* ---- raw device of a directory on Android: walk dm down through 1:1 targets to the partition ---- */
static char rawname[64], rawpath[96];
static uint64_t rawbytes;
static int sysread(const char *path, char *buf, size_t n) {
  int fd = open(path, O_RDONLY); if (fd < 0) return -1;
  ssize_t r = read(fd, buf, n - 1); close(fd); if (r < 0) return -1;
  buf[r] = 0; while (r && (buf[r - 1] == '\n')) buf[--r] = 0; return 0;
}
static void dm_check_identity(const char *name) {  // exactly one target, default-key/linear/bow/crypt at offset 0
  char buf[16384]; memset(buf, 0, sizeof buf);
  struct dm_ioctl *io = (struct dm_ioctl *)buf;
  io->version[0] = DM_VERSION_MAJOR; io->data_size = sizeof buf; io->data_start = sizeof *io;
  io->flags = DM_STATUS_TABLE_FLAG;
  char dmname[128]; snprintf(dmname, sizeof dmname, "/sys/block/%s/dm/name", name);
  if (sysread(dmname, io->name, sizeof io->name)) die("cannot read %s", dmname);
  int fd = open("/dev/device-mapper", O_RDWR); if (fd < 0) fd = open("/dev/mapper/control", O_RDWR);
  if (fd < 0) die("open device-mapper control");
  if (ioctl(fd, DM_TABLE_STATUS, io)) die("DM_TABLE_STATUS %s: %s", io->name, strerror(errno));
  close(fd);
  if (io->target_count != 1) die("%s (%s) has %u targets; need exactly 1", name, io->name, io->target_count);
  struct dm_target_spec *t = (struct dm_target_spec *)(buf + io->data_start);
  const char *ty = t->target_type, *par = (const char *)(t + 1);
  if (t->sector_start != 0) die("%s target does not start at 0", name);
  // the last parameter of linear/default-key/crypt before options is the start sector on the lower device
  if (!strcmp(ty, "linear")) {
    unsigned long long off; if (sscanf(par, "%*s %llu", &off) != 1 || off) die("%s: linear target with offset", name);
  } else if (!strcmp(ty, "default-key") || !strcmp(ty, "crypt")) {
    unsigned long long iv, off; char dev[64];
    if (sscanf(par, "%*s %*s %llu %63s %llu", &iv, dev, &off) != 3 || off) die("%s: %s target with offset (%s)", name, ty, par);
  } else if (strcmp(ty, "bow")) die("%s: unsupported dm target %s", name, ty);
  printf("raw: %s (%s) = %s, offset 0\n", name, io->name, ty);
}
static void resolve_raw(dev_t dev) {
  char link[256], path[128], cur[64];
  snprintf(path, sizeof path, "/sys/dev/block/%u:%u", major(dev), minor(dev));
  ssize_t n = readlink(path, link, sizeof link - 1); if (n < 0) die("readlink %s", path);
  link[n] = 0; snprintf(cur, sizeof cur, "%s", strrchr(link, '/') + 1);
  for (int depth = 0; !strncmp(cur, "dm-", 3); depth++) {
    if (depth > 4) die("dm stack too deep");
    dm_check_identity(cur);
    char sl[128]; snprintf(sl, sizeof sl, "/sys/block/%s/slaves", cur);
    DIR *d = opendir(sl); if (!d) die("opendir %s", sl);
    struct dirent *de; int cnt = 0; char next[64] = "";
    while ((de = readdir(d))) if (de->d_name[0] != '.') { cnt++; snprintf(next, sizeof next, "%s", de->d_name); }
    closedir(d);
    if (cnt != 1) die("%s has %d lower devices", cur, cnt);
    snprintf(cur, sizeof cur, "%s", next);
  }
  snprintf(rawname, sizeof rawname, "%s", cur);
  char ue[128], buf[1024]; snprintf(ue, sizeof ue, "/sys/class/block/%s/uevent", cur);
  if (sysread(ue, buf, sizeof buf)) die("read %s", ue);
  char *pn = strstr(buf, "PARTNAME=");
  int is_userdata = pn && !strncmp(pn + 9, "userdata", 8) && (pn[17] == '\n' || pn[17] == 0);
  if (!is_userdata && !test_mode) die("raw device %s is not the userdata partition", cur);
  snprintf(rawpath, sizeof rawpath, "/dev/block/%s", cur);
  if (access(rawpath, F_OK)) snprintf(rawpath, sizeof rawpath, "/dev/%s", cur);
  int fd = open(rawpath, O_RDONLY); if (fd < 0) die("open %s", rawpath);
  if (ioctl(fd, BLKGETSIZE64, &rawbytes)) die("BLKGETSIZE64 %s", rawpath);
  close(fd);
}

/* ---- pieces ---- */
static char dirp[256];
static void piecepath(char *out, size_t n, uint32_t i) { snprintf(out, n, "%s/disk.%04u", dirp, i); }
static uint32_t count_pieces(void) {
  uint32_t i = 0; char p[300];
  for (;; i++) { piecepath(p, sizeof p, i); if (access(p, F_OK)) return i; }
}
static int is_f2fs(int fd) { struct statfs s; if (fstatfs(fd, &s)) die("statfs"); return (uint32_t)s.f_type == F2FS_MAGIC_; }
static void pin_state(int fd, const char *p, uint32_t *gcfail) {
  if (!is_f2fs(fd)) { if (!test_mode) die("%s: not on f2fs", p); *gcfail = 0; return; }
  int fl = 0; if (ioctl(fd, FS_IOC_GETFLAGS, &fl)) die("%s: FS_IOC_GETFLAGS", p);
  if (!(fl & FS_NOCOW_FL_)) die("%s: NOT pinned", p);
  uint32_t v = 0; if (ioctl(fd, F2FS_IOC_GET_PIN_FILE_, &v)) die("%s: F2FS_IOC_GET_PIN_FILE", p);
  *gcfail = v;
}
static void make_piece(uint32_t i, uint64_t bytes) {
  char p[300]; piecepath(p, sizeof p, i);
  int fd = open(p, O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC, 0600); if (fd < 0) die("create %s: %s", p, strerror(errno));
  if (is_f2fs(fd)) {
    uint32_t one = 1; if (ioctl(fd, F2FS_IOC_SET_PIN_FILE_, &one)) die("%s: pin: %s", p, strerror(errno));
    while (fallocate(fd, 0, 0, bytes)) if (errno != EAGAIN) die("%s: fallocate: %s", p, strerror(errno));
  } else {
    if (!test_mode) die("%s: not on f2fs", p);
    uint8_t *z = ablk(1 << 20);   // ext4 test: write zeros so the extents are not "unwritten"
    for (uint64_t o = 0; o < bytes; o += 1 << 20) if (pwrite(fd, z, 1 << 20, o) != 1 << 20) die("%s: write", p);
    free(z);
  }
  if (fsync(fd)) die("%s: fsync", p);
  close(fd);
}
// FIEMAP one piece; append its extents (logical order) to out[]. Returns the piece size.
static uint64_t fiemap_piece(uint32_t i, ext_t *out, uint32_t *n, uint32_t max, uint32_t *gcfail) {
  char p[300]; piecepath(p, sizeof p, i);
  int fd = open(p, O_RDONLY | O_CLOEXEC); if (fd < 0) die("open %s", p);
  struct stat st; if (fstat(fd, &st)) die("stat %s", p);
  uint64_t size = st.st_size;
  if (!size || size % BLK) die("%s: size %llu not a multiple of 4096", p, (unsigned long long)size);
  pin_state(fd, p, gcfail);
  const uint32_t B = 512;
  struct fiemap *fm = calloc(1, sizeof *fm + B * sizeof(struct fiemap_extent)); if (!fm) die("oom");
  uint64_t pos = 0; int last = 0;
  while (!last && pos < size) {
    memset(fm, 0, sizeof *fm); fm->fm_start = pos; fm->fm_length = size - pos;
    fm->fm_flags = FIEMAP_FLAG_SYNC; fm->fm_extent_count = B;
    if (ioctl(fd, FS_IOC_FIEMAP, fm)) die("%s: FIEMAP: %s", p, strerror(errno));
    if (!fm->fm_mapped_extents) break;
    for (uint32_t k = 0; k < fm->fm_mapped_extents; k++) {
      struct fiemap_extent *x = &fm->fm_extents[k];
      if (x->fe_flags & BAD_FLAGS) die("%s: extent flags 0x%x not allowed", p, x->fe_flags);
      if (x->fe_logical != pos) die("%s: hole or overlap at %llu", p, (unsigned long long)pos);
      if (x->fe_physical % BLK || x->fe_length % BLK) die("%s: unaligned extent", p);
      uint64_t len = x->fe_length; if (pos + len > size) len = size - pos;
      if (*n && out[*n - 1].piece == i && out[*n - 1].phys + out[*n - 1].len == x->fe_physical &&
          out[*n - 1].logical + out[*n - 1].len == pos) out[*n - 1].len += len;  // merge contiguous
      else {
        if (*n >= max) die("too many extents (max %u)", max);
        out[(*n)++] = (ext_t){ i, 0, pos, x->fe_physical, len };
      }
      pos += len;
      if (x->fe_flags & FIEMAP_EXTENT_LAST) last = 1;
    }
  }
  free(fm); close(fd);
  if (pos != size) die("%s: extents cover %llu of %llu bytes", p, (unsigned long long)pos, (unsigned long long)size);
  return size;
}
// raw offset of logical byte <l> of piece <i>; the 4 KiB block at <l> must not cross an extent
static uint64_t phys_of(const ext_t *e, uint32_t n, uint32_t i, uint64_t l) {
  for (uint32_t k = 0; k < n; k++)
    if (e[k].piece == i && l >= e[k].logical && l + BLK <= e[k].logical + e[k].len) return e[k].phys + (l - e[k].logical);
  die("piece %u offset %llu not mapped", i, (unsigned long long)l); return 0;
}
static void check_bounds(const ext_t *e, uint32_t n) {
  for (uint32_t a = 0; a < n; a++) {
    if (!e[a].len || e[a].phys % BLK || e[a].len % BLK) die("extent %u malformed", a);
    if (e[a].phys + e[a].len > rawbytes || e[a].phys + e[a].len < e[a].phys) die("extent %u outside %s", a, rawname);
    for (uint32_t b = a + 1; b < n; b++)
      if (e[a].phys < e[b].phys + e[b].len && e[b].phys < e[a].phys + e[a].len) die("extents %u and %u overlap", a, b);
  }
}

/* ---- table + canaries ---- */
static void canary_fill(canary_t *c, uint32_t piece, uint32_t which, uint64_t self) {
  memset(c, 0, BLK); memcpy(c->magic, "VEGASCN1", 8); memcpy(c->uuid, H->uuid, 16);
  c->piece = piece; c->which = which; c->self = self; c->crc = crc32(c, offsetof(canary_t, crc));
}
static void canary_check(int fd, uint32_t piece, uint32_t which, uint64_t self) {
  canary_t *c = ablk(BLK); rd(fd, c, BLK, self);
  if (memcmp(c->magic, "VEGASCN1", 8) || memcmp(c->uuid, H->uuid, 16) || c->piece != piece || c->which != which ||
      c->self != self || c->crc != crc32(c, offsetof(canary_t, crc)))
    die("canary %s of piece %u at %llu is wrong: the file moved or the blocks were overwritten", which ? "tail" : "head",
        piece, (unsigned long long)self);
  free(c);
}
static uint64_t piece_size(uint32_t i) {
  uint64_t s = 0; for (uint32_t k = 0; k < H->nextents; k++) if (E[k].piece == i) s += E[k].len; return s;
}
static void finish_header(void) {
  H->ext_crc = crc32(E, H->nextents * sizeof(ext_t));
  H->hdr_crc = 0; H->hdr_crc = crc32(H, sizeof *H);
}
static void validate_table(void) {
  if (memcmp(H->magic, "VEGASDK1", 8)) die("no vegasdisk table (magic)");
  if (H->version != 2 || H->table_bytes != TABLE_BYTES) die("unsupported table version/size");
  uint32_t c = H->hdr_crc; H->hdr_crc = 0; uint32_t c2 = crc32(H, sizeof *H); H->hdr_crc = c;
  if (c != c2) die("header CRC mismatch");
  if (!H->npieces || H->npieces > MAX_PIECES || !H->nextents || H->nextents > MAX_EXT) die("bad counts");
  if (crc32(E, H->nextents * sizeof(ext_t)) != H->ext_crc) die("extent table CRC mismatch");
  uint64_t data = 0;
  for (uint32_t i = 0; i < H->npieces; i++) {  // extents of each piece are contiguous in logical order from 0
    uint64_t pos = 0;
    for (uint32_t k = 0; k < H->nextents; k++) if (E[k].piece == i) {
      if (E[k].logical != pos) die("piece %u: extent table not contiguous", i);
      pos += E[k].len;
    }
    uint64_t head = i ? BLK : TABLE_BYTES;
    if (pos < head + 2 * BLK) die("piece %u too small", i);
    data += pos - head - BLK;
  }
  for (uint32_t k = 0; k < H->nextents; k++) if (E[k].piece >= H->npieces) die("extent piece out of range");
  if (E[0].piece != 0 || E[0].logical != 0 || E[0].len < TABLE_BYTES)
    die("the table area (first 1 MiB of piece 0) is not one contiguous extent");
  if (data != H->data_bytes) die("data size mismatch");
}
static void write_canaries(int fd, uint32_t from) {
  canary_t *c = ablk(BLK);
  for (uint32_t i = from; i < H->npieces; i++) {
    uint64_t sz = piece_size(i);
    if (i) { uint64_t o = phys_of(E, H->nextents, i, 0); canary_fill(c, i, 0, o); wr(fd, c, BLK, o); }
    uint64_t o = phys_of(E, H->nextents, i, sz - BLK); canary_fill(c, i, 1, o); wr(fd, c, BLK, o);
  }
  free(c);
}
static void check_canaries(int fd) {
  for (uint32_t i = 0; i < H->npieces; i++) {
    uint64_t sz = piece_size(i);
    if (i) canary_check(fd, i, 0, phys_of(E, H->nextents, i, 0));
    canary_check(fd, i, 1, phys_of(E, H->nextents, i, sz - BLK));
  }
}

static void read_fsid(int fd, uint8_t *out) {
  uint8_t *b = ablk(BLK); rd(fd, b, BLK, 0); memcpy(out, b + FSID_OFF, FSID_LEN); free(b);
}
static void check_fsid(int fd) {
  uint8_t now[FSID_LEN]; read_fsid(fd, now);
  if (memcmp(now, H->fsid, FSID_LEN))
    die("the partition's f2fs superblock differs from the one the table was made on: /data was formatted or reset "
        "since, the pieces are gone and their blocks may be in use");
}

/* ---- Android side ---- */
static int open_raw(int rw) {
  int fd = open(rawpath, (rw ? O_RDWR : O_RDONLY) | O_DIRECT | O_CLOEXEC);
  if (fd < 0) die("open %s: %s", rawpath, strerror(errno));
  return fd;
}
static void setdir(const char *d, int create) {
  snprintf(dirp, sizeof dirp, "%s", d);
  if (create) { if (mkdir(dirp, 0700) && errno != EEXIST) die("mkdir %s", dirp); }
  struct stat st; if (stat(dirp, &st) || !S_ISDIR(st.st_mode)) die("%s is not a directory", dirp);
  resolve_raw(st.st_dev);
}
// FIEMAP all pieces into a fresh extent list; returns the count
static uint32_t scan(ext_t *out, uint32_t np, uint32_t *maxgc) {
  uint32_t n = 0; *maxgc = 0;
  for (uint32_t i = 0; i < np; i++) { uint32_t g; fiemap_piece(i, out, &n, MAX_EXT, &g); if (g > *maxgc) *maxgc = g; }
  return n;
}
static void load_table_from_raw(int fd, uint64_t anchor) { rd(fd, table, TABLE_BYTES, anchor); validate_table(); }
static void print_info(void) {
  char u[33]; hexuuid(H->uuid, u);
  uint64_t anchor = phys_of(E, H->nextents, 0, 0);
  printf("raw=%s anchor=%llu uuid=%s pieces=%u extents=%u data_mib=%llu\n", rawname, (unsigned long long)anchor, u,
         H->npieces, H->nextents, (unsigned long long)(H->data_bytes >> 20));
}
static uint32_t first_new, np_made;
static void undo_new_pieces(void) {   // no table lists these yet: unlinking them is safe
  char p[300];
  for (uint32_t i = np_made + 1; i-- > first_new;) { piecepath(p, sizeof p, i); if (!unlink(p)) fprintf(stderr, "vegasdisk: removed %s\n", p); }
  if (!first_new) rmdir(dirp);
}
static int cmd_create_grow(int grow, uint64_t mib, uint64_t piece_mib) {
  uint64_t want = mib << 20, pbytes = piece_mib << 20;
  if (pbytes < SECTION || pbytes % SECTION) die("piece size must be a multiple of %u MiB", SECTION >> 20);
  uint32_t have = count_pieces();
  ext_t *scanbuf = calloc(MAX_EXT, sizeof(ext_t)); if (!scanbuf) die("oom");
  uint32_t gc;
  int fd = open_raw(1);
  if (grow) {
    if (!have) die("%s has no pieces; use create", dirp);
    uint32_t n = scan(scanbuf, have, &gc);
    load_table_from_raw(fd, phys_of(scanbuf, n, 0, 0));
    if (H->npieces != have) die("table lists %u pieces, %u exist", H->npieces, have);
    if (n != H->nextents || memcmp(scanbuf, E, n * sizeof(ext_t))) die("pieces moved since the table was written");
    if (gc) die("f2fs GC failed %u times on a pinned piece: refusing to grow", gc);
    check_fsid(fd);
    check_canaries(fd);
  } else {
    if (have) die("%s already has pieces", dirp);
    memset(table, 0, TABLE_BYTES); memcpy(H->magic, "VEGASDK1", 8); H->version = 2; H->table_bytes = TABLE_BYTES;
    read_fsid(fd, H->fsid);
    if (getrandom(H->uuid, 16, 0) != 16) die("getrandom");
    H->created = (uint64_t)time(NULL);
  }
  uint64_t total = 0;  // current raw size of all pieces
  for (uint32_t i = 0; i < have; i++) total += piece_size(i);
  first_new = have; np_made = have;
  on_die = undo_new_pieces;   // until the table is written, a failure removes the pieces this run made
  while (total < want) {
    if (np_made >= MAX_PIECES) die("too many pieces");
    uint64_t b = want - total < pbytes ? want - total : pbytes;
    b = (b + SECTION - 1) / SECTION * SECTION;   // whole sections (also covers the table + canaries of a tiny piece)
    make_piece(np_made, b); np_made++; total += b;
  }
  uint32_t np = np_made;
  if (np == have) { on_die = NULL; printf("already %llu MiB\n", (unsigned long long)(total >> 20)); print_info(); return 0; }
  int dfd = open(dirp, O_RDONLY | O_DIRECTORY | O_CLOEXEC);   // checkpoint the new files' allocation before FIEMAP
  if (dfd < 0 || syncfs(dfd)) die("syncfs %s", dirp);
  close(dfd);
  uint32_t n = scan(scanbuf, np, &gc);
  if (gc) die("f2fs reports %u GC failures on a pinned piece", gc);
  if (n > MAX_EXT) die("too many extents");
  memcpy(E, scanbuf, n * sizeof(ext_t)); H->nextents = n; H->npieces = np;
  check_bounds(E, n);
  uint64_t data = 0;
  for (uint32_t i = 0; i < np; i++) data += piece_size(i) - (i ? BLK : TABLE_BYTES) - BLK;
  H->data_bytes = data;
  finish_header();
  validate_table();
  write_canaries(fd, first_new);
  if (!grow) {   // a new disk: zero the first MiB of data, so no stale filesystem signature from earlier blocks shows
    uint8_t *z = ablk(BLK);
    for (uint64_t l = TABLE_BYTES; l < TABLE_BYTES + (1u << 20) && l + BLK <= piece_size(0) - BLK; l += BLK)
      wr(fd, z, BLK, phys_of(E, n, 0, l));
    free(z);
  }
  on_die = NULL;   // from here the new table may be (partly) on disk: never unlink pieces it could list
  wr(fd, table, TABLE_BYTES, phys_of(E, n, 0, 0));   // the table last: it is what makes the new pieces visible
  if (fsync(fd)) die("fsync raw");
  memset(table, 0, TABLE_BYTES);
  load_table_from_raw(fd, phys_of(scanbuf, n, 0, 0));
  check_canaries(fd);
  close(fd); free(scanbuf);
  printf("%s: %u pieces, %llu MiB data\n", grow ? "grown" : "created", np, (unsigned long long)(H->data_bytes >> 20));
  print_info();
  return 0;
}
static int cmd_verify(int quiet, int allow_gc) {   // allow_gc: delete (FIEMAP == table was just checked)
  uint32_t have = count_pieces(); if (!have) die("%s has no pieces", dirp);
  ext_t *scanbuf = calloc(MAX_EXT, sizeof(ext_t)); if (!scanbuf) die("oom");
  uint32_t gc, n = scan(scanbuf, have, &gc);
  int fd = open_raw(0);
  load_table_from_raw(fd, phys_of(scanbuf, n, 0, 0));
  if (H->npieces != have) die("table lists %u pieces, %u exist", H->npieces, have);
  if (n != H->nextents || memcmp(scanbuf, E, n * sizeof(ext_t))) die("FIEMAP differs from the table: pieces moved");
  check_bounds(E, n);
  check_fsid(fd);
  check_canaries(fd);
  close(fd); free(scanbuf);
  if (gc && !allow_gc) die("f2fs GC failed %u times on a pinned piece (unpinned and moved after gc_pin_file_thresh): stop using "
              "the disk from Linux", gc);
  if (!quiet) printf("verify OK (f2fs pin gc failures 0)\n");
  print_info();
  return 0;
}
static int cmd_delete(const char *uuid) {
  uint8_t u[16]; if (parseuuid(uuid, u)) die("bad uuid");
  cmd_verify(1, 1);
  if (memcmp(u, H->uuid, 16)) die("uuid does not match the table");
  // scrub before unlinking: a stale table + canaries in freed blocks must never map again (vegasdisk.conf survives).
  // The table first (it alone makes the disk mappable), then every canary; all inside the verified extents.
  // (H/E stay valid: they are the in-memory copy.)
  int fd = open_raw(1);
  uint8_t *z = ablk(TABLE_BYTES);
  uint64_t anchor = phys_of(E, H->nextents, 0, 0);
  wr(fd, z, TABLE_BYTES, anchor);
  if (fsync(fd)) die("fsync raw");
  for (uint32_t i = 0; i < H->npieces; i++) {
    uint64_t sz = piece_size(i);
    if (i) wr(fd, z, BLK, phys_of(E, H->nextents, i, 0));
    wr(fd, z, BLK, phys_of(E, H->nextents, i, sz - BLK));
  }
  if (fsync(fd)) die("fsync raw");
  rd(fd, z, BLK, anchor);
  if (!memcmp(z, "VEGASDK1", 8)) die("table still readable after scrub");
  close(fd); free(z);
  char p[300];
  for (uint32_t i = H->npieces; i-- > 0;) { piecepath(p, sizeof p, i); if (unlink(p)) die("unlink %s", p); }
  rmdir(dirp);
  printf("deleted %u pieces\n", H->npieces);
  return 0;
}

/* ---- Linux side ---- */
static int dm_control(void) {   // Debian/initramfs: /dev/mapper/control; Android: /dev/device-mapper
  int fd = open("/dev/mapper/control", O_RDWR); if (fd < 0) fd = open("/dev/device-mapper", O_RDWR);
  if (fd < 0) die("open the device-mapper control node");
  return fd;
}
static int cmd_unmap(const char *name) {
  int cfd = dm_control();
  struct dm_ioctl c; memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", name);
  if (ioctl(cfd, DM_DEV_REMOVE, &c)) die("DM_DEV_REMOVE %s: %s", name, strerror(errno));
  char node[96]; snprintf(node, sizeof node, "/dev/mapper/%s", name);
  struct stat st; if (!lstat(node, &st) && S_ISBLK(st.st_mode)) unlink(node);
  printf("%s removed\n", name); close(cfd); return 0;
}
static char map_name[DM_NAME_LEN]; static int map_cfd = -1;
static void remove_half_made(void) {   // map failed after DM_DEV_CREATE: do not leave a table-less device behind
  struct dm_ioctl c; memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", map_name);
  if (ioctl(map_cfd, DM_DEV_REMOVE, &c)) fprintf(stderr, "vegasdisk: also could not remove %s: %s\n", map_name, strerror(errno));
  char node[96]; snprintf(node, sizeof node, "/dev/mapper/%s", map_name); unlink(node);
}
static int cmd_map(int dry, int ro, const char *dev, const char *anchor_s, const char *uuid_s, const char *name) {
  uint8_t u[16]; if (parseuuid(uuid_s, u)) die("bad uuid");
  char *end; uint64_t anchor = strtoull(anchor_s, &end, 10); if (*end || anchor % BLK) die("bad anchor");
  int fd = open(dev, O_RDONLY | O_DIRECT | O_CLOEXEC); if (fd < 0) die("open %s: %s", dev, strerror(errno));
  struct stat st; if (fstat(fd, &st) || !S_ISBLK(st.st_mode)) die("%s is not a block device", dev);
  if (ioctl(fd, BLKGETSIZE64, &rawbytes)) die("BLKGETSIZE64");
  snprintf(rawname, sizeof rawname, "%s", dev);
  if (!test_mode) {   // must be the userdata partition
    char ue[128], buf[1024];
    snprintf(ue, sizeof ue, "/sys/dev/block/%u:%u/uevent", major(st.st_rdev), minor(st.st_rdev));
    if (sysread(ue, buf, sizeof buf)) die("read %s", ue);
    char *pn = strstr(buf, "PARTNAME=");
    if (!pn || strncmp(pn + 9, "userdata", 8) || (pn[17] != '\n' && pn[17])) die("%s is not the userdata partition", dev);
  }
  if (anchor + TABLE_BYTES > rawbytes) die("anchor outside the device");
  load_table_from_raw(fd, anchor);
  if (memcmp(u, H->uuid, 16)) die("uuid mismatch");
  if (phys_of(E, H->nextents, 0, 0) != anchor) die("table does not start at the anchor");
  check_bounds(E, H->nextents);
  check_fsid(fd);
  check_canaries(fd);
  close(fd);
  // dm table: for each piece, its data range [head, size - BLK) through its extents
  size_t cap = 4096 + (size_t)H->nextents * 2 * (sizeof(struct dm_target_spec) + 64);
  uint8_t *buf = calloc(1, cap); if (!buf) die("oom");
  struct dm_ioctl *io = (struct dm_ioctl *)buf;
  size_t pos = sizeof *io; uint64_t start = 0; uint32_t targets = 0;
  for (uint32_t i = 0; i < H->npieces; i++) {
    uint64_t lo = i ? BLK : TABLE_BYTES, hi = piece_size(i) - BLK;
    for (uint32_t k = 0; k < H->nextents; k++) {
      const ext_t *e = &E[k]; if (e->piece != i) continue;
      uint64_t a = e->logical > lo ? e->logical : lo, b = e->logical + e->len < hi ? e->logical + e->len : hi;
      if (a >= b) continue;
      struct dm_target_spec *t = (struct dm_target_spec *)(buf + pos);
      t->sector_start = start; t->length = (b - a) / 512; strcpy(t->target_type, "linear");
      char *par = (char *)(t + 1);
      int m = snprintf(par, 64, "%u:%u %llu", major(st.st_rdev), minor(st.st_rdev),
                       (unsigned long long)((e->phys + (a - e->logical)) / 512));
      size_t sz = (sizeof *t + m + 1 + 7) & ~7UL; t->next = sz; pos += sz; start += t->length; targets++;
      if (dry) printf("%llu %llu linear %s\n", (unsigned long long)t->sector_start, (unsigned long long)t->length, par);
    }
  }
  if (start * 512 != H->data_bytes) die("mapped size mismatch");
  char us[33]; hexuuid(H->uuid, us);
  printf("%s: %u targets, %llu MiB, uuid %s%s\n", name, targets, (unsigned long long)(H->data_bytes >> 20), us,
         dry ? " (check only)" : "");
  if (dry) return 0;
  int cfd = dm_control();
  struct dm_ioctl c; memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", name);
  if (ioctl(cfd, DM_DEV_CREATE, &c)) die("DM_DEV_CREATE %s: %s", name, strerror(errno));
  snprintf(map_name, sizeof map_name, "%s", name); map_cfd = cfd; on_die = remove_half_made;
  io->version[0] = DM_VERSION_MAJOR; io->data_size = pos; io->data_start = sizeof *io;
  io->target_count = targets; io->flags = ro ? DM_READONLY_FLAG : 0;
  snprintf(io->name, sizeof io->name, "%s", name);
  if (ioctl(cfd, DM_TABLE_LOAD, io)) die("DM_TABLE_LOAD: %s", strerror(errno));
  memset(&c, 0, sizeof c);
  c.version[0] = DM_VERSION_MAJOR; c.data_size = sizeof c; c.data_start = sizeof c;
  snprintf(c.name, sizeof c.name, "%s", name);
  if (ioctl(cfd, DM_DEV_SUSPEND, &c)) die("DM_DEV_SUSPEND (resume): %s", strerror(errno));
  char node[96]; snprintf(node, sizeof node, "/dev/mapper/%s", name);
  mkdir("/dev/mapper", 0755);
  if (access(node, F_OK)) { if (mknod(node, S_IFBLK | 0600, c.dev)) die("mknod %s", node); }
  on_die = NULL;
  printf("%s -> %s (%u:%u)\n", name, node, major(c.dev), minor(c.dev));
  close(cfd);
  return 0;
}

int main(int argc, char **argv) {
  int a = 1;
  if (a < argc && !strcmp(argv[a], "--test")) { test_mode = 1; a++; }
  table = ablk(TABLE_BYTES); H = (hdr_t *)table; E = (ext_t *)(table + BLK);
  _Static_assert(sizeof(ext_t) == 32, "ext_t"); _Static_assert(sizeof(hdr_t) <= BLK, "hdr_t");
  _Static_assert(sizeof(canary_t) <= BLK, "canary_t");
  if (a >= argc) goto usage;
  const char *cmd = argv[a++];
  if (!strcmp(cmd, "create") || !strcmp(cmd, "grow")) {
    if (argc - a < 2) goto usage;
    uint64_t piece_mib = 1024;   // 1 GiB pieces
    if (argc - a >= 4 && !strcmp(argv[a + 2], "--piece-mib")) piece_mib = strtoull(argv[a + 3], 0, 10);
    setdir(argv[a], 1);
    return cmd_create_grow(!strcmp(cmd, "grow"), strtoull(argv[a + 1], 0, 10), piece_mib);
  }
  if (!strcmp(cmd, "verify") || !strcmp(cmd, "info")) { if (argc - a < 1) goto usage; setdir(argv[a], 0); return cmd_verify(!strcmp(cmd, "info"), 0); }
  if (!strcmp(cmd, "delete")) { if (argc - a < 2) goto usage; setdir(argv[a], 0); return cmd_delete(argv[a + 1]); }
  if (!strcmp(cmd, "unmap")) { if (argc - a != 1) goto usage; return cmd_unmap(argv[a]); }
  if (!strcmp(cmd, "map")) {
    int dry = 0, ro = 0;
    for (; a < argc && argv[a][0] == '-'; a++) {
      if (!strcmp(argv[a], "-n")) dry = 1; else if (!strcmp(argv[a], "--ro")) ro = 1; else goto usage;
    }
    if (argc - a != 4) goto usage;
    return cmd_map(dry, ro, argv[a], argv[a + 1], argv[a + 2], argv[a + 3]);
  }
usage:
  fprintf(stderr, "usage: vegasdisk [--test] create|grow <dir> <MiB> [--piece-mib N] | verify|info <dir> |\n"
                  "       delete <dir> <uuid> | map [-n] [--ro] <rawdev> <anchor> <uuid> <name> | unmap <name>\n");
  return 2;
}
