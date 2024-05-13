#include "dolphin/os.h"
#include "dolphin/types.h"

typedef struct HeapCell {
    struct HeapCell* prev;
    struct HeapCell* next;
    u32 size;
} HeapCell;

typedef struct Heap {
    s32 size;
    struct HeapCell* free; // linked list of free cells
    struct HeapCell* allocated; // linked list of allocated cells
} Heap;

void* ArenaEnd;
void* ArenaStart;
int NumHeaps;
struct Heap* HeapArray;
volatile OSHeapHandle __OSCurrHeap = -1;

#define InRange(addr, start, end) ((u8*)(start) <= (u8*)(addr) && (u8*)(addr) < (u8*)(end))
#define OFFSET(addr, align) (((u32)(addr) & ((align) - 1)))

#define ALIGNMENT 32
#define MINOBJSIZE 64

static inline void* DLAddFront(struct HeapCell* neighbor, struct HeapCell* cell) {
    cell->next = neighbor;
    cell->prev = NULL;
    if (neighbor != NULL)
        neighbor->prev = cell;
    return cell;
}

void DLLookup(void) {
    // UNUSED FUNCTION
}

static inline HeapCell* DLExtract(struct HeapCell* list, struct HeapCell* cell) {
    if (cell->next != NULL)
        cell->next->prev = cell->prev;
    if (cell->prev == NULL)
        list = cell->next;
    else
        cell->prev->next = cell->next;
    return list;
}

static HeapCell* DLInsert(HeapCell* list, HeapCell* cell, void* unused /* needed to match OSFreeToHeap */) {
    HeapCell* before = NULL;
    HeapCell* after = list;

    while (after != NULL) {
        if (cell <= after)
            break;
        before = after;
        after = after->next;
    }
    cell->next = after;
    cell->prev = before;
    if (after != NULL) {
        after->prev = cell;
        if ((u8*)cell + cell->size == (u8*)after) {
            cell->size += after->size;
            after = after->next;
            cell->next = after;
            if (after != NULL)
                after->prev = cell;
        }
    }
    if (before != NULL) {
        before->next = cell;
        if ((u8*)before + before->size == (u8*)cell) {
            before->size += cell->size;
            before->next = after;
            if (after != NULL)
                after->prev = before;
        }
        return list;
    }
    return cell;
}

void DLOverlap(void) {
    // UNUSED FUNCTION
}

void DLSize(void) {
    // UNUSED FUNCTION
}

void* OSAllocFromHeap(OSHeapHandle heap, u32 size) {
    struct Heap* hd = &HeapArray[heap];
    s32 sizeAligned = OSRoundUp32B(ALIGNMENT + size);
    struct HeapCell* cell;
    struct HeapCell* oldTail;
    u32 leftoverSpace;

    // find first cell with enough capacity
    for (cell = hd->free; cell != NULL; cell = cell->next) {
        if (sizeAligned <= (s32)cell->size)
            break;
    }
    if (cell == NULL)
        return NULL;

    leftoverSpace = cell->size - sizeAligned;
    if (leftoverSpace < MINOBJSIZE) {
        // remove this cell from the free list
        hd->free = DLExtract(hd->free, cell);
    } else {
        // remove this cell from the free list and make a new cell out of the
        // remaining space
        struct HeapCell* newcell = (void*)((u8*)cell + sizeAligned);
        cell->size = sizeAligned;
        newcell->size = leftoverSpace;
        newcell->prev = cell->prev;
        newcell->next = cell->next;
        if (newcell->next != NULL)
            newcell->next->prev = newcell;
        if (newcell->prev != NULL)
            newcell->prev->next = newcell;
        else
            hd->free = newcell;
    }

    // add the cell to the beginning of the allocated list
    hd->allocated = DLAddFront(hd->allocated, cell);

    return (u8*)cell + ALIGNMENT;
}

// void OSAllocFixed(void)
// {
// 	// UNUSED FUNCTION
// }

void OSFreeToHeap(OSHeapHandle heap, void* ptr) {
    HeapCell* cell = (void*)((u8*)ptr - ALIGNMENT);
    Heap* hd = &HeapArray[heap];
    HeapCell* list = hd->allocated;

    // remove cell from the allocated list
    // hd->allocated = DLExtract(hd->allocated, cell);
    if (cell->next != NULL)
        cell->next->prev = cell->prev;
    if (cell->prev == NULL)
        list = cell->next;
    else
        cell->prev->next = cell->next;
    hd->allocated = list;
    hd->free = DLInsert(hd->free, cell, list);
}

OSHeapHandle OSSetCurrentHeap(OSHeapHandle heap) {
    OSHeapHandle old = __OSCurrHeap;

    __OSCurrHeap = heap;
    return old;
}

void* OSInitAlloc(void* arenaStart, void* arenaEnd, int maxHeaps) {
    u32 totalSize = maxHeaps * sizeof(struct Heap);
    int i;

    HeapArray = arenaStart;
    NumHeaps = maxHeaps;

    for (i = 0; i < NumHeaps; i++) {
        Heap* heap = &HeapArray[i];

        heap->size = -1;
        heap->free = heap->allocated = NULL;
    }

    __OSCurrHeap = -1;

    arenaStart = (u8*)HeapArray + totalSize;
    arenaStart = (void*)OSRoundUp32B(arenaStart);

    ArenaStart = arenaStart;
    ArenaEnd = (void*)OSRoundDown32B(arenaEnd);

    return arenaStart;
}

