#!/usr/bin/env python3

###
# Generates build files for the project.
# This file also includes the project configuration,
# such as compiler flags and the object matching status.
#
# Usage:
#   python3 configure.py
#   ninja
#
# Append --help to see available options.
###

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from tools.project import (
    Object,
    ProjectConfig,
    calculate_progress,
    generate_build,
    is_windows,
)

### Game versions

# Note: update ``.vscode/c_cpp_properties.json``'s defines
# when updating this list

VERSIONS = [
    "MQ-J",  # 0
    "MQ-U",  # 1
    # "MQ-P",  # 2
    "CE-J",  # 3
    "CE-U",  # 4
    "CE-P",  # 5
]

DEFAULT_VERSION = VERSIONS.index("MQ-J")

### Script's arguments

parser = argparse.ArgumentParser()
parser.add_argument(
    "mode",
    choices=["configure", "progress"],
    default="configure",
    help="script mode (default: configure)",
    nargs="?",
)
parser.add_argument(
    "-v",
    "--version",
    choices=VERSIONS,
    type=str.upper,
    default=VERSIONS[DEFAULT_VERSION],
    help="version to build",
)
parser.add_argument(
    "--build-dir",
    metavar="DIR",
    type=Path,
    default=Path("build"),
    help="base build directory (default: build)",
)
parser.add_argument(
    "--binutils",
    metavar="BINARY",
    type=Path,
    help="path to binutils (optional)",
)
parser.add_argument(
    "--compilers",
    metavar="DIR",
    type=Path,
    help="path to compilers (optional)",
)
parser.add_argument(
    "--map",
    action="store_true",
    help="generate map file(s)",
    default=True,
)
parser.add_argument(
    "--no-asm",
    action="store_true",
    help="don't incorporate .s files from asm directory",
)
parser.add_argument(
    "--debug",
    action="store_true",
    help="build with debug info (non-matching)",
    default=True,
)
if not is_windows():
    parser.add_argument(
        "--wrapper",
        metavar="BINARY",
        type=Path,
        help="path to wibo or wine (optional)",
    )
parser.add_argument(
    "--dtk",
    metavar="BINARY | DIR",
    type=Path,
    help="path to decomp-toolkit binary or source (optional)",
)
parser.add_argument(
    "--sjiswrap",
    metavar="EXE",
    type=Path,
    help="path to sjiswrap.exe (optional)",
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="print verbose output",
)

args = parser.parse_args()

### Create new project configuration

config = ProjectConfig()
config.version = args.version.upper() # allows users to use lowercase when defining the version to use
version_num = VERSIONS.index(config.version)

# Apply arguments
config.build_dir = args.build_dir
config.dtk_path = args.dtk
config.binutils_path = args.binutils
config.compilers_path = args.compilers
config.debug = args.debug
config.generate_map = args.map
config.sjiswrap_path = args.sjiswrap

if not is_windows():
    config.wrapper = args.wrapper

if args.no_asm:
    config.asm_dir = None

### Tool versions

config.binutils_tag = "2.42-1"
config.compilers_tag = "20231018"
config.dtk_tag = "v0.7.5"
config.sjiswrap_tag = "v1.1.1"
config.wibo_tag = "0.6.11"

### Project

config.config_path = Path("config") / config.version / "config.yml"
config.check_sha_path = Path("config") / config.version / "build.sha1"

### Flags (same as zeldaret/oot-gc)

config.asflags = [
    "-mgekko",
    "-I include",
    "-I libc",
    f"-I build/{config.version}/include",
]

config.ldflags = [
    "-fp hardware",
    "-nodefaults",
    "-warn off"
]

# ``-DMQ_J=0 -DMQ-U=2, ...``
version_defines = " ".join(f"-D{version.replace('-', '_')}={i}" for i, version in enumerate(VERSIONS))

