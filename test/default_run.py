#
# Copyright (C) 2022 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys, os, shutil, shlex, re, subprocess, glob
from argparse import ArgumentParser, BooleanOptionalAction, Namespace
from os import path
from os.path import isfile, isdir, basename
from typing import List
from subprocess import DEVNULL, PIPE, STDOUT
from tempfile import NamedTemporaryFile

COLOR_RED = '\033[91m'
COLOR_BLUE = '\033[94m'
COLOR_NORMAL = '\033[0m'

def parse_args(argv):
  argp, opt_bool = ArgumentParser(), BooleanOptionalAction
  argp.add_argument("--64", dest="is64", action="store_true")
  argp.add_argument("--O", action="store_true")
  argp.add_argument("--Xcompiler-option", default=[], action="append")
  argp.add_argument("--add-libdir-argument", action="store_true")
  argp.add_argument("--android-art-root", default="/apex/com.android.art")
  argp.add_argument("--android-i18n-root", default="/apex/com.android.i18n")
  argp.add_argument("--android-log-tags", default="*:i")
  argp.add_argument("--android-root", default="/system")
  argp.add_argument("--android-runtime-option", default=[], action="append")
  argp.add_argument("--android-tzdata-root", default="/apex/com.android.tzdata")
  argp.add_argument("--app-image", default=True, action=opt_bool)
  argp.add_argument("--baseline", action="store_true")
  argp.add_argument("--bionic", action="store_true")
  argp.add_argument("--boot", default="")
  argp.add_argument("--chroot", default="")
  argp.add_argument("--compact-dex-level")
  argp.add_argument("--compiler-only-option", default=[], action="append")
  argp.add_argument("--create-runner", action="store_true")
  argp.add_argument("--diff-min-log-tag", default="E")
  argp.add_argument("--debug", action="store_true")
  argp.add_argument("--debug-agent")
  argp.add_argument("--debug-wrap-agent", action="store_true")
  argp.add_argument("--dex2oat-dm", action="store_true")
  argp.add_argument(
      "--dex2oat-rt-timeout", type=int,
      default=360)  # The *hard* timeout.  6 min.
  argp.add_argument(
      "--dex2oat-timeout", type=int, default=300)  # The "soft" timeout.  5 min.
  argp.add_argument("--dry-run", action="store_true")
  argp.add_argument("--experimental", default=[], action="append")
  argp.add_argument("--external-log-tags", action="store_true")
  argp.add_argument("--gc-stress", action="store_true")
  argp.add_argument("--gdb", action="store_true")
  argp.add_argument("--gdb-arg", default=[], action="append")
  argp.add_argument("--gdb-dex2oat", action="store_true")
  argp.add_argument("--gdb-dex2oat-args", default=[], action="append")
  argp.add_argument("--gdbserver", action="store_true")
  argp.add_argument("--gdbserver-bin")
  argp.add_argument("--gdbserver-port", default=":5039")
  argp.add_argument("--host", action="store_true")
  argp.add_argument("--image", default=True, action=opt_bool)
  argp.add_argument("--instruction-set-features", default="")
  argp.add_argument("--interpreter", action="store_true")
  argp.add_argument("--invoke-with", default=[], action="append")
  argp.add_argument("--jit", action="store_true")
  argp.add_argument("--jvm", action="store_true")
  argp.add_argument("--jvmti", action="store_true")
  argp.add_argument("--jvmti-field-stress", action="store_true")
  argp.add_argument("--jvmti-redefine-stress", action="store_true")
  argp.add_argument("--jvmti-step-stress", action="store_true")
  argp.add_argument("--jvmti-trace-stress", action="store_true")
  argp.add_argument("--lib", default="")
  argp.add_argument("--optimize", default=True, action=opt_bool)
  argp.add_argument("--prebuild", default=True, action=opt_bool)
  argp.add_argument("--profile", action="store_true")
  argp.add_argument("--random-profile", action="store_true")
  argp.add_argument("--relocate", default=False, action=opt_bool)
  argp.add_argument("--runtime-dm", action="store_true")
  argp.add_argument("--runtime-extracted-zipapex", default="")
  argp.add_argument("--runtime-option", default=[], action="append")
  argp.add_argument("--runtime-zipapex", default="")
  argp.add_argument("--secondary", action="store_true")
  argp.add_argument("--secondary-app-image", default=True, action=opt_bool)
  argp.add_argument("--secondary-class-loader-context", default="")
  argp.add_argument("--secondary-compilation", default=True, action=opt_bool)
  argp.add_argument("--simpleperf", action="store_true")
  argp.add_argument("--sync", action="store_true")
  argp.add_argument("--testlib", default=[], action="append")
  argp.add_argument("--timeout", default=0, type=int)
  argp.add_argument("--vdex", action="store_true")
  argp.add_argument("--vdex-arg", default=[], action="append")
  argp.add_argument("--vdex-filter", default="")
  argp.add_argument("--verify", default=True, action=opt_bool)
  argp.add_argument("--verify-soft-fail", action="store_true")
  argp.add_argument("--with-agent", default=[], action="append")
  argp.add_argument("--zygote", action="store_true")
  argp.add_argument("--test_args", default=[], action="append")
  argp.add_argument("--stdout_file", default="")
  argp.add_argument("--stderr_file", default="")
  argp.add_argument("--main", default="Main")
  argp.add_argument("--expected_exit_code", default=0)

  # Python parser requires the format --key=--value, since without the equals symbol
  # it looks like the required value has been omitted and there is just another flag.
  # For example, '--args --foo --host --64' will become '--arg=--foo --host --64'
  # because otherwise the --args is missing its value and --foo is unknown argument.
  for i, arg in reversed(list(enumerate(argv))):
    if arg in [
        "--args", "--runtime-option", "--android-runtime-option",
        "-Xcompiler-option", "--compiler-only-option"
    ]:
      argv[i] += "=" + argv.pop(i + 1)

  # Accept single-dash arguments as if they were double-dash arguments.
  # For exmpample, '-Xcompiler-option' becomes '--Xcompiler-option'
  # became single-dash can be used only with single-letter arguments.
  for i, arg in list(enumerate(argv)):
    if arg.startswith("-") and not arg.startswith("--"):
      argv[i] = "-" + arg
    if arg == "--":
      break

  return argp.parse_args(argv)


# Note: This must start with the CORE_IMG_JARS in Android.common_path.mk
# because that's what we use for compiling the boot.art image.
# It may contain additional modules from TEST_CORE_JARS.
bpath_modules = ("core-oj core-libart okhttp bouncycastle apache-xml core-icu4j"
                 " conscrypt")


# Helper function to construct paths for apex modules (for both -Xbootclasspath and
# -Xbootclasspath-location).
def get_apex_bootclasspath_impl(bpath_prefix: str):
  bpath_separator = ""
  bpath = ""
  bpath_jar = ""
  for bpath_module in bpath_modules.split(" "):
    apex_module = "com.android.art"
    if bpath_module == "conscrypt":
      apex_module = "com.android.conscrypt"
    if bpath_module == "core-icu4j":
      apex_module = "com.android.i18n"
    bpath_jar = f"/apex/{apex_module}/javalib/{bpath_module}.jar"
    bpath += f"{bpath_separator}{bpath_prefix}{bpath_jar}"
    bpath_separator = ":"
  return bpath


# Gets a -Xbootclasspath paths with the apex modules.
def get_apex_bootclasspath(host: bool):
  bpath_prefix = ""

  if host:
    bpath_prefix = os.environ["ANDROID_HOST_OUT"]

  return get_apex_bootclasspath_impl(bpath_prefix)


# Gets a -Xbootclasspath-location paths with the apex modules.
def get_apex_bootclasspath_locations(host: bool):
  bpath_location_prefix = ""

  if host:
    ANDROID_BUILD_TOP=os.environ["ANDROID_BUILD_TOP"]
    ANDROID_HOST_OUT=os.environ["ANDROID_HOST_OUT"]
    if ANDROID_HOST_OUT[0:len(ANDROID_BUILD_TOP)+1] == f"{ANDROID_BUILD_TOP}/":
      bpath_location_prefix=ANDROID_HOST_OUT[len(ANDROID_BUILD_TOP)+1:]
    else:
      print(f"ANDROID_BUILD_TOP/ is not a prefix of ANDROID_HOST_OUT"\
            "\nANDROID_BUILD_TOP={ANDROID_BUILD_TOP}"\
            "\nANDROID_HOST_OUT={ANDROID_HOST_OUT}")
      sys.exit(1)

  return get_apex_bootclasspath_impl(bpath_location_prefix)


