# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

from glob import glob
from os.path import join, sep

from SCons.Defaults import processDefines

from platformio import util


def dump_includes(env):
    includes = []

    for item in env.get("CPPPATH", []):
        includes.append(env.subst(item))

    # installed libs
    for lb in env.GetLibBuilders():
        includes.extend(lb.get_inc_dirs())

    # includes from toolchains
    p = env.PioPlatform()
    for name in p.get_installed_packages():
        if p.get_package_type(name) != "toolchain":
            continue
        toolchain_dir = util.glob_escape(p.get_package_dir(name))
        toolchain_incglobs = [
            join(toolchain_dir, "*", "include*"),
            join(toolchain_dir, "lib", "gcc", "*", "*", "include*")
        ]
        for g in toolchain_incglobs:
            includes.extend(glob(g))

    return includes


def dump_defines(env):
    defines = []
    # global symbols
    for item in processDefines(env.get("CPPDEFINES", [])):
        defines.append(env.subst(item).replace('\\', ''))

    # special symbol for Atmel AVR MCU
    if env['PIOPLATFORM'] == "atmelavr":
        defines.append(
            "__AVR_%s__" % env.BoardConfig().get("build.mcu").upper()
            .replace("ATMEGA", "ATmega").replace("ATTINY", "ATtiny"))
    return defines


def dump_debug(env):

    def _fix_path_sep(path):
        result = []
        items = path if isinstance(path, list) else [path]
        for item in items:
            result.append(item.replace("/", sep).replace("\\", sep))
        return result if isinstance(path, list) else result[0]

    def _dump_server(configuration):
        if not configuration:
            return
        if not set(configuration.keys()) >= set(["package", "executable"]):
            return
        pkg_dir = env.PioPlatform().get_package_dir(configuration['package'])
        if not pkg_dir:
            return
        return {
            "cwd": pkg_dir,
            "executable": _fix_path_sep(configuration['executable']),
            "arguments": _fix_path_sep(configuration.get("arguments"))
        }

    gdbinit = None
    if "DEBUG_GDBINIT" in env:
        if isinstance(env['DEBUG_GDBINIT'], list):
            gdbinit = env['DEBUG_GDBINIT']
        else:
            gdbinit = [env['DEBUG_GDBINIT']]

    tool_settings = env.DebugToolSettings()
    if tool_settings and not gdbinit:
        gdbinit = tool_settings.get("gdbinit")

    env.AutodetectDebugPort()

    return {
        "gdb_path": util.where_is_program(
            env.subst("$GDB"), env.subst("${ENV['PATH']}")),
        "prog_path": env.subst("$PROG_PATH"),
        "tool": tool_settings['name'] if tool_settings else None,
        "gdbinit": [env.subst(cmd) for cmd in gdbinit] if gdbinit else None,
        "port": env.subst("$DEBUG_PORT"),
        "server": (_dump_server(tool_settings['server'])
                   if tool_settings and "server" in tool_settings else None)
    }


def DumpIDEData(env):
    LINTCCOM = "$CFLAGS $CCFLAGS $CPPFLAGS $_CPPDEFFLAGS"
    LINTCXXCOM = "$CXXFLAGS $CCFLAGS $CPPFLAGS $_CPPDEFFLAGS"

    data = {
        "libsource_dirs":
        [env.subst(l) for l in env.get("LIBSOURCE_DIRS", [])],
        "defines": dump_defines(env),
        "includes": dump_includes(env),
        "debug": dump_debug(env),
        "cc_flags": env.subst(LINTCCOM),
        "cxx_flags": env.subst(LINTCXXCOM),
        "cc_path": util.where_is_program(
            env.subst("$CC"), env.subst("${ENV['PATH']}")),
        "cxx_path": util.where_is_program(
            env.subst("$CXX"), env.subst("${ENV['PATH']}")),
    }

    env_ = env.Clone()
    # https://github.com/platformio/platformio-atom-ide/issues/34
    _new_defines = []
    for item in processDefines(env_.get("CPPDEFINES", [])):
        item = item.replace('\\"', '"')
        if " " in item:
            _new_defines.append(item.replace(" ", "\\\\ "))
        else:
            _new_defines.append(item)
    env_.Replace(CPPDEFINES=_new_defines)

    data.update({
        "cc_flags": env_.subst(LINTCCOM),
        "cxx_flags": env_.subst(LINTCXXCOM)
    })

    return data


def exists(_):
    return True


def generate(env):
    env.AddMethod(DumpIDEData)
    return env