OSHeapHandle OSCreateHeap(void* start, void* end) {
    int i;
    HeapCell* cell = (void*)OSRoundUp32B(start);

    end = (void*)OSRoundDown32B(end);
    for (i = 0; i < NumHeaps; i++) {
        Heap* hd = &HeapArray[i];

        if (hd->size < 0) {
            hd->size = (u8*)end - (u8*)cell;
            cell->prev = NULL;
            cell->next = NULL;
            cell->size = hd->size;
            hd->free = cell;
            hd->allocated = NULL;
            return i;
        }
    }
    return -1;
}

// void OSDestroyHeap(void)
// {
// 	// UNUSED FUNCTION
// }

// void OSAddToHeap(void)
// {
// 	// UNUSED FUNCTION
// }

#define ASSERTREPORT(line, cond)                               \
    if (!(cond)) {                                             \
        OSReport("OSCheckHeap: Failed " #cond " in %d", line); \
        return -1;                                             \
    }

s32 OSCheckHeap(int heap) {
    struct Heap* hd;
    struct HeapCell* cell;
    long total = 0;
    long free = 0;

    ASSERTREPORT(0x37D, HeapArray);
    ASSERTREPORT(0x37E, 0 <= heap && heap < NumHeaps);
    hd = &HeapArray[heap];
    ASSERTREPORT(0x381, 0 <= hd->size);

    ASSERTREPORT(0x383, hd->allocated == NULL || hd->allocated->prev == NULL);

    for (cell = hd->allocated; cell; cell = cell->next) {
        ASSERTREPORT(0x386, InRange(cell, ArenaStart, ArenaEnd));
        ASSERTREPORT(0x387, OFFSET(cell, ALIGNMENT) == 0);
        ASSERTREPORT(0x388, cell->next == NULL || cell->next->prev == cell);
        ASSERTREPORT(0x389, MINOBJSIZE <= cell->size);
        ASSERTREPORT(0x38A, OFFSET(cell->size, ALIGNMENT) == 0);
        total += cell->size;
        ASSERTREPORT(0x38D, 0 < total && total <= hd->size);
#ifdef ENABLE_HEAPDESC
        ASSERTREPORT(0x390, cell->hd == hd);
        ASSERTREPORT(0x391, ALIGNMENT + cell->requested <= cell->size);
#endif
    }

    ASSERTREPORT(0x395, hd->free == NULL || hd->free->prev == NULL);

    for (cell = hd->free; cell; cell = cell->next) {
        ASSERTREPORT(0x398, InRange(cell, ArenaStart, ArenaEnd));
        ASSERTREPORT(0x399, OFFSET(cell, ALIGNMENT) == 0);
        ASSERTREPORT(0x39A, cell->next == NULL || cell->next->prev == cell);
        ASSERTREPORT(0x39B, MINOBJSIZE <= cell->size);
        ASSERTREPORT(0x39C, OFFSET(cell->size, ALIGNMENT) == 0);
        // clang-format off
        ASSERTREPORT(0x39D, cell->next == NULL || (char*) cell + cell->size < (char*) cell->next);
        // clang-format on
        total += cell->size;
        free = (cell->size + free);
        free -= ALIGNMENT;
        ASSERTREPORT(0x3A1, 0 < total && total <= hd->size);
#ifdef ENABLE_HEAPDESC
        ASSERTREPORT(0x3A4, cell->hd == NULL);
#endif
    }
    ASSERTREPORT(0x3A8, total == hd->size);
    return free;
}

// void OSReferentSize(void)
// {
// 	// UNUSED FUNCTION
// }

#define ASSERTMSGLINE(line, cond, msg) \
    if (!(cond)) {                     \
        OSReport(msg, line);           \
        return;                        \
    }

// unused but the strings are required to match
void OSDumpHeap(int heap) {
    struct Heap* hd;
    struct HeapCell* cell;

    OSReport("\nOSDumpHeap(%d):\n", heap);
    // ASSERTMSGLINE(0x3DE, HeapArray, "OSDumpHeap(): heap is not initialized.");
    // ASSERTMSGLINE(0x3DF, (heap >= 0) && (heap < NumHeaps), "OSDumpHeap(): invalid heap handle.");
    hd = &HeapArray[heap];
    if (hd->size < 0) {
        OSReport("--------Inactive\n");
        return;
    }
    // ASSERTMSGLINE(0x3E8, OSCheckHeap(heap) >= 0, "OSDumpHeap(): heap is broken.");
#ifdef ENABLE_HEAPDESC
    OSReport("padding %d/(%f%%) header %d/(%f%%) payload %d/(%f%%)\n", hd->paddingBytes,
             (100.0 * hd->paddingBytes / hd->size), hd->headerBytes, (100.0 * hd->headerBytes / hd->size),
             hd->payloadBytes, (100.0 * hd->payloadBytes / hd->size));
#endif
    OSReport("addr	size		end	prev	next\n");
    OSReport("--------Allocated\n");

    // ASSERTMSGLINE(0x3F5, hd->allocated == NULL || hd->allocated->prev == NULL, "OSDumpHeap(): heap is broken.");

    for (cell = hd->allocated; cell; cell = cell->next) {
        OSReport("%x	%d	%x	%x	%x\n", cell, cell->size, (char*)cell + cell->size, cell->prev,
                 cell->next);
    }
    OSReport("--------Free\n");
    for (cell = hd->free; cell; cell = cell->next) {
        OSReport("%x	%d	%x	%x	%x\n", cell, cell->size, (char*)cell + cell->size, cell->prev,
                 cell->next);
    }
}

// void OSVisitAllocated(void)
// {
// 	// UNUSED FUNCTION
// }