def default_run(ctx, args, **kwargs):
  # Clone the args so we can modify them without affecting args in the caller.
  args = Namespace(**vars(args))

  # Overwrite args based on the named parameters.
  # E.g. the caller can do `default_run(args, jvmti=True)` to modify args.jvmti.
  for name, new_value in kwargs.items():
    old_value = getattr(args, name)
    assert isinstance(new_value, old_value.__class__), name + " should have type " + str(old_value.__class__)
    if isinstance(old_value, list):
      setattr(args, name, old_value + new_value)  # Lists get merged.
    else:
      setattr(args, name, new_value)

  # Script debugging: Record executed commands into the given directory.
  # This is useful to ensure that changes to the script don't change behaviour.
  # (the commands are appended so the directory needs to be cleared before run)
  ART_TEST_CMD_DIR = os.environ.get("ART_TEST_CMD_DIR")

  # Script debugging: Record executed commands, but don't actually run the main test.
  # This makes it possible the extract the test commands without waiting for days.
  # This will make tests fail since there is no stdout.  Use with large -j value.
  ART_TEST_DRY_RUN = os.environ.get("ART_TEST_DRY_RUN")

  def run(cmdline: str,
          env={},
          check=True,
          parse_exit_code_from_stdout=False,
          expected_exit_code=0,
          save_cmd=True) -> subprocess.CompletedProcess:
    env.setdefault("PATH", PATH)  # Ensure that PATH is always set.
    env = {k: v for k, v in env.items() if v != None}  # Filter "None" entries.
    if ART_TEST_CMD_DIR and save_cmd and cmdline != "true":
      tmp = os.environ["DEX_LOCATION"]
      with open(
          os.path.join(ART_TEST_CMD_DIR, os.environ["FULL_TEST_NAME"]),
          "a") as f:
        # Replace DEX_LOCATION (which is randomly generated temporary directory),
        # with a deterministic placeholder so that we can do a diff from run to run.
        f.write("\n".join(
            k + ":" + v.replace(tmp, "<tmp>") for k, v in env.items()) + "\n\n")
        f.write(re.sub(" +", "\n", cmdline).replace(tmp, "<tmp>") + "\n\n")
      if ART_TEST_DRY_RUN and ("dalvikvm" in cmdline or
                               "adb shell chroot" in cmdline):
        cmdline = "true"  # We still need to run some command, so run the no-op "true" binary instead.

    if cmdline != "true":
      print(f"{COLOR_BLUE}$ {cmdline}{COLOR_NORMAL}")
    proc = subprocess.run([cmdline],
                          shell=True,
                          executable="/bin/bash",
                          env=env,
                          encoding="utf8",
                          capture_output=True)
    if proc.stdout:
      print(proc.stdout.strip(), flush=True)
    if proc.stderr:
      print(proc.stderr.strip(), flush=True)

    # ADB forwards exit code from the executed command, but if ADB process itself crashes,
    # it will also return non-zero exit code, and we can not distinguish those two cases.
    # As a work-around, we wrap the executed command so that it always returns 0 exit code
    # and we also make it print the actual exit code as the last line of its stdout.
    if parse_exit_code_from_stdout:
      assert proc.returncode == 0, f"ADB failed (exit code {proc.returncode})"
      found = re.search("exit_code=([0-9]+)$", proc.stdout)
      assert found, "Expected exit code as the last line of stdout"
      proc.stdout = proc.stdout[:found.start(0)]  # Remove the exit code from stdout.
      proc.returncode = int(found.group(1))  # Use it as if it was the process exit code.

    # Check the exit code.
    if (check and proc.returncode != expected_exit_code):
      suffix = ""
      if proc.returncode == 124:
        suffix = " (TIME OUT)"
      elif expected_exit_code != 0:
        suffix = " (expected {})".format(expected_exit_code)
      print(f"{COLOR_RED}{TEST_NAME} FAILED: Command returned exit code "
            f"{proc.returncode}{suffix}{COLOR_NORMAL}", file=sys.stderr)
      sys.exit(1)

    return proc

  # Store copy of stdout&stderr of command in files so that we can diff them later.
  # This may run under 'adb shell' so we are limited only to 'sh' shell feature set.
  def tee(cmd: str):
    # 'tee' works on stdout only, so we need to temporarily swap stdout and stderr.
    cmd = f"({cmd} | tee -a {DEX_LOCATION}/{basename(args.stdout_file)}) 3>&1 1>&2 2>&3"
    cmd = f"({cmd} | tee -a {DEX_LOCATION}/{basename(args.stderr_file)}) 3>&1 1>&2 2>&3"
    return f"set -o pipefail; {cmd}"  # Use exit code of first failure in piped command.

  class Adb():

    def __init__(self):
      self.env = {
          "ADB_VENDOR_KEYS": os.environ.get("ADB_VENDOR_KEYS"),
          "ANDROID_SERIAL": os.environ.get("ANDROID_SERIAL"),
          "PATH": os.environ.get("PATH"),
      }

    def root(self) -> None:
      run("adb root", self.env)

    def wait_for_device(self) -> None:
      run("adb wait-for-device", self.env)

    def shell(self, cmdline: str, **kwargs) -> subprocess.CompletedProcess:
      return run(f"adb shell '{cmdline}; echo exit_code=$?'", self.env,
                 parse_exit_code_from_stdout=True, **kwargs)

    def push(self, src: str, dst: str, **kwargs) -> None:
      run(f"adb push {src} {dst}", self.env, **kwargs)

    def pull(self, src: str, dst: str, **kwargs) -> None:
      run(f"adb pull {src} {dst}", self.env, **kwargs)

  adb = Adb()

  local_path = os.path.dirname(__file__)

  # Check that stdout is connected to a terminal and that we have at least 1 color.
  # This ensures that if the stdout is not connected to a terminal and instead
  # the stdout will be used for a log, it will not append the color characters.
  bold_red = ""
  if sys.stdout.isatty():
    if int(subprocess.run(["tput", "colors"], capture_output=True).stdout) >= 1:
      bold_red = subprocess.run(["tput", "bold"],
                                text=True,
                                capture_output=True).stdout.strip()
      bold_red += subprocess.run(["tput", "setaf", "1"],
                                 text=True,
                                 capture_output=True).stdout.strip()

  ANDROID_BUILD_TOP = os.environ.get("ANDROID_BUILD_TOP")
  ANDROID_DATA = os.environ.get("ANDROID_DATA")
  ANDROID_HOST_OUT = os.environ["ANDROID_HOST_OUT"]
  ANDROID_LOG_TAGS = os.environ.get("ANDROID_LOG_TAGS", "")
  ART_TIME_OUT_MULTIPLIER = int(os.environ.get("ART_TIME_OUT_MULTIPLIER", 1))
  DEX2OAT = os.environ.get("DEX2OAT", "")
  DEX_LOCATION = os.environ["DEX_LOCATION"]
  JAVA = os.environ.get("JAVA")
  OUT_DIR = os.environ.get("OUT_DIR")
  PATH = os.environ.get("PATH", "")
  SANITIZE_HOST = os.environ.get("SANITIZE_HOST", "")
  TEST_NAME = os.environ["TEST_NAME"]
  USE_EXRACTED_ZIPAPEX = os.environ.get("USE_EXRACTED_ZIPAPEX", "")

  assert ANDROID_BUILD_TOP, "Did you forget to run `lunch`?"

  ANDROID_ROOT = args.android_root
  ANDROID_ART_ROOT = args.android_art_root
  ANDROID_I18N_ROOT = args.android_i18n_root
  ANDROID_TZDATA_ROOT = args.android_tzdata_root
  ARCHITECTURES_32 = "(arm|x86|none)"
  ARCHITECTURES_64 = "(arm64|x86_64|none)"
  ARCHITECTURES_PATTERN = ARCHITECTURES_32
  GET_DEVICE_ISA_BITNESS_FLAG = "--32"
  BOOT_IMAGE = args.boot
  CHROOT = args.chroot
  COMPILE_FLAGS = ""
  DALVIKVM = "dalvikvm32"
  DEBUGGER = "n"
  WITH_AGENT = args.with_agent
  DEBUGGER_AGENT = args.debug_agent
  WRAP_DEBUGGER_AGENT = args.debug_wrap_agent
  DEX2OAT_NDEBUG_BINARY = "dex2oat32"
  DEX2OAT_DEBUG_BINARY = "dex2oatd32"
  EXPERIMENTAL = args.experimental
  FALSE_BIN = "false"
  FLAGS = ""
  ANDROID_FLAGS = ""
  GDB = ""
  GDB_ARGS = ""
  GDB_DEX2OAT = ""
  GDB_DEX2OAT_ARGS = ""
  GDBSERVER_DEVICE = "gdbserver"
  GDBSERVER_HOST = "gdbserver"
  HAVE_IMAGE = args.image
  HOST = args.host
  BIONIC = args.bionic
  CREATE_ANDROID_ROOT = False
  USE_ZIPAPEX = (args.runtime_zipapex != "")
  ZIPAPEX_LOC = args.runtime_zipapex
  USE_EXTRACTED_ZIPAPEX = (args.runtime_extracted_zipapex != "")
  EXTRACTED_ZIPAPEX_LOC = args.runtime_extracted_zipapex
  INTERPRETER = args.interpreter
  JIT = args.jit
  INVOKE_WITH = " ".join(args.invoke_with)
  USE_JVMTI = args.jvmti
  IS_JVMTI_TEST = False
  ADD_LIBDIR_ARGUMENTS = args.add_libdir_argument
  SUFFIX64 = ""
  ISA = "x86"
  LIBRARY_DIRECTORY = "lib"
  TEST_DIRECTORY = "nativetest"
  MAIN = args.main
  OPTIMIZE = args.optimize
  PREBUILD = args.prebuild
  RELOCATE = args.relocate
  SECONDARY_DEX = ""
  TIME_OUT = "n"  # "n" (disabled), "timeout" (use timeout), "gdb" (use gdb)
  TIMEOUT_DUMPER = "signal_dumper"
  # Values in seconds.
  TIME_OUT_EXTRA = 0
  TIME_OUT_VALUE = args.timeout
  USE_GDB = args.gdb
  USE_GDBSERVER = args.gdbserver
  GDBSERVER_PORT = args.gdbserver_port
  USE_GDB_DEX2OAT = args.gdb_dex2oat
  USE_JVM = args.jvm
  VERIFY = "y" if args.verify else "n"  # y=yes,n=no,s=softfail
  ZYGOTE = ""
  DEX_VERIFY = ""
  INSTRUCTION_SET_FEATURES = args.instruction_set_features
  ARGS = ""
  VDEX_ARGS = ""
  DRY_RUN = args.dry_run
  TEST_VDEX = args.vdex
  TEST_DEX2OAT_DM = args.dex2oat_dm
  TEST_RUNTIME_DM = args.runtime_dm
  TEST_IS_NDEBUG = args.O
  APP_IMAGE = args.app_image
  SECONDARY_APP_IMAGE = args.secondary_app_image
  SECONDARY_CLASS_LOADER_CONTEXT = args.secondary_class_loader_context
  SECONDARY_COMPILATION = args.secondary_compilation
  JVMTI_STRESS = False
  JVMTI_REDEFINE_STRESS = args.jvmti_redefine_stress
  JVMTI_STEP_STRESS = args.jvmti_step_stress
  JVMTI_FIELD_STRESS = args.jvmti_field_stress
  JVMTI_TRACE_STRESS = args.jvmti_trace_stress
  PROFILE = args.profile
  RANDOM_PROFILE = args.random_profile
  DEX2OAT_TIMEOUT = args.dex2oat_timeout
  DEX2OAT_RT_TIMEOUT = args.dex2oat_rt_timeout
  CREATE_RUNNER = args.create_runner
  INT_OPTS = ""
  SIMPLEPERF = args.simpleperf
  DEBUGGER_OPTS = ""
  JVM_VERIFY_ARG = ""
  LIB = args.lib

  # if True, run 'sync' before dalvikvm to make sure all files from
  # build step (e.g. dex2oat) were finished writing.
  SYNC_BEFORE_RUN = args.sync

  # When running a debug build, we want to run with all checks.
  ANDROID_FLAGS += " -XX:SlowDebug=true"
  # The same for dex2oatd, both prebuild and runtime-driven.
  ANDROID_FLAGS += (" -Xcompiler-option --runtime-arg -Xcompiler-option "
                    "-XX:SlowDebug=true")
  COMPILER_FLAGS = "  --runtime-arg -XX:SlowDebug=true"

  # Let the compiler and runtime know that we are running tests.
  COMPILE_FLAGS += " --compile-art-test"
  ANDROID_FLAGS += " -Xcompiler-option --compile-art-test"

  if USE_JVMTI:
    IS_JVMTI_TEST = True
    # Secondary images block some tested behavior.
    SECONDARY_APP_IMAGE = False
  if args.gc_stress:
    # Give an extra 20 mins if we are gc-stress.
    TIME_OUT_EXTRA += 1200
  for arg in args.testlib:
    ARGS += f" {arg}"
  for arg in args.test_args:
    ARGS += f" {arg}"
  for arg in args.compiler_only_option:
    COMPILE_FLAGS += f" {arg}"
  for arg in args.Xcompiler_option:
    FLAGS += f" -Xcompiler-option {arg}"
    COMPILE_FLAGS += f" {arg}"
  if args.secondary:
    SECONDARY_DEX = f":{DEX_LOCATION}/{TEST_NAME}-ex.jar"
    # Enable cfg-append to make sure we get the dump for both dex files.
    # (otherwise the runtime compilation of the secondary dex will overwrite
    # the dump of the first one).
    FLAGS += " -Xcompiler-option --dump-cfg-append"
    COMPILE_FLAGS += " --dump-cfg-append"
  for arg in args.android_runtime_option:
    ANDROID_FLAGS += f" {arg}"
  for arg in args.runtime_option:
    FLAGS += f" {arg}"
    if arg == "-Xmethod-trace":
      # Method tracing can slow some tests down a lot.
      TIME_OUT_EXTRA += 1200
  if args.compact_dex_level:
    arg = args.compact_dex_level
    COMPILE_FLAGS += f" --compact-dex-level={arg}"
  if JVMTI_REDEFINE_STRESS:
    # APP_IMAGE doesn't really work with jvmti redefine stress
    SECONDARY_APP_IMAGE = False
    JVMTI_STRESS = True
  if JVMTI_REDEFINE_STRESS or JVMTI_STEP_STRESS or JVMTI_FIELD_STRESS or JVMTI_TRACE_STRESS:
    USE_JVMTI = True
    JVMTI_STRESS = True
  if HOST:
    ANDROID_ROOT = ANDROID_HOST_OUT
    ANDROID_ART_ROOT = f"{ANDROID_HOST_OUT}/com.android.art"
    ANDROID_I18N_ROOT = f"{ANDROID_HOST_OUT}/com.android.i18n"
    ANDROID_TZDATA_ROOT = f"{ANDROID_HOST_OUT}/com.android.tzdata"
    # On host, we default to using the symlink, as the PREFER_32BIT
    # configuration is the only configuration building a 32bit version of
    # dex2oat.
    DEX2OAT_DEBUG_BINARY = "dex2oatd"
    DEX2OAT_NDEBUG_BINARY = "dex2oat"
  if BIONIC:
    # We need to create an ANDROID_ROOT because currently we cannot create
    # the frameworks/libcore with linux_bionic so we need to use the normal
    # host ones which are in a different location.
    CREATE_ANDROID_ROOT = True
  if USE_ZIPAPEX:
    # TODO (b/119942078): Currently apex does not support
    # symlink_preferred_arch so we will not have a dex2oatd to execute and
    # need to manually provide
    # dex2oatd64.
    DEX2OAT_DEBUG_BINARY = "dex2oatd64"
  if WITH_AGENT:
    USE_JVMTI = True
  if DEBUGGER_AGENT:
    DEBUGGER = "agent"
    USE_JVMTI = True
    TIME_OUT = "n"
  if args.debug:
    USE_JVMTI = True
    DEBUGGER = "y"
    TIME_OUT = "n"
  if args.gdbserver_bin:
    arg = args.gdbserver_bin
    GDBSERVER_HOST = arg
    GDBSERVER_DEVICE = arg
  if args.gdbserver or args.gdb or USE_GDB_DEX2OAT:
    TIME_OUT = "n"
  for arg in args.gdb_arg:
    GDB_ARGS += f" {arg}"
  if args.gdb_dex2oat_args:
    for arg in arg.split(";"):
      GDB_DEX2OAT_ARGS += f"{arg} "
  if args.zygote:
    ZYGOTE = "-Xzygote"
    print("Spawning from zygote")
  if args.baseline:
    FLAGS += " -Xcompiler-option --baseline"
    COMPILE_FLAGS += " --baseline"
  if args.verify_soft_fail:
    VERIFY = "s"
  if args.is64:
    SUFFIX64 = "64"
    ISA = "x86_64"
    GDBSERVER_DEVICE = "gdbserver64"
    DALVIKVM = "dalvikvm64"
    LIBRARY_DIRECTORY = "lib64"
    TEST_DIRECTORY = "nativetest64"
    ARCHITECTURES_PATTERN = ARCHITECTURES_64
    GET_DEVICE_ISA_BITNESS_FLAG = "--64"
    DEX2OAT_NDEBUG_BINARY = "dex2oat64"
    DEX2OAT_DEBUG_BINARY = "dex2oatd64"
  if args.vdex_filter:
    option = args.vdex_filter
    VDEX_ARGS += f" --compiler-filter={option}"
  if args.vdex_arg:
    arg = args.vdex_arg
    VDEX_ARGS += f" {arg}"

