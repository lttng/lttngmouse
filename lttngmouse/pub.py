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

from abc import ABC, abstractmethod
import packaging.version


class Pkg(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def version(self) -> packaging.version.Version:
        ...


class DistroVersion(ABC):
    @property
    @abstractmethod
    def number(self) -> packaging.version.Version | None:
        ...

    @property
    @abstractmethod
    def number_str(self) -> str | None:
        ...

    @property
    @abstractmethod
    def name(self) -> str | None:
        ...

    @property
    @abstractmethod
    def tools_pkg(self) -> Pkg | None:
        ...

    @property
    @abstractmethod
    def ust_pkg(self) -> Pkg | None:
        ...

    @property
    @abstractmethod
    def modules_pkg(self) -> Pkg | None:
        ...


class Distro(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def versions(self) -> list[DistroVersion]:
        ...


class Distros(ABC):
    @property
    @abstractmethod
    def ubuntu(self) -> Distro:
        ...

    @property
    @abstractmethod
    def ubuntu_ppa(self) -> Distro:
        ...

    @property
    @abstractmethod
    def debian(self) -> Distro:
        ...

    @property
    @abstractmethod
    def fedora(self) -> Distro:
        ...

    @property
    @abstractmethod
    def opensuse(self) -> Distro:
        ...

    @property
    @abstractmethod
    def arch(self) -> Distro:
        ...

    @property
    @abstractmethod
    def alpine(self) -> Distro:
        ...

    @property
    @abstractmethod
    def buildroot(self) -> Distro:
        ...

    @property
    @abstractmethod
    def yocto(self) -> Distro:
        ...