cflags_base = [
    "-Cpp_exceptions off",
    "-proc gekko",
    "-fp hardware",
    "-fp_contract on",
    "-enum int",
    "-align powerpc",
    "-nosyspath",
    "-RTTI off",
    "-str reuse",
    "-multibyte",
    "-O4,p",
    "-inline auto",
    "-nodefaults",
    "-msgstyle gcc",

    # includes and macros
    "-i include",
    "-i libc",
    f"-i build/{config.version}/include",
    f"{version_defines}",
    f"-DVERSION={version_num}",
    f"-DDOLPHIN_REV={2002 if version_num == VERSIONS.index('MQ-J') else 2003}",
]

# Debug flags
if config.debug:
    cflags_base.extend(["-sym on", "-DDEBUG=1"])
else:
    cflags_base.append("-DNDEBUG=1")

# SIM flags
cflags_sim = [
    *cflags_base,
    "-inline auto,deferred",
]

# Dolphin SDK/Libraries flags
cflags_dolphin = [
    *cflags_base,
]

# Metrowerks library flags (TBD)
cflags_runtime = [
    *cflags_base,
    "-msgstyle gcc",
    # "-use_lmw_stmw on",
    # "-str reuse,pool,readonly",
    # "-gccinc",
    # "-common off",
    "-inline auto,deferred",
]

# Set linker version to use
config.linker_version = "GC/1.1"

### Helper functions

# for SIM objects (the emulator files)
def SIM(lib_name: str, objects: List[Object]) -> Dict[str, Any]:
    if lib_name == "Core" and version_num != VERSIONS.index("CE-P"):
        # CE PAL contains extra files
        objects.pop(3) # "emulator/Core/xlText.c"
        objects.pop(5) # "emulator/Core/xlFile.c"

    return {
        "lib": lib_name,
        "mw_version": config.linker_version,
        "cflags": cflags_runtime,
        "host": False,
        "objects": objects,
    }

# Helper function for THP objects inside the emulator folders
def THP(lib_name: str, objects: List[Object]) -> Dict[str, Any]:
    return {
        "lib": lib_name,
        "mw_version": config.linker_version,
        "cflags": cflags_dolphin,
        "host": False,
        "objects": objects,
    }

# Helper function for Dolphin libraries
def DolphinLib(lib_name: str, objects: List[Object]) -> Dict[str, Any]:
    return {
        "lib": lib_name,
        "mw_version": "GC/1.2.5n",
        "cflags": cflags_dolphin,
        "host": False,
        "objects": objects,
    }

# Helper function for libraries sharing the same informations
def GenericLib(lib_name: str, objects: List[Object]) -> Dict[str, Any]:
    return {
        "lib": lib_name,
        "mw_version": "GC/1.3.2",
        "cflags": cflags_runtime,
        "host": False,
        "objects": objects,
    }

### Link order

Matching = True
NonMatching = False

config.warn_missing_config = True
config.warn_missing_source = False