# HACK: Force the use of `signal_dumper` on host.
  if HOST:
    TIME_OUT = "timeout"

# If you change this, update the timeout in testrunner.py as well.
  if not TIME_OUT_VALUE:
    # 10 minutes is the default.
    TIME_OUT_VALUE = 600

    # For sanitized builds use a larger base.
    # TODO: Consider sanitized target builds?
    if SANITIZE_HOST != "":
      TIME_OUT_VALUE = 1500  # 25 minutes.

    TIME_OUT_VALUE += TIME_OUT_EXTRA

# Escape hatch for slow hosts or devices. Accept an environment variable as a timeout factor.
  if ART_TIME_OUT_MULTIPLIER:
    TIME_OUT_VALUE *= ART_TIME_OUT_MULTIPLIER

# The DEX_LOCATION with the chroot prefix, if any.
  CHROOT_DEX_LOCATION = f"{CHROOT}{DEX_LOCATION}"

  # If running on device, determine the ISA of the device.
  if not HOST and not USE_JVM:
    ISA = run(
        f"{ANDROID_BUILD_TOP}/art/test/utils/get-device-isa {GET_DEVICE_ISA_BITNESS_FLAG}",
        adb.env,
        save_cmd=False).stdout.strip()

  if not USE_JVM:
    FLAGS += f" {ANDROID_FLAGS}"
    # we don't want to be trying to get adbconnections since the plugin might
    # not have been built.
    FLAGS += " -XjdwpProvider:none"
    for feature in EXPERIMENTAL:
      FLAGS += f" -Xexperimental:{feature} -Xcompiler-option --runtime-arg -Xcompiler-option -Xexperimental:{feature}"
      COMPILE_FLAGS = f"{COMPILE_FLAGS} --runtime-arg -Xexperimental:{feature}"

  if CREATE_ANDROID_ROOT:
    ANDROID_ROOT = f"{DEX_LOCATION}/android-root"

  if ZYGOTE == "":
    if OPTIMIZE:
      if VERIFY == "y":
        DEX_OPTIMIZE = "-Xdexopt:verified"
      else:
        DEX_OPTIMIZE = "-Xdexopt:all"
      print("Performing optimizations")
    else:
      DEX_OPTIMIZE = "-Xdexopt:none"
      print("Skipping optimizations")

    if VERIFY == "y":
      JVM_VERIFY_ARG = "-Xverify:all"
      print("Performing verification")
    elif VERIFY == "s":
      JVM_VERIFY_ARG = "Xverify:all"
      DEX_VERIFY = "-Xverify:softfail"
      print("Forcing verification to be soft fail")
    else:  # VERIFY == "n"
      DEX_VERIFY = "-Xverify:none"
      JVM_VERIFY_ARG = "-Xverify:none"
      print("Skipping verification")

  print("------------------------------")

  if DEBUGGER == "y":
    # Use this instead for ddms and connect by running 'ddms':
    # DEBUGGER_OPTS="-XjdwpOptions=server=y,suspend=y -XjdwpProvider:adbconnection"
    # TODO: add a separate --ddms option?

    PORT = 12345
    print("Waiting for jdb to connect:")
    if not HOST:
      print(f"    adb forward tcp:{PORT} tcp:{PORT}")
    print(f"    jdb -attach localhost:{PORT}")
    if not USE_JVM:
      # Use the default libjdwp agent. Use --debug-agent to use a custom one.
      DEBUGGER_OPTS = f"-agentpath:libjdwp.so=transport=dt_socket,address={PORT},server=y,suspend=y -XjdwpProvider:internal"
    else:
      DEBUGGER_OPTS = f"-agentlib:jdwp=transport=dt_socket,address={PORT},server=y,suspend=y"
  elif DEBUGGER == "agent":
    PORT = 12345
    # TODO Support ddms connection and support target.
    assert HOST, "--debug-agent not supported yet for target!"
    AGENTPATH = DEBUGGER_AGENT
    if WRAP_DEBUGGER_AGENT:
      WRAPPROPS = f"{ANDROID_ROOT}/{LIBRARY_DIRECTORY}/libwrapagentpropertiesd.so"
      if TEST_IS_NDEBUG:
        WRAPPROPS = f"{ANDROID_ROOT}/{LIBRARY_DIRECTORY}/libwrapagentproperties.so"
      AGENTPATH = f"{WRAPPROPS}={ANDROID_BUILD_TOP}/art/tools/libjdwp-compat.props,{AGENTPATH}"
    print(f"Connect to localhost:{PORT}")
    DEBUGGER_OPTS = f"-agentpath:{AGENTPATH}=transport=dt_socket,address={PORT},server=y,suspend=y"

  for agent in WITH_AGENT:
    FLAGS += f" -agentpath:{agent}"

  if USE_JVMTI:
    if not USE_JVM:
      plugin = "libopenjdkjvmtid.so"
      if TEST_IS_NDEBUG:
        plugin = "libopenjdkjvmti.so"
      # We used to add flags here that made the runtime debuggable but that is not
      # needed anymore since the plugin can do it for us now.
      FLAGS += f" -Xplugin:{plugin}"

      # For jvmti tests, set the threshold of compilation to 1, so we jit early to
      # provide better test coverage for jvmti + jit. This means we won't run
      # the default --jit configuration but it is not too important test scenario for
      # jvmti tests. This is art specific flag, so don't use it with jvm.
      FLAGS += " -Xjitthreshold:1"

