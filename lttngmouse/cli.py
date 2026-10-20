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

from typing import Annotated
import rich.console
import rich.table
import lttngmouse
import rich.box
import logging
import asyncio
import sys
import typer
import enum


class _LogLevel(str, enum.Enum):
    NOTSET = 'N'
    DEBUG = 'D'
    INFO = 'I'
    WARNING = 'W'
    ERROR = 'E'
    CRITICAL = 'C'


def _cfg_logging(log_level: _LogLevel):
    level = {
        _LogLevel.NOTSET: logging.NOTSET,
        _LogLevel.DEBUG: logging.DEBUG,
        _LogLevel.INFO: logging.INFO,
        _LogLevel.WARNING: logging.WARNING,
        _LogLevel.ERROR: logging.ERROR,
        _LogLevel.CRITICAL: logging.CRITICAL,
    }[log_level]

    logging.basicConfig(level=level,
                        format='%(asctime)s [%(name)s] %(levelname).1s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')


def _table_from_distros(distros: lttngmouse.Distros):
    table = rich.table.Table(box=rich.box.ROUNDED)

    for header in ('Dist. name', 'Dist. version no.', 'Dist. version name', 'Package name',
                   'Package version'):
        # Wrap long values instead of truncating them in a narrow terminal
        table.add_column(header, overflow='fold')

    all_distros = [
        distros.ubuntu,
        distros.ubuntu_ppa,
        distros.debian,
        distros.fedora,
        distros.opensuse,
        distros.arch,
        distros.alpine,
        distros.buildroot,
        distros.yocto,
    ]

    for distro in all_distros:
        distro_name = distro.name

        if distro is distros.ubuntu_ppa:
            distro_name = 'Ubuntu'

        for dv in distro.versions:
            for pkg in dv.tools_pkg, dv.ust_pkg, dv.modules_pkg:
                if pkg is None:
                    continue

                table.add_row(distro_name,
                              dv.number_str if dv.number_str is not None else '',
                              dv.name if dv.name is not None else '',
                              pkg.name, str(pkg.version))

    return table


# Don't show local variables in tracebacks: they're noisy and may
# contain HTTP response contents.
_app = typer.Typer(pretty_exceptions_show_locals=False)


@_app.command(help='LTTng distribution package dynamic data')
def _main(log_level: Annotated[_LogLevel,
                               typer.Option('-l', '--log-level',
                                            help='Set the logging level.')] = _LogLevel.CRITICAL):
    _cfg_logging(log_level)
    table = _table_from_distros(asyncio.run(lttngmouse.distros()))
    console = rich.console.Console()

    # Without a terminal, Rich assumes 80 columns and would wrap the
    # table: use its natural width instead.
    if not console.is_terminal:
        options = console.options.update_width(sys.maxsize)
        console.width = console.measure(table, options=options).maximum

    console.print(table)


if __name__ == '__main__':
    _app()
