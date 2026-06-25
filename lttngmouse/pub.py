# Copyright (c) 2021-2025 Philippe Proulx <eeppeliteloop@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from typing import Protocol
import packaging.version


class Pkg(Protocol):
    name: str
    version: packaging.version.Version


class DistroVersion(Protocol):
    number: packaging.version.Version | None
    number_str: str | None
    name: str | None
    tools_pkg: Pkg | None
    ust_pkg: Pkg | None
    modules_pkg: Pkg | None


class Distro(Protocol):
    name: str
    versions: list[DistroVersion]


class Distros(Protocol):
    ubuntu: Distro
    ubuntu_ppa: Distro
    debian: Distro
    fedora: Distro
    opensuse: Distro
    arch: Distro
    alpine: Distro
    buildroot: Distro
    yocto: Distro