# Add the libdir to the argv passed to the main function.
  if ADD_LIBDIR_ARGUMENTS:
    if HOST:
      ARGS += f" {ANDROID_HOST_OUT}/{TEST_DIRECTORY}/"
    else:
      ARGS += f" /data/{TEST_DIRECTORY}/art/{ISA}/"
  if IS_JVMTI_TEST:
    agent = "libtiagentd.so"
    lib = "tiagentd"
    if TEST_IS_NDEBUG:
      agent = "libtiagent.so"
      lib = "tiagent"

    ARGS += f" {lib}"
    if USE_JVM:
      FLAGS += f" -agentpath:{ANDROID_HOST_OUT}/nativetest64/{agent}={TEST_NAME},jvm"
    else:
      FLAGS += f" -agentpath:{agent}={TEST_NAME},art"

  if JVMTI_STRESS:
    agent = "libtistressd.so"
    if TEST_IS_NDEBUG:
      agent = "libtistress.so"

    # Just give it a default start so we can always add ',' to it.
    agent_args = "jvmti-stress"
    if JVMTI_REDEFINE_STRESS:
      # We really cannot do this on RI so don't both passing it in that case.
      if not USE_JVM:
        agent_args = f"{agent_args},redefine"
    if JVMTI_FIELD_STRESS:
      agent_args = f"{agent_args},field"
    if JVMTI_STEP_STRESS:
      agent_args = f"{agent_args},step"
    if JVMTI_TRACE_STRESS:
      agent_args = f"{agent_args},trace"
    # In the future add onto this;
    if USE_JVM:
      FLAGS += f" -agentpath:{ANDROID_HOST_OUT}/nativetest64/{agent}={agent_args}"
    else:
      FLAGS += f" -agentpath:{agent}={agent_args}"

  if USE_JVM:
    env = {
        "ANDROID_I18N_ROOT": ANDROID_I18N_ROOT,
        "DEX_LOCATION": DEX_LOCATION,
        "JAVA_HOME": os.environ["JAVA_HOME"],
        "LANG":
            "en_US.UTF-8",  # Needed to enable unicode and make the output is deterministic.
        "LD_LIBRARY_PATH": f"{ANDROID_HOST_OUT}/lib64",
    }
    # Some jvmti tests are flaky without -Xint on the RI.
    if IS_JVMTI_TEST:
      FLAGS += " -Xint"
    # Xmx is necessary since we don't pass down the ART flags to JVM.
    # We pass the classes2 path whether it's used (src-multidex) or not.
    cmdline = f"{JAVA} {DEBUGGER_OPTS} {JVM_VERIFY_ARG} -Xmx256m -classpath classes:classes2 {FLAGS} {MAIN} {ARGS}"
    if CREATE_RUNNER:
      with open("runit.sh", "w") as f:
        f.write("#!/bin/bash")
        print(f"export LD_LIBRARY_PATH=\"{LD_LIBRARY_PATH}\"")
        f.write(cmdline)
      os.chmod("runit.sh", 0o777)
      pwd = os.getcwd()
      print(f"Runnable test script written to {pwd}/runit.sh")
      return
    else:
      run(tee(cmdline),
          env,
          expected_exit_code=args.expected_exit_code)
      return

  b_path = get_apex_bootclasspath(HOST)
  b_path_locations = get_apex_bootclasspath_locations(HOST)

  BCPEX = ""
  if isfile(f"{TEST_NAME}-bcpex.jar"):
    BCPEX = f":{DEX_LOCATION}/{TEST_NAME}-bcpex.jar"

  # Pass down the bootclasspath
  FLAGS += f" -Xbootclasspath:{b_path}{BCPEX}"
  FLAGS += f" -Xbootclasspath-locations:{b_path_locations}{BCPEX}"
  COMPILE_FLAGS += f" --runtime-arg -Xbootclasspath:{b_path}"
  COMPILE_FLAGS += f" --runtime-arg -Xbootclasspath-locations:{b_path_locations}"

  if not HAVE_IMAGE:
    # Disable image dex2oat - this will forbid the runtime to patch or compile an image.
    FLAGS += " -Xnoimage-dex2oat"

    # We'll abuse a second flag here to test different behavior. If --relocate, use the
    # existing image - relocation will fail as patching is disallowed. If --no-relocate,
    # pass a non-existent image - compilation will fail as dex2oat is disallowed.
    if not RELOCATE:
      BOOT_IMAGE = "/system/non-existent/boot.art"
    # App images cannot be generated without a boot image.
    APP_IMAGE = False
  DALVIKVM_BOOT_OPT = f"-Ximage:{BOOT_IMAGE}"

  if USE_GDB_DEX2OAT:
    assert HOST, "The --gdb-dex2oat option is not yet implemented for target."

  if USE_GDB:
    assert not USE_GDBSERVER, "Cannot pass both --gdb and --gdbserver at the same time!"
    if not HOST:
      # We might not have any hostname resolution if we are using a chroot.
      GDB = f"{GDBSERVER_DEVICE} --no-startup-with-shell 127.0.0.1{GDBSERVER_PORT}"
    else:
      if run("uname").stdout.strip() == "Darwin":
        GDB = "lldb"
        GDB_ARGS += f" -- {DALVIKVM}"
        DALVIKVM = ""
      else:
        GDB = "gdb"
        GDB_ARGS += f" --args {DALVIKVM}"
        # Enable for Emacs "M-x gdb" support. TODO: allow extra gdb arguments on command line.
        # gdbargs=f"--annotate=3 {gdbargs}"
  elif USE_GDBSERVER:
    if not HOST:
      # We might not have any hostname resolution if we are using a chroot.
      GDB = f"{GDBSERVER_DEVICE} --no-startup-with-shell 127.0.0.1{GDBSERVER_PORT}"
    else:
      GDB = f"{GDBSERVER_HOST} {GDBSERVER_PORT}"

      assert shutil.which(GDBSERVER_HOST), f"{GDBSERVER_HOST} is not available"

  if INTERPRETER:
    INT_OPTS += " -Xint"

  if JIT:
    INT_OPTS += " -Xusejit:true"
  else:
    INT_OPTS += " -Xusejit:false"

  if INTERPRETER or JIT:
    if VERIFY == "y":
      INT_OPTS += " -Xcompiler-option --compiler-filter=verify"
      COMPILE_FLAGS += " --compiler-filter=verify"
    elif VERIFY == "s":
      INT_OPTS += " -Xcompiler-option --compiler-filter=extract"
      COMPILE_FLAGS += " --compiler-filter=extract"
      DEX_VERIFY = f"{DEX_VERIFY} -Xverify:softfail"
    else:  # VERIFY == "n"
      INT_OPTS += " -Xcompiler-option --compiler-filter=assume-verified"
      COMPILE_FLAGS += " --compiler-filter=assume-verified"
      DEX_VERIFY = f"{DEX_VERIFY} -Xverify:none"

  JNI_OPTS = "-Xjnigreflimit:512 -Xcheck:jni"

  COMPILE_FLAGS += " --runtime-arg -Xnorelocate"
  if RELOCATE:
    FLAGS += " -Xrelocate"
  else:
    FLAGS += " -Xnorelocate"

  if BIONIC:
    # This is the location that soong drops linux_bionic builds. Despite being
    # called linux_bionic-x86 the build is actually amd64 (x86_64) only.
    assert path.exists(f"{OUT_DIR}/soong/host/linux_bionic-x86"), (
        "linux_bionic-x86 target doesn't seem to have been built!")
    # Set TIMEOUT_DUMPER manually so it works even with apex's
    TIMEOUT_DUMPER = f"{OUT_DIR}/soong/host/linux_bionic-x86/bin/signal_dumper"

  # Prevent test from silently falling back to interpreter in no-prebuild mode. This happens
  # when DEX_LOCATION path is too long, because vdex/odex filename is constructed by taking
  # full path to dex, stripping leading '/', appending '@classes.vdex' and changing every
  # remaining '/' into '@'.
  if HOST:
    max_filename_size = int(
        run(f"getconf NAME_MAX {DEX_LOCATION}", save_cmd=False).stdout)
  else:
    # There is no getconf on device, fallback to standard value.
    # See NAME_MAX in kernel <linux/limits.h>
    max_filename_size = 255
  # Compute VDEX_NAME.
  DEX_LOCATION_STRIPPED = DEX_LOCATION.lstrip("/")
  VDEX_NAME = f"{DEX_LOCATION_STRIPPED}@{TEST_NAME}.jar@classes.vdex".replace(
      "/", "@")
  assert len(VDEX_NAME) <= max_filename_size, "Dex location path too long"

  if HOST:
    # On host, run binaries (`dex2oat(d)`, `dalvikvm`, `profman`) from the `bin`
    # directory under the "Android Root" (usually `out/host/linux-x86`).
    #
    # TODO(b/130295968): Adjust this if/when ART host artifacts are installed
    # under the ART root (usually `out/host/linux-x86/com.android.art`).
    ANDROID_ART_BIN_DIR = f"{ANDROID_ROOT}/bin"
  else:
    # On target, run binaries (`dex2oat(d)`, `dalvikvm`, `profman`) from the ART
    # APEX's `bin` directory. This means the linker will observe the ART APEX
    # linker configuration file (`/apex/com.android.art/etc/ld.config.txt`) for
    # these binaries.
    ANDROID_ART_BIN_DIR = f"{ANDROID_ART_ROOT}/bin"

  profman_cmdline = "true"
  dex2oat_cmdline = "true"
  vdex_cmdline = "true"
  dm_cmdline = "true"
  mkdir_locations = f"{DEX_LOCATION}/dalvik-cache/{ISA}"
  strip_cmdline = "true"
  sync_cmdline = "true"
  linkroot_cmdline = "true"
  linkroot_overlay_cmdline = "true"
  setupapex_cmdline = "true"
  installapex_cmdline = "true"
  installapex_test_cmdline = "true"

  def linkdirs(host_out: str, root: str):
    dirs = list(filter(os.path.isdir, glob.glob(os.path.join(host_out, "*"))))
    # Also create a link for the boot image.
    dirs.append(f"{ANDROID_HOST_OUT}/apex/art_boot_images")
    return " && ".join(f"ln -sf {dir} {root}" for dir in dirs)

  if CREATE_ANDROID_ROOT:
    mkdir_locations += f" {ANDROID_ROOT}"
    linkroot_cmdline = linkdirs(ANDROID_HOST_OUT, ANDROID_ROOT)
    if BIONIC:
      # TODO Make this overlay more generic.
      linkroot_overlay_cmdline = linkdirs(
          f"{OUT_DIR}/soong/host/linux_bionic-x86", ANDROID_ROOT)
    # Replace the boot image to a location expected by the runtime.
    DALVIKVM_BOOT_OPT = f"-Ximage:{ANDROID_ROOT}/art_boot_images/javalib/boot.art"

  if USE_ZIPAPEX:
    # TODO Currently this only works for linux_bionic zipapexes because those are
    # stripped and so small enough that the ulimit doesn't kill us.
    mkdir_locations += f" {DEX_LOCATION}/zipapex"
    setupapex_cmdline = f"unzip -o -u {ZIPAPEX_LOC} apex_payload.zip -d {DEX_LOCATION}"
    installapex_cmdline = f"unzip -o -u {DEX_LOCATION}/apex_payload.zip -d {DEX_LOCATION}/zipapex"
    ANDROID_ART_BIN_DIR = f"{DEX_LOCATION}/zipapex/bin"
  elif USE_EXTRACTED_ZIPAPEX:
    # Just symlink the zipapex binaries
    ANDROID_ART_BIN_DIR = f"{DEX_LOCATION}/zipapex/bin"
    # Force since some tests manually run this file twice.
    # If the {RUN} is executed multiple times we don't need to recreate the link
    installapex_test_cmdline = f"test -L {DEX_LOCATION}/zipapex"
    installapex_cmdline = f"ln -s -f --verbose {EXTRACTED_ZIPAPEX_LOC} {DEX_LOCATION}/zipapex"

  # PROFILE takes precedence over RANDOM_PROFILE, since PROFILE tests require a
  # specific profile to run properly.
  if PROFILE or RANDOM_PROFILE:
    profman_cmdline = f"{ANDROID_ART_BIN_DIR}/profman  \
      --apk={DEX_LOCATION}/{TEST_NAME}.jar \
      --dex-location={DEX_LOCATION}/{TEST_NAME}.jar"

    if isfile(f"{TEST_NAME}-ex.jar") and SECONDARY_COMPILATION:
      profman_cmdline = f"{profman_cmdline} \
        --apk={DEX_LOCATION}/{TEST_NAME}-ex.jar \
        --dex-location={DEX_LOCATION}/{TEST_NAME}-ex.jar"

    COMPILE_FLAGS = f"{COMPILE_FLAGS} --profile-file={DEX_LOCATION}/{TEST_NAME}.prof"
    FLAGS = f"{FLAGS} -Xcompiler-option --profile-file={DEX_LOCATION}/{TEST_NAME}.prof"
    if PROFILE:
      profman_cmdline = f"{profman_cmdline} --create-profile-from={DEX_LOCATION}/profile \
          --reference-profile-file={DEX_LOCATION}/{TEST_NAME}.prof"

    else:
      profman_cmdline = f"{profman_cmdline} --generate-test-profile={DEX_LOCATION}/{TEST_NAME}.prof \
          --generate-test-profile-seed=0"

  def get_prebuilt_lldb_path():
    CLANG_BASE = "prebuilts/clang/host"
    CLANG_VERSION = run(
        f"{ANDROID_BUILD_TOP}/build/soong/scripts/get_clang_version.py"
    ).stdout.strip()
    uname = run("uname -s").stdout.strip()
    if uname == "Darwin":
      PREBUILT_NAME = "darwin-x86"
    elif uname == "Linux":
      PREBUILT_NAME = "linux-x86"
    else:
      print(
          "Unknown host $(uname -s). Unsupported for debugging dex2oat with LLDB.",
          file=sys.stderr)
      return
    CLANG_PREBUILT_HOST_PATH = f"{ANDROID_BUILD_TOP}/{CLANG_BASE}/{PREBUILT_NAME}/{CLANG_VERSION}"
    # If the clang prebuilt directory exists and the reported clang version
    # string does not, then it is likely that the clang version reported by the
    # get_clang_version.py script does not match the expected directory name.
    if isdir(f"{ANDROID_BUILD_TOP}/{CLANG_BASE}/{PREBUILT_NAME}"):
      assert isdir(CLANG_PREBUILT_HOST_PATH), (
          "The prebuilt clang directory exists, but the specific "
          "clang\nversion reported by get_clang_version.py does not exist in "
          "that path.\nPlease make sure that the reported clang version "
          "resides in the\nprebuilt clang directory!")

    # The lldb-server binary is a dependency of lldb.
    os.environ[
        "LLDB_DEBUGSERVER_PATH"] = f"{CLANG_PREBUILT_HOST_PATH}/runtimes_ndk_cxx/x86_64/lldb-server"

    # Set the current terminfo directory to TERMINFO so that LLDB can read the
    # termcap database.
    terminfo = re.search("/.*/terminfo/", run("infocmp", save_cmd=False).stdout)
    if terminfo:
      os.environ["TERMINFO"] = terminfo[0]

    return f"{CLANG_PREBUILT_HOST_PATH}/bin/lldb.sh"

  def write_dex2oat_cmdlines(name: str):
    nonlocal dex2oat_cmdline, dm_cmdline, vdex_cmdline

    class_loader_context = ""
    enable_app_image = False
    if APP_IMAGE:
      enable_app_image = True

    # If the name ends in -ex then this is a secondary dex file
    if name.endswith("-ex"):
      # Lazily realize the default value in case DEX_LOCATION/TEST_NAME change
      nonlocal SECONDARY_CLASS_LOADER_CONTEXT
      if SECONDARY_CLASS_LOADER_CONTEXT == "":
        if SECONDARY_DEX == "":
          # Tests without `--secondary` load the "-ex" jar in a separate PathClassLoader
          # that is a child of the main PathClassLoader. If the class loader is constructed
          # in any other way, the test needs to specify the secondary CLC explicitly.
          SECONDARY_CLASS_LOADER_CONTEXT = f"PCL[];PCL[{DEX_LOCATION}/{TEST_NAME}.jar]"
        else:
          # Tests with `--secondary` load the `-ex` jar a part of the main PathClassLoader.
          SECONDARY_CLASS_LOADER_CONTEXT = f"PCL[{DEX_LOCATION}/{TEST_NAME}.jar]"
      class_loader_context = f"'--class-loader-context={SECONDARY_CLASS_LOADER_CONTEXT}'"
      enable_app_image = enable_app_image and SECONDARY_APP_IMAGE

    app_image = ""
    if enable_app_image:
      app_image = f"--app-image-file={DEX_LOCATION}/oat/{ISA}/{name}.art --resolve-startup-const-strings=true"

    nonlocal GDB_DEX2OAT, GDB_DEX2OAT_ARGS
    if USE_GDB_DEX2OAT:
      prebuilt_lldb_path = get_prebuilt_lldb_path()
      GDB_DEX2OAT = f"{prebuilt_lldb_path} -f"
      GDB_DEX2OAT_ARGS += " -- "

    dex2oat_binary = DEX2OAT_DEBUG_BINARY
    if TEST_IS_NDEBUG:
      dex2oat_binary = DEX2OAT_NDEBUG_BINARY
    dex2oat_cmdline = f"{INVOKE_WITH} {GDB_DEX2OAT} \
                        {ANDROID_ART_BIN_DIR}/{dex2oat_binary} \
                        {GDB_DEX2OAT_ARGS} \
                        {COMPILE_FLAGS} \
                        --boot-image={BOOT_IMAGE} \
                        --dex-file={DEX_LOCATION}/{name}.jar \
                        --oat-file={DEX_LOCATION}/oat/{ISA}/{name}.odex \
                        {app_image} \
                        --generate-mini-debug-info \
                        --instruction-set={ISA} \
                        {class_loader_context}"

    if INSTRUCTION_SET_FEATURES != "":
      dex2oat_cmdline += f" --instruction-set-features={INSTRUCTION_SET_FEATURES}"

    # Add in a timeout. This is important for testing the compilation/verification time of
    # pathological cases. We do not append a timeout when debugging dex2oat because we
    # do not want it to exit while debugging.
    # Note: as we don't know how decent targets are (e.g., emulator), only do this on the host for
    #       now. We should try to improve this.
    #       The current value is rather arbitrary. run-tests should compile quickly.
    # Watchdog timeout is in milliseconds so add 3 '0's to the dex2oat timeout.
    if HOST and not USE_GDB_DEX2OAT:
      # Use SIGRTMIN+2 to try to dump threads.
      # Use -k 1m to SIGKILL it a minute later if it hasn't ended.
      dex2oat_cmdline = f"timeout -k {DEX2OAT_TIMEOUT}s -s SIGRTMIN+2 {DEX2OAT_RT_TIMEOUT}s {dex2oat_cmdline} --watchdog-timeout={DEX2OAT_TIMEOUT}000"
    if PROFILE or RANDOM_PROFILE:
      vdex_cmdline = f"{dex2oat_cmdline} {VDEX_ARGS} --input-vdex={DEX_LOCATION}/oat/{ISA}/{name}.vdex --output-vdex={DEX_LOCATION}/oat/{ISA}/{name}.vdex"
    elif TEST_VDEX:
      if VDEX_ARGS == "":
        # If no arguments need to be passed, just delete the odex file so that the runtime only picks up the vdex file.
        vdex_cmdline = f"rm {DEX_LOCATION}/oat/{ISA}/{name}.odex"
      else:
        vdex_cmdline = f"{dex2oat_cmdline} {VDEX_ARGS} --compact-dex-level=none --input-vdex={DEX_LOCATION}/oat/{ISA}/{name}.vdex"
    elif TEST_DEX2OAT_DM:
      vdex_cmdline = f"{dex2oat_cmdline} {VDEX_ARGS} --dump-timings --dm-file={DEX_LOCATION}/oat/{ISA}/{name}.dm"
      dex2oat_cmdline = f"{dex2oat_cmdline} --copy-dex-files=false --output-vdex={DEX_LOCATION}/oat/{ISA}/primary.vdex"
      dm_cmdline = f"zip -qj {DEX_LOCATION}/oat/{ISA}/{name}.dm {DEX_LOCATION}/oat/{ISA}/primary.vdex"
    elif TEST_RUNTIME_DM:
      dex2oat_cmdline = f"{dex2oat_cmdline} --copy-dex-files=false --output-vdex={DEX_LOCATION}/oat/{ISA}/primary.vdex"
      dm_cmdline = f"zip -qj {DEX_LOCATION}/{name}.dm {DEX_LOCATION}/oat/{ISA}/primary.vdex"

