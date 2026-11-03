/* Original organizer categorization, with no-replace moves and verified undo.
 * macOS and Linux only. No fallback to an overwrite-capable rename is allowed.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/stat.h>
#include <dirent.h>
#include <limits.h>
#ifdef __linux__
#include <sys/syscall.h>
#include <fcntl.h>
#endif
#define MAX_UNDO 100
#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
typedef struct { char src[PATH_MAX], dest[PATH_MAX]; dev_t dev; ino_t ino; } MoveAction;
static MoveAction undoStack[MAX_UNDO];
static int undoCount = 0;

/* Returns 1=success, 0=collision/no action, -1=error. */
static int moveExclusive(const char *source, const char *dest) {
#ifdef __APPLE__
    int rc = renamex_np(source, dest, RENAME_EXCL);
#elif defined(__linux__) && defined(SYS_renameat2)
    int rc = (int)syscall(SYS_renameat2, AT_FDCWD, source, AT_FDCWD, dest, 1 /* RENAME_NOREPLACE */);
#else
    errno = ENOTSUP;
    int rc = -1;
#endif
    if (rc == 0) return 1;
    return errno == EEXIST || errno == ENOTEMPTY ? 0 : -1;
}

const char* getCategory(const char *filename) {
    const char *ext = strrchr(filename, '.');
    if (!ext) return "Others";
    if (!strcasecmp(ext, ".pdf") || !strcasecmp(ext, ".docx") || !strcasecmp(ext, ".txt")) return "Documents";
    if (!strcasecmp(ext, ".jpg") || !strcasecmp(ext, ".jpeg") || !strcasecmp(ext, ".png") || !strcasecmp(ext, ".gif")) return "Images";
    if (!strcasecmp(ext, ".mp3") || !strcasecmp(ext, ".wav")) return "Music";
    if (!strcasecmp(ext, ".mp4") || !strcasecmp(ext, ".mkv") || !strcasecmp(ext, ".mov")) return "Videos";
    if (!strcasecmp(ext, ".zip") || !strcasecmp(ext, ".tar") || !strcasecmp(ext, ".rar")) return "Archives";
    return "Others";
}


int moveFile(const char *source, const char *destFolder) {
    struct stat file, folder;
    if (!source || !destFolder || strlen(source) >= PATH_MAX ||
        lstat(source, &file) != 0 || !S_ISREG(file.st_mode)) return -1;
    if (mkdir(destFolder, 0755) != 0 && errno != EEXIST) return -1;
    /* A pre-existing symlink is not an acceptable category directory. */
    if (lstat(destFolder, &folder) != 0 || !S_ISDIR(folder.st_mode)) return -1;
    const char *name = strrchr(source, '/'); name = name ? name + 1 : source;
    char dest[PATH_MAX];
    int n = snprintf(dest, sizeof(dest), "%s/%s", destFolder, name);
    if (n < 0 || (size_t)n >= sizeof(dest)) return -1;
    int status = moveExclusive(source, dest);
    if (status != 1) return status;
    /* Keep the newest 100 successful moves, never record failed/skipped moves. */
    if (undoCount == MAX_UNDO) {
        memmove(undoStack, undoStack + 1, sizeof(MoveAction) * (MAX_UNDO - 1));
        undoCount--;
    }
    MoveAction *action = &undoStack[undoCount++];
    snprintf(action->src, sizeof(action->src), "%s", source);
    snprintf(action->dest, sizeof(action->dest), "%s", dest);
    action->dev = file.st_dev; action->ino = file.st_ino;
    return 1;
}

/* Return number moved, or -1 when the directory cannot be opened.
 * Collisions remain in the watched folder; symlinks and subdirectories are skipped.
 */
int organizeFolder(const char *folderPath, void (*callback)(int)) {
    struct stat folder;
    if (lstat(folderPath, &folder) != 0 || !S_ISDIR(folder.st_mode)) return -1;
    DIR *dir = opendir(folderPath);
    if (!dir) return -1;
    struct dirent *entry;
    int moved = 0;
    while ((entry = readdir(dir))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char filePath[PATH_MAX], destFolder[PATH_MAX];
        int n = snprintf(filePath, sizeof(filePath), "%s/%s", folderPath, entry->d_name);
        if (n < 0 || (size_t)n >= sizeof(filePath)) continue;
        struct stat file;
        if (lstat(filePath, &file) != 0 || !S_ISREG(file.st_mode)) continue;
        n = snprintf(destFolder, sizeof(destFolder), "%s/%s", folderPath, getCategory(entry->d_name));
        if (n < 0 || (size_t)n >= sizeof(destFolder)) continue;
        if (moveFile(filePath, destFolder) == 1) moved++;
    }
    closedir(dir);
    if (callback) callback(100);
    return moved;
}

int undoLastMove(void) {
    if (!undoCount) return 0;
    MoveAction *action = &undoStack[undoCount - 1];
    struct stat file;
    /* Never move a replacement file now occupying the old destination. */
    if (lstat(action->dest, &file) != 0 || !S_ISREG(file.st_mode) ||
        file.st_dev != action->dev || file.st_ino != action->ino) return -1;
    int status = moveExclusive(action->dest, action->src);
    if (status == 1) undoCount--;
    return status; /* Collision/error leaves the action available for retry. */
}