config.libs = [
    SIM(
        "Core",
        [
            Object(Matching, "emulator/Core/xlCoreGCN.c"),
            Object(Matching, "emulator/Core/xlPostGCN.c"),
            Object(Matching, "emulator/Core/xlFileGCN.c"),
            Object(Matching, "emulator/Core/xlText.c"),
            Object(Matching, "emulator/Core/xlList.c"),
            Object(Matching, "emulator/Core/xlHeap.c"),
            Object(Matching, "emulator/Core/xlFile.c"),
            Object(Matching, "emulator/Core/xlObject.c"),
        ]
    ),
    SIM(
        "Fire",
        [
            Object(NonMatching if version_num == VERSIONS.index("CE-P") else Matching, "emulator/Fire/simGCN.c"),
            Object(Matching, "emulator/Fire/movie.c"),
        ]
    ),
    THP(
        "THP",
        [
            # NOTE: these files should be in the THP lib
            Object(Matching, "emulator/Fire/THPPlayer.c"),
            Object(Matching, "emulator/Fire/THPAudioDecode.c"),
            Object(Matching, "emulator/Fire/THPDraw.c"),
            Object(Matching, "emulator/Fire/THPRead.c", cflags=[*cflags_dolphin, "-inline auto,deferred"]),
            Object(Matching, "emulator/Fire/THPVideoDecode.c"),
        ]
    ),
    SIM(
        "Fire",
        [
            Object(NonMatching, "emulator/Fire/mcardGCN.c"),
            Object(Matching, "emulator/Fire/codeGCN.c"),
            Object(NonMatching, "emulator/Fire/soundGCN.c"),
            Object(NonMatching, "emulator/Fire/frame.c"),
            Object(Matching, "emulator/Fire/system.c"),
            Object(NonMatching, "emulator/Fire/cpu.c"),
            Object(Matching, "emulator/Fire/pif.c"),
            Object(Matching, "emulator/Fire/ram.c"),
            Object(Matching, "emulator/Fire/rom.c"),
            Object(Matching, "emulator/Fire/rdp.c"),
            Object(Matching, "emulator/Fire/rdb.c"),
            Object(NonMatching, "emulator/Fire/rsp.c"),
            Object(Matching, "emulator/Fire/mips.c"),
            Object(Matching, "emulator/Fire/disk.c"),
            Object(Matching, "emulator/Fire/flash.c"),
            Object(Matching, "emulator/Fire/sram.c"),
            Object(Matching, "emulator/Fire/audio.c"),
            Object(Matching, "emulator/Fire/video.c"),
            Object(Matching, "emulator/Fire/serial.c"),
            Object(Matching, "emulator/Fire/library.c"),
            Object(Matching, "emulator/Fire/peripheral.c"),
            Object(NonMatching, "emulator/Fire/_frameGCNcc.c"),
            Object(NonMatching, "emulator/Fire/_buildtev.c"),
        ],
    ),
    DolphinLib(
        "base",
        [
            Object(NonMatching, "dolphin/base/PPCArch.c"),
        ],
    ),
    DolphinLib(
        "os",
        [
            Object(Matching, "dolphin/os/OS.c"),
            Object(Matching, "dolphin/os/OSAlarm.c"),
            Object(Matching, "dolphin/os/OSAlloc.c"),
            Object(Matching, "dolphin/os/OSArena.c"),
            Object(Matching, "dolphin/os/OSAudioSystem.c"),
            Object(Matching, "dolphin/os/OSCache.c"),
            Object(Matching, "dolphin/os/OSContext.c"),
            Object(Matching, "dolphin/os/OSError.c"),
            Object(Matching, "dolphin/os/OSFont.c"),
            Object(Matching, "dolphin/os/OSInterrupt.c"),
            Object(Matching, "dolphin/os/OSLink.c"),
            Object(Matching, "dolphin/os/OSMessage.c"),
            Object(Matching, "dolphin/os/OSMemory.c"),
            Object(Matching, "dolphin/os/OSMutex.c"),
            Object(Matching if version_num > VERSIONS.index("MQ-J") else NonMatching, "dolphin/os/OSReboot.c"),
            Object(Matching, "dolphin/os/OSReset.c"),
            Object(Matching, "dolphin/os/OSResetSW.c"),
            Object(Matching, "dolphin/os/OSRtc.c"),
            Object(Matching, "dolphin/os/OSSync.c"),
            Object(Matching, "dolphin/os/OSThread.c"),
            Object(Matching, "dolphin/os/OSTime.c"),
            Object(Matching, "dolphin/os/__start.c"),
            Object(Matching, "dolphin/os/__ppc_eabi_init.c"),
        ],
    ),
    DolphinLib(
        "exi",
        [
            Object(NonMatching, "dolphin/exi/EXIBios.c"),
            Object(NonMatching, "dolphin/exi/EXIUart.c"),
        ],
    ),
    DolphinLib(
        "si",
        [
            Object(NonMatching, "dolphin/si/SIBios.c"),
            Object(NonMatching, "dolphin/si/SISamplingRate.c"),
        ],
    ),
    DolphinLib(
        "vi",
        [
            Object(NonMatching, "dolphin/vi/vi.c"),
        ],
    ),
    DolphinLib(
        "db",
        [
            Object(NonMatching, "dolphin/db/db.c"),
        ],
    ),
    DolphinLib(
        "mtx",
        [
            Object(NonMatching, "dolphin/mtx/mtx.c", cflags=[*cflags_base, "-fp_contract off"]),
            Object(NonMatching, "dolphin/mtx/mtxvec.c"),
            Object(NonMatching, "dolphin/mtx/mtx44.c"),
        ],
    ),
    DolphinLib(
        "gx",
        [
            Object(NonMatching, "dolphin/gx/GXInit.c"),
            Object(NonMatching, "dolphin/gx/GXFifo.c"),
            Object(NonMatching, "dolphin/gx/GXAttr.c"),
            Object(NonMatching, "dolphin/gx/GXMisc.c"),
            Object(NonMatching, "dolphin/gx/GXGeometry.c"),
            Object(NonMatching, "dolphin/gx/GXFrameBuf.c"),
            Object(NonMatching, "dolphin/gx/GXLight.c"),
            Object(NonMatching, "dolphin/gx/GXTexture.c"),
            Object(NonMatching, "dolphin/gx/GXBump.c"),
            Object(NonMatching, "dolphin/gx/GXTev.c"),
            Object(NonMatching, "dolphin/gx/GXPixel.c"),
            Object(NonMatching, "dolphin/gx/GXTransform.c"),
            Object(NonMatching, "dolphin/gx/GXPerf.c"),
        ],
    ),
    DolphinLib(
        "pad",
        [
            Object(NonMatching, "dolphin/pad/Padclamp.c"),
            Object(NonMatching, "dolphin/pad/Pad.c"),
        ],
    ),
    DolphinLib(
        "dvd",
        [
            Object(NonMatching, "dolphin/dvd/dvdlow.c"),
            Object(NonMatching, "dolphin/dvd/dvdfs.c"),
            Object(NonMatching, "dolphin/dvd/dvd.c"),
            Object(NonMatching, "dolphin/dvd/dvdqueue.c"),
            Object(NonMatching, "dolphin/dvd/dvderror.c"),
            Object(NonMatching, "dolphin/dvd/dvdidutils.c"),
            Object(NonMatching, "dolphin/dvd/dvdFatal.c"),
            Object(NonMatching, "dolphin/dvd/fstload.c"),
        ],
    ),
    DolphinLib(
        "demo",
        [
            Object(NonMatching, "dolphin/demo/DEMOInit.c"),
            Object(NonMatching, "dolphin/demo/DEMOPuts.c"),
            Object(NonMatching, "dolphin/demo/DEMOFont.c"),
            Object(NonMatching, "dolphin/demo/DEMOPad.c"),
            Object(NonMatching, "dolphin/demo/DEMOStats.c"),
        ],
    ),
    DolphinLib(
        "ai",
        [
            Object(NonMatching, "dolphin/ai/ai.c"),
        ],
    ),
    DolphinLib(
        "ar",
        [
            Object(NonMatching, "dolphin/ar/ar.c"),
        ],
    ),
    DolphinLib(
        "dsp",
        [
            Object(NonMatching, "dolphin/dsp/dsp.c"),
            Object(NonMatching, "dolphin/dsp/dsp_debug.c"),
            Object(NonMatching, "dolphin/dsp/dsp_task.c"),
        ],
    ),
    DolphinLib(
        "card",
        [
            Object(NonMatching, "dolphin/card/CARDBios.c"),
            Object(NonMatching, "dolphin/card/CARDUnlock.c"),
            Object(NonMatching, "dolphin/card/CARDRdwr.c"),
            Object(NonMatching, "dolphin/card/CARDBlock.c"),
            Object(NonMatching, "dolphin/card/CARDDir.c"),
            Object(NonMatching, "dolphin/card/CARDCheck.c"),
            Object(NonMatching, "dolphin/card/CARDMount.c"),
            Object(NonMatching, "dolphin/card/CARDFormat.c"),
            Object(NonMatching, "dolphin/card/CARDOpen.c"),
            Object(NonMatching, "dolphin/card/CARDCreate.c"),
            Object(NonMatching, "dolphin/card/CARDRead.c"),
            Object(NonMatching, "dolphin/card/CARDWrite.c"),
            Object(NonMatching, "dolphin/card/CARDDelete.c"),
            Object(NonMatching, "dolphin/card/CARDStat.c"),
            Object(NonMatching, "dolphin/card/CARDRename.c"),
            Object(NonMatching, "dolphin/card/CARDNet.c"),
        ],
    ),
    DolphinLib(
        "THP",
        [
            Object(NonMatching, "dolphin/thp/THPDec.c"),
            Object(NonMatching, "dolphin/thp/THPAudio.c"),
            Object(NonMatching, "dolphin/thp/texPalette.c"),
        ],
    ),
    GenericLib(
        "TRK_MINNOW_DOLPHIN",
        [
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/mainloop.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/nubevent.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/nubinit.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/msg.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/msgbuf.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/serpoll.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/usr_put.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/dispatch.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/msghndlr.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/support.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/mutex_TRK.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/notify.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/ppc/Generic/flush_cache.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/mem_TRK.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/ppc/Generic/__exception.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/ppc/Generic/targimpl.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Os/dolphin/dolphin_trk.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/ppc/Generic/mpc_7xx_603e.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Portable/main_TRK.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Os/dolphin/dolphin_trk_glue.c"),
            Object(NonMatching, "TRK_MINNOW_DOLPHIN/Os/dolphin/targcont.c"),
        ]
    ),
    GenericLib(
        "Runtime.PPCEABI.H",
        [
            Object(NonMatching, "PowerPC_EABI_Support/Runtime/Src/__mem.c"),
            Object(NonMatching, "PowerPC_EABI_Support/Runtime/Src/__va_arg.c"),
            Object(NonMatching, "PowerPC_EABI_Support/Runtime/Src/global_destructor_chain.c"),
            Object(NonMatching, "PowerPC_EABI_Support/Runtime/Src/runtime.c"),
        ]
    ),
    GenericLib(
        "MSL_C",
        [
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/abort_exit.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Src/ansi_files.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Src/ansi_fp.c", extra_cflags=["-inline noauto"]),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/buffer_io.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/PPC_EABI/SRC/critical_regions.ppc_eabi.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/ctype.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/direct_io.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/errno.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/mbstring.c", extra_cflags=["-inline noauto"]),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/mem.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/mem_funcs.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/misc_io.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/printf.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/scanf.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/string.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/strtoul.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Src/uart_console_io.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/float.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common/Src/wchar_io.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/e_asin.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/e_pow.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/fminmaxdim.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/s_ceil.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/s_copysign.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/s_floor.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/s_frexp.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/s_ldexp.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Double_precision/w_pow.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Single_precision/hyperbolicsf.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Single_precision/log10f.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Single_precision/trigf.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/PPC_EABI/SRC/math_inlines.c"),
            Object(NonMatching, "PowerPC_EABI_Support/MSL/MSL_C/MSL_Common_Embedded/Math/Single_precision/common_float_tables.c"),
        ]
    ),
    GenericLib(
        "amcstubs",
        [
            Object(NonMatching, "amcstubs/AmcExi2Stubs.c"),
        ]
    ),
    GenericLib(
        "OdemuExi2",
        [
            Object(NonMatching, "OdemuExi2/DebuggerDriver.c"),
        ]
    ),
    GenericLib(
        "odenotstub",
        [
            Object(NonMatching, "odenotstub/odenotstub.c"),
        ]
    ),
]

### Execute mode

if args.mode == "configure":
    # Write build.ninja and objdiff.json
    generate_build(config)
elif args.mode == "progress":
    # Print progress and write progress.json
    config.progress_each_module = args.verbose
    calculate_progress(config)
else:
    sys.exit("Unknown mode: " + args.mode)