# Enable mini-debug-info for JIT (if JIT is used).

  FLAGS += " -Xcompiler-option --generate-mini-debug-info"

  if PREBUILD:
    mkdir_locations += f" {DEX_LOCATION}/oat/{ISA}"

    # "Primary".
    write_dex2oat_cmdlines(TEST_NAME)
    dex2oat_cmdline = re.sub(" +", " ", dex2oat_cmdline)
    dm_cmdline = re.sub(" +", " ", dm_cmdline)
    vdex_cmdline = re.sub(" +", " ", vdex_cmdline)

    # Enable mini-debug-info for JIT (if JIT is used).
    FLAGS += " -Xcompiler-option --generate-mini-debug-info"

    if isfile(f"{TEST_NAME}-ex.jar") and SECONDARY_COMPILATION:
      # "Secondary" for test coverage.

      # Store primary values.
      base_dex2oat_cmdline = dex2oat_cmdline
      base_dm_cmdline = dm_cmdline
      base_vdex_cmdline = vdex_cmdline

      write_dex2oat_cmdlines(f"{TEST_NAME}-ex")
      dex2oat_cmdline = re.sub(" +", " ", dex2oat_cmdline)
      dm_cmdline = re.sub(" +", " ", dm_cmdline)
      vdex_cmdline = re.sub(" +", " ", vdex_cmdline)

      # Concatenate.
      dex2oat_cmdline = f"{base_dex2oat_cmdline} && {dex2oat_cmdline}"
      dm_cmdline = base_dm_cmdline  # Only use primary dm.
      vdex_cmdline = f"{base_vdex_cmdline} && {vdex_cmdline}"

  if SYNC_BEFORE_RUN:
    sync_cmdline = "sync"

  DALVIKVM_ISA_FEATURES_ARGS = ""
  if INSTRUCTION_SET_FEATURES != "":
    DALVIKVM_ISA_FEATURES_ARGS = f"-Xcompiler-option --instruction-set-features={INSTRUCTION_SET_FEATURES}"

# java.io.tmpdir can only be set at launch time.
  TMP_DIR_OPTION = ""
  if not HOST:
    TMP_DIR_OPTION = "-Djava.io.tmpdir=/data/local/tmp"

# The build servers have an ancient version of bash so we cannot use @Q.
  QUOTED_DALVIKVM_BOOT_OPT = shlex.quote(DALVIKVM_BOOT_OPT)

  DALVIKVM_CLASSPATH = f"{DEX_LOCATION}/{TEST_NAME}.jar"
  if isfile(f"{TEST_NAME}-aotex.jar"):
    DALVIKVM_CLASSPATH = f"{DALVIKVM_CLASSPATH}:{DEX_LOCATION}/{TEST_NAME}-aotex.jar"
  DALVIKVM_CLASSPATH = f"{DALVIKVM_CLASSPATH}{SECONDARY_DEX}"

  # We set DumpNativeStackOnSigQuit to false to avoid stressing libunwind.
  # b/27185632
  # b/24664297

  dalvikvm_cmdline = f"{INVOKE_WITH} {GDB} {ANDROID_ART_BIN_DIR}/{DALVIKVM} \
                       {GDB_ARGS} \
                       {FLAGS} \
                       {DEX_VERIFY} \
                       -XXlib:{LIB} \
                       {DEX2OAT} \
                       {DALVIKVM_ISA_FEATURES_ARGS} \
                       {ZYGOTE} \
                       {JNI_OPTS} \
                       {INT_OPTS} \
                       {DEBUGGER_OPTS} \
                       {QUOTED_DALVIKVM_BOOT_OPT} \
                       {TMP_DIR_OPTION} \
                       -XX:DumpNativeStackOnSigQuit:false \
                       -cp {DALVIKVM_CLASSPATH} {MAIN} {ARGS}"

  if SIMPLEPERF:
    dalvikvm_cmdline = f"simpleperf record {dalvikvm_cmdline} && simpleperf report"

  def sanitize_dex2oat_cmdline(cmdline: str) -> str:
    args = []
    for arg in cmdline.split(" "):
      if arg == "--class-loader-context=&":
        arg = "--class-loader-context=\&"
      args.append(arg)
    return " ".join(args)

  # Remove whitespace.
  dex2oat_cmdline = sanitize_dex2oat_cmdline(dex2oat_cmdline)
  dalvikvm_cmdline = re.sub(" +", " ", dalvikvm_cmdline)
  dm_cmdline = re.sub(" +", " ", dm_cmdline)
  vdex_cmdline = sanitize_dex2oat_cmdline(vdex_cmdline)
  profman_cmdline = re.sub(" +", " ", profman_cmdline)

  # Use an empty ASAN_OPTIONS to enable defaults.
  # Note: this is required as envsetup right now exports detect_leaks=0.
  RUN_TEST_ASAN_OPTIONS = ""

  # Multiple shutdown leaks. b/38341789
  if RUN_TEST_ASAN_OPTIONS != "":
    RUN_TEST_ASAN_OPTIONS = f"{RUN_TEST_ASAN_OPTIONS}:"
  RUN_TEST_ASAN_OPTIONS = f"{RUN_TEST_ASAN_OPTIONS}detect_leaks=0"

  assert not args.external_log_tags, "Deprecated: use --android-log-tags=*:v"

  ANDROID_LOG_TAGS = args.android_log_tags

  if not HOST:
    adb.root()
    adb.wait_for_device()
    adb.shell(f"rm -rf {CHROOT_DEX_LOCATION} && mkdir -p {CHROOT_DEX_LOCATION}")
    adb.push(f"{TEST_NAME}*.jar", CHROOT_DEX_LOCATION)
    if PROFILE or RANDOM_PROFILE:
      adb.push("profile", CHROOT_DEX_LOCATION, check=False)
    # Copy resource folder
    if isdir("res"):
      adb.push("res", CHROOT_DEX_LOCATION)

    # Populate LD_LIBRARY_PATH.
    LD_LIBRARY_PATH = ""
    if ANDROID_ROOT != "/system":
      # Current default installation is dalvikvm 64bits and dex2oat 32bits,
      # so we can only use LD_LIBRARY_PATH when testing on a local
      # installation.
      LD_LIBRARY_PATH = f"{ANDROID_ROOT}/{LIBRARY_DIRECTORY}"

    # This adds libarttest(d).so to the default linker namespace when dalvikvm
    # is run from /apex/com.android.art/bin. Since that namespace is essentially
    # an alias for the com_android_art namespace, that gives libarttest(d).so
    # full access to the internal ART libraries.
    LD_LIBRARY_PATH = f"/data/{TEST_DIRECTORY}/com.android.art/lib{SUFFIX64}:{LD_LIBRARY_PATH}"
    dlib = ("" if TEST_IS_NDEBUG else "d")
    art_test_internal_libraries = [
        f"libartagent{dlib}.so",
        f"libarttest{dlib}.so",
        f"libtiagent{dlib}.so",
        f"libtistress{dlib}.so",
    ]
    NATIVELOADER_DEFAULT_NAMESPACE_LIBS = ":".join(art_test_internal_libraries)
    dlib = ""
    art_test_internal_libraries = []

    # Needed to access the test's Odex files.
    LD_LIBRARY_PATH = f"{DEX_LOCATION}/oat/{ISA}:{LD_LIBRARY_PATH}"
    # Needed to access the test's native libraries (see e.g. 674-hiddenapi,
    # which generates `libhiddenapitest_*.so` libraries in `{DEX_LOCATION}`).
    LD_LIBRARY_PATH = f"{DEX_LOCATION}:{LD_LIBRARY_PATH}"

    # Prepend directories to the path on device.
    PREPEND_TARGET_PATH = ANDROID_ART_BIN_DIR
    if ANDROID_ROOT != "/system":
      PREPEND_TARGET_PATH = f"{PREPEND_TARGET_PATH}:{ANDROID_ROOT}/bin"

    timeout_dumper_cmd = ""

    # Check whether signal_dumper is available.
    if TIMEOUT_DUMPER == "signal_dumper":
      # Chroot? Use as prefix for tests.
      TIMEOUT_DUMPER_PATH_PREFIX = ""
      if CHROOT:
        TIMEOUT_DUMPER_PATH_PREFIX = f"{CHROOT}/"

      # Testing APEX?
      if adb.shell(
          f"test -x {TIMEOUT_DUMPER_PATH_PREFIX}/apex/com.android.art/bin/signal_dumper",
          check=False,
          save_cmd=False).returncode:
        TIMEOUT_DUMPER = "/apex/com.android.art/bin/signal_dumper"
      # Is it in /system/bin?
      elif adb.shell(
          f"test -x {TIMEOUT_DUMPER_PATH_PREFIX}/system/bin/signal_dumper",
          check=False,
          save_cmd=False).returncode:
        TIMEOUT_DUMPER = "/system/bin/signal_dumper"
      else:
        TIMEOUT_DUMPER = ""
    else:
      TIMEOUT_DUMPER = ""

    if TIMEOUT_DUMPER:
      # Use "-l" to dump to logcat. That is convenience for the build bot crash symbolization.
      # Use exit code 124 for toybox timeout (b/141007616).
      timeout_dumper_cmd = f"{TIMEOUT_DUMPER} -l -s 15 -e 124"

    timeout_prefix = ""
    if TIME_OUT == "timeout":
      # Add timeout command if time out is desired.
      #
      # Note: We first send SIGTERM (the timeout default, signal 15) to the signal dumper, which
      #       will induce a full thread dump before killing the process. To ensure any issues in
      #       dumping do not lead to a deadlock, we also use the "-k" option to definitely kill the
      #       child.
      # Note: Using "--foreground" to not propagate the signal to children, i.e., the runtime.
      timeout_prefix = f"timeout --foreground -k 120s {TIME_OUT_VALUE}s {timeout_dumper_cmd} {cmdline}"

    env = {
      "ASAN_OPTIONS": RUN_TEST_ASAN_OPTIONS,
      "ANDROID_DATA": DEX_LOCATION,
      "DEX_LOCATION": DEX_LOCATION,
      "ANDROID_ROOT": ANDROID_ROOT,
      "ANDROID_I18N_ROOT": ANDROID_I18N_ROOT,
      "ANDROID_ART_ROOT": ANDROID_ART_ROOT,
      "ANDROID_TZDATA_ROOT": ANDROID_TZDATA_ROOT,
      "ANDROID_LOG_TAGS": ANDROID_LOG_TAGS,
      "LD_LIBRARY_PATH": LD_LIBRARY_PATH,
      "NATIVELOADER_DEFAULT_NAMESPACE_LIBS": NATIVELOADER_DEFAULT_NAMESPACE_LIBS,
      "PATH": f"{PREPEND_TARGET_PATH}:$PATH",
    }  # pyformat: disable

    def run_cmd(cmdline: str, env={}, **kwargs) -> subprocess.CompletedProcess:
      if cmdline == "true" or DRY_RUN:
        return run('true')  # Noop command which just executes the linux 'true' binary.
      cmdline = (f"cd {DEX_LOCATION} && " +
                 "".join(f"export {k}={v} && " for k, v in env.items()) +
                 cmdline)
      # Create a script with the command. The command can get longer than the longest
      # allowed adb command and there is no way to get the exit status from a adb shell command.
      with NamedTemporaryFile(mode="w") as cmdfile:
        cmdfile.write("echo '$$ {}'\n".format(cmdline.replace("'", r"'\''")))
        cmdfile.write(cmdline)
        cmdfile.flush()
        adb.push(
            cmdfile.name, f"{CHROOT_DEX_LOCATION}/cmdline.sh", save_cmd=False)
      chroot_prefix = f"chroot {CHROOT}" if CHROOT else ""
      return adb.shell(f"{chroot_prefix} sh {DEX_LOCATION}/cmdline.sh", **kwargs)

    if USE_GDB or USE_GDBSERVER:
      print(f"Forward {GDBSERVER_PORT} to local port and connect GDB")

    run_cmd(f"rm -rf {DEX_LOCATION}/dalvik-cache/ && mkdir -p {mkdir_locations}")
    # Restore stdout/stderr from previous run (the directory might have been cleared).
    adb.push(args.stdout_file, f"{CHROOT}{DEX_LOCATION}/{basename(args.stdout_file)}")
    adb.push(args.stderr_file, f"{CHROOT}{DEX_LOCATION}/{basename(args.stderr_file)}")
    run_cmd(f"{profman_cmdline}", env)
    run_cmd(f"{dex2oat_cmdline}", env)
    run_cmd(f"{dm_cmdline}", env)
    run_cmd(f"{vdex_cmdline}", env)
    run_cmd(f"{strip_cmdline}")
    run_cmd(f"{sync_cmdline}")
    run_cmd(tee(f"{timeout_prefix} {dalvikvm_cmdline}"),
            env,
            expected_exit_code=args.expected_exit_code)
    # Copy the on-device stdout/stderr to host.
    adb.pull(f"{CHROOT}{DEX_LOCATION}/{basename(args.stdout_file)}", args.stdout_file)
    adb.pull(f"{CHROOT}{DEX_LOCATION}/{basename(args.stderr_file)}", args.stderr_file)
  else:
    # Host run.
    if USE_ZIPAPEX or USE_EXRACTED_ZIPAPEX:
      # Put the zipapex files in front of the ld-library-path
      LD_LIBRARY_PATH = f"{ANDROID_DATA}/zipapex/{LIBRARY_DIRECTORY}:{ANDROID_ROOT}/{TEST_DIRECTORY}"
    else:
      LD_LIBRARY_PATH = f"{ANDROID_ROOT}/{LIBRARY_DIRECTORY}:{ANDROID_ROOT}/{TEST_DIRECTORY}"

    env = {
        "ANDROID_PRINTF_LOG": "brief",
        "ASAN_OPTIONS": RUN_TEST_ASAN_OPTIONS,
        "ANDROID_DATA": DEX_LOCATION,
        "DEX_LOCATION": DEX_LOCATION,
        "ANDROID_ROOT": ANDROID_ROOT,
        "ANDROID_I18N_ROOT": ANDROID_I18N_ROOT,
        "ANDROID_ART_ROOT": ANDROID_ART_ROOT,
        "ANDROID_TZDATA_ROOT": ANDROID_TZDATA_ROOT,
        "ANDROID_LOG_TAGS": ANDROID_LOG_TAGS,
        "LD_LIBRARY_PATH": LD_LIBRARY_PATH,
        "PATH": f"{PATH}:{ANDROID_ART_BIN_DIR}",
        # Temporarily disable address space layout randomization (ASLR).
        # This is needed on the host so that the linker loads core.oat at the necessary address.
        "LD_USE_LOAD_BIAS": "1",
    }

    cmdline = dalvikvm_cmdline

    if TIME_OUT == "gdb":
      if run("uname").stdout.strip() == "Darwin":
        # Fall back to timeout on Mac.
        TIME_OUT = "timeout"
      elif ISA == "x86":
        # prctl call may fail in 32-bit on an older (3.2) 64-bit Linux kernel. Fall back to timeout.
        TIME_OUT = "timeout"
      else:
        # Check if gdb is available.
        proc = run('gdb --eval-command="quit"', check=False, save_cmd=False)
        if proc.returncode != 0:
          # gdb isn't available. Fall back to timeout.
          TIME_OUT = "timeout"

    if TIME_OUT == "timeout":
      # Add timeout command if time out is desired.
      #
      # Note: We first send SIGTERM (the timeout default, signal 15) to the signal dumper, which
      #       will induce a full thread dump before killing the process. To ensure any issues in
      #       dumping do not lead to a deadlock, we also use the "-k" option to definitely kill the
      #       child.
      # Note: Using "--foreground" to not propagate the signal to children, i.e., the runtime.
      cmdline = f"timeout --foreground -k 120s {TIME_OUT_VALUE}s {TIMEOUT_DUMPER} -s 15 {cmdline}"

    os.chdir(ANDROID_BUILD_TOP)

    # Make sure we delete any existing compiler artifacts.
    # This enables tests to call the RUN script multiple times in a row
    # without worrying about interference.
    shutil.rmtree(f"{DEX_LOCATION}/oat", ignore_errors=True)
    shutil.rmtree(f"{DEX_LOCATION}/dalvik-cache/", ignore_errors=True)

    run(f"mkdir -p {mkdir_locations}", save_cmd=False)
    run(setupapex_cmdline)
    if run(installapex_test_cmdline, check=False).returncode != 0:
      run(installapex_cmdline)
    run(linkroot_cmdline)
    run(linkroot_overlay_cmdline)
    run(profman_cmdline, env)
    run(dex2oat_cmdline, env)
    run(dm_cmdline, env)
    run(vdex_cmdline, env)
    run(strip_cmdline)
    run(sync_cmdline)

    if CREATE_RUNNER:
      with open(f"{DEX_LOCATION}/runit.sh", "w") as f:
        f.write("#!/bin/bash")
        for var in ("ANDROID_PRINTF_LOG ANDROID_DATA ANDROID_ROOT "
                    "ANDROID_I18N_ROOT ANDROID_TZDATA_ROOT ANDROID_ART_ROOT "
                    "LD_LIBRARY_PATH DYLD_LIBRARY_PATH PATH LD_USE_LOAD_BIAS"
                   ).split(" "):
          value = os.environ.get(var, "")
          f.write(f'export {var}="{value}"')
        f.write(cmdline)
      os.chmod("{DEX_LOCATION}/runit.sh", 0o777)
      print(f"Runnable test script written to {DEX_LOCATION}/runit.sh")
    if DRY_RUN:
      return

    if USE_GDB:
      # When running under gdb, we cannot do piping and grepping...
      env["TERM"] = os.environ.get("TERM", "")
      subprocess.run(cmdline, env=env, shell=True)
    elif USE_GDBSERVER:
      print(f"Connect to {GDBSERVER_PORT}")
      # When running under gdb, we cannot do piping and grepping...
      subprocess.run(cmdline, env=env, shell=True)
    else:
      if TIME_OUT != "gdb":
        run(tee(cmdline),
            env,
            expected_exit_code=args.expected_exit_code)

        # Remove unwanted log messages from stderr before diffing with the expected output.
        # NB: The unwanted log line can be interleaved in the middle of wanted stderr printf.
        #     In particular, unhandled exception is printed using several unterminated printfs.
        ALL_LOG_TAGS = ["V", "D", "I", "W", "E", "F", "S"]
        skip_tag_set = "|".join(ALL_LOG_TAGS[:ALL_LOG_TAGS.index(args.diff_min_log_tag.upper())])
        skip_reg_exp = fr'[[:alnum:]]+ ({skip_tag_set}) #-# #:#:# [^\n]*\n'.replace('#', '[0-9]+')
        run(fr"sed -i -z -E 's/{skip_reg_exp}//g' '{args.stderr_file}'")
        if not HAVE_IMAGE:
          message = "(Unable to open file|Could not create image space)"
          run(fr"sed -i -E '/^dalvikvm(|32|64) E .* {message}/d' '{args.stderr_file}'")
        if ANDROID_LOG_TAGS != "*:i" and "D" in skip_tag_set:
          run(fr"sed -i -E '/^(Time zone|I18n) APEX ICU file found/d' '{args.stderr_file}'")
      else:
        # With a thread dump that uses gdb if a timeout.
        proc = run(cmdline, check=False)
        # TODO: Spawn a watcher process.
        raise Exception("Not implemented")
        # ( sleep {TIME_OUT_VALUE} && \
        #   echo "##### Thread dump using gdb on test timeout" && \
        #   ( gdb -q -p {pid} --eval-command="info thread" --eval-command="thread apply all bt" \
        #                    --eval-command="call exit(124)" --eval-command=quit || \
        #     kill {pid} )) 2> /dev/null & watcher=$!
        test_exit_status = proc.returncode
        # pkill -P {watcher} 2> /dev/null # kill the sleep which will in turn end the watcher as well
        if proc.returncode == 124 and TIME_OUT == "timeout":
          print("\e[91mTEST TIMED OUT!\e[0m", file=sys.stderr)
        assert proc.returncode == args.expected_exit_code, f"exit code: {proc.returncode}"