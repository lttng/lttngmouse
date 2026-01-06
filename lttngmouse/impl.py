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

import re
import bs4
import time
import typing
import aiohttp
import asyncio
import logging
import datetime
import lttngmouse.pub
import packaging.version
import concurrent.futures
from typing import Any, Callable


class _Pkg(lttngmouse.pub.Pkg):
    def __init__(self, name: str, version: packaging.version.Version):
        self._name = name
        self._version = version

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version


class _DistroVersion(lttngmouse.pub.DistroVersion):
    def __init__(self, number: packaging.version.Version | None, number_str: str | None,
                 name: str | None):
        self._number = number
        self._number_str = number_str
        self._name = name
        self._tools_pkg = None
        self._ust_pkg = None
        self._modules_pkg = None

    @property
    def number(self):
        return self._number

    @property
    def number_str(self):
        return self._number_str

    @property
    def name(self):
        return self._name

    @property
    def tools_pkg(self):
        return self._tools_pkg

    def _set_tools_pkg(self, pkg: lttngmouse.pub.Pkg):
        self._tools_pkg = pkg

    @property
    def ust_pkg(self):
        return self._ust_pkg

    def _set_ust_pkg(self, pkg: lttngmouse.pub.Pkg):
        self._ust_pkg = pkg

    @property
    def modules_pkg(self):
        return self._modules_pkg

    def _set_modules_pkg(self, pkg: lttngmouse.pub.Pkg):
        self._modules_pkg = pkg


class _Distro(lttngmouse.pub.Distro):
    def __init__(self, name: str, versions: list[lttngmouse.pub.DistroVersion]):
        self._name = name
        self._versions = versions

    @property
    def name(self):
        return self._name

    @property
    def versions(self):
        return self._versions


class _Distros(lttngmouse.pub.Distros):
    def __init__(self,
                 ubuntu: lttngmouse.pub.Distro,
                 ubuntu_ppa: lttngmouse.pub.Distro,
                 debian: lttngmouse.pub.Distro,
                 fedora: lttngmouse.pub.Distro,
                 opensuse: lttngmouse.pub.Distro,
                 arch: lttngmouse.pub.Distro,
                 alpine: lttngmouse.pub.Distro,
                 buildroot: lttngmouse.pub.Distro,
                 yocto: lttngmouse.pub.Distro):
        self._ubuntu = ubuntu
        self._ubuntu_ppa = ubuntu_ppa
        self._debian = debian
        self._fedora = fedora
        self._opensuse = opensuse
        self._arch = arch
        self._alpine = alpine
        self._buildroot = buildroot
        self._yocto = yocto

    @property
    def ubuntu(self):
        return self._ubuntu

    @property
    def ubuntu_ppa(self):
        return self._ubuntu_ppa

    @property
    def debian(self):
        return self._debian

    @property
    def fedora(self):
        return self._fedora

    @property
    def opensuse(self):
        return self._opensuse

    @property
    def arch(self):
        return self._arch

    @property
    def alpine(self):
        return self._alpine

    @property
    def buildroot(self):
        return self._buildroot

    @property
    def yocto(self):
        return self._yocto


class _DistrosBuilder:
    def __init__(self):
        self._logger = logging.getLogger('lttngmouse')
        self._req_count = 0

    def _session_get(self, session: aiohttp.ClientSession, url: str):
        self._logger.debug(f'HTTP GET `{url}`')
        self._req_count += 1
        return session.get(url)

    async def _text_from_url(self, session, url):
        async with self._session_get(session, url) as resp:
            text = await resp.text()
            status = resp.status

            if status != 200 and status != 404:
                raise RuntimeError(f'Unexpected HTTP status {status} for `{url}`')

        self._logger.debug(f'Retrieved `{url}` (status {status})')
        return text, status

    async def _soup_from_url(self, session, url):
        text, status = await self._text_from_url(session, url)
        return bs4.BeautifulSoup(text, 'html.parser'), status

    @staticmethod
    def _distro_version_sort_key(distro_version: lttngmouse.pub.DistroVersion):
        return (
            distro_version.number is None,
            distro_version.number if distro_version.number is not None else distro_version.name
        )

    @staticmethod
    def _sorted_distro_versions(distro_versions: list[lttngmouse.pub.DistroVersion]):
        return sorted(distro_versions, key=_DistrosBuilder._distro_version_sort_key)

    @staticmethod
    def _distro_from_repology_repos(name: str, repology_repos: Any,
                                    repo_distro_version_func: Callable[[Any],
                                                                       tuple[str | None,
                                                                             str | None] | None]):
        distro_versions = []

        for repo in repology_repos:
            repo_distro_version = repo_distro_version_func(repo)

            if repo_distro_version is None:
                continue

            distro_version = None

            for dv in distro_versions:
                if (dv.number_str, dv.name) == repo_distro_version:
                    assert type(dv) is _DistroVersion
                    distro_version = dv
                    break

            if distro_version is None:
                ver_number = None

                if repo_distro_version[0] is not None:
                    ver_number = packaging.version.parse(repo_distro_version[0])

                distro_version = _DistroVersion(ver_number,
                                                repo_distro_version[0],
                                                repo_distro_version[1])
                distro_versions.append(distro_version)

            pkg = _Pkg(repo['visiblename'], packaging.version.parse(repo['version']))

            if pkg.name in ('lttng-tools', 'ltt-control'):
                distro_version._set_tools_pkg(pkg)
            elif 'ust' in pkg.name and 'python' not in pkg.name:
                distro_version._set_ust_pkg(pkg)
            elif 'modules' in pkg.name:
                distro_version._set_modules_pkg(pkg)

        return _Distro(name, _DistrosBuilder._sorted_distro_versions(distro_versions))

    async def _ubuntu_name_map(self):
        self._logger.info('Retrieving Ubuntu release names')

        async with aiohttp.ClientSession() as session:
            soup, _ = await self._soup_from_url(session, 'https://releases.ubuntu.com/releases/')

        name_map = {}

        for m in re.findall(r'Ubuntu (\d+\.\d+)(?:\.\d+)?.*?\((.+?)\)',
                            soup.select('.p-table-wrapper pre')[0].get_text(strip=True)):
            name_map[m[0]] = m[1]

        return name_map

    async def _ubuntu_distro(self, repology_repos: Any):
        def repo_distro_version(repo: Any):
            m = re.match(r'ubuntu_(\d+)_(\d+)', repo['repo'])

            if m:
                ver = f'{m.group(1)}.{m.group(2)}'
                return ver, name_map[ver] if ver in name_map else ""

        name_map = await self._ubuntu_name_map()
        return self._distro_from_repology_repos('Ubuntu', repology_repos, repo_distro_version)

    @staticmethod
    def _pkg_from_ppa_page_td_el(name: str, td_elem: bs4.Tag):
        m = re.match(r'\d+\.\d+\.\d+', td_elem.get_text(strip=True))
        assert m is not None
        return _Pkg(name, packaging.version.parse(m.group(0)))

    async def _distro_version_from_ubuntu_ppa_page(self, session: aiohttp.ClientSession,
                                                   ppa_url: str) -> lttngmouse.pub.DistroVersion:
        self._logger.info(f'Retrieving PPA page `{ppa_url}`')
        soup, _ = await self._soup_from_url(session, ppa_url)
        distro_version = _DistroVersion(None, None,
                                        '{} PPA'.format(soup.select('meta[itemprop="name"]')[0]['content']))

        for tr_el in soup.select('#packages_list tbody tr'):
            td_els = tr_el.select('td')

            if 'ltt-control' in td_els[0].get_text() and distro_version.tools_pkg is None:
                distro_version._set_tools_pkg(self._pkg_from_ppa_page_td_el('ltt-control',
                                                                            td_els[1]))

            if 'ust' in td_els[0].get_text() and distro_version.ust_pkg is None:
                distro_version._set_ust_pkg(self._pkg_from_ppa_page_td_el('ust', td_els[1]))

            if 'lttng-modules' in td_els[0].get_text() and distro_version.modules_pkg is None:
                distro_version._set_modules_pkg(self._pkg_from_ppa_page_td_el('lttng-modules',
                                                                              td_els[1]))

        return distro_version

    async def _ubuntu_ppa_distro(self):
        async with aiohttp.ClientSession() as session:
            self._logger.info("Retrieving Launchpad's `~lttng` user page")
            soup, _ = await self._soup_from_url(session, 'https://launchpad.net/~lttng')
            urls = []

            for a_el in soup.find_all('a'):
                url = str(typing.cast(bs4.Tag, a_el)['href'])

                if '/ubuntu/stable-2.' in url:
                    urls.append(f'https://launchpad.net{url}')

            distro_versions = await asyncio.gather(
                *[self._distro_version_from_ubuntu_ppa_page(session, url) for url in urls]
            )

        return _Distro('Ubuntu LTTng Stable PPA',
                       _DistrosBuilder._sorted_distro_versions(distro_versions))

    async def _debian_distro(self, repology_repos: Any):
        def repo_distro_version(repo: Any):
            if 'debian_unstable' in repo['repo']:
                return None, 'sid'

            m_ver = re.match(r'debian_(\d+)', repo['repo'])

            if m_ver:
                if 'subrepo' in repo:
                    m_name = re.match(r'([^/]+)', repo['subrepo'])

                    if m_name:
                        return m_ver.group(1), m_name.group(1)

        return self._distro_from_repology_repos('Debian', repology_repos, repo_distro_version)

    async def _fedora_distro(self, repology_repos: Any):
        def repo_distro_version(repo: Any):
            if 'fedora_rawhide' in repo['repo']:
                return None, 'Rawhide'

            m = re.match(r'fedora_(\d+)', repo['repo'])

            if m:
                return m.group(1), None

        return self._distro_from_repology_repos('Fedora', repology_repos, repo_distro_version)

    async def _opensuse_distro(self, repology_repos: Any):
        def repo_distro_version(repo: Any):
            if 'opensuse_tumbleweed' in repo['repo']:
                return None, 'Tumbleweed'

            m = re.match(r'opensuse_leap_(\d+)_(\d+)', repo['repo'])

            if m:
                return f'{m.group(1)}.{m.group(2)}', 'Leap'

        return self._distro_from_repology_repos('openSUSE', repology_repos, repo_distro_version)

    async def _arch_distro(self, repology_repos: Any):
        def repo_distro_version(repo):
            if repo['repo'] == 'arch':
                return None, None

        return self._distro_from_repology_repos('Arch Linux', repology_repos, repo_distro_version)

    async def _alpine_distro(self, repology_repos: Any):
        def repo_distro_version(repo: Any):
            if 'alpine_edge' in repo['repo']:
                return None, 'Edge'
            m = re.match(r'alpine_(\d+)_(\d+)', repo['repo'])

            if m:
                return f'{m.group(1)}.{m.group(2)}', None

        return self._distro_from_repology_repos('Alpine Linux', repology_repos, repo_distro_version)

    async def _pkg_from_br_pkg_mk(self, session: aiohttp.ClientSession, br_version: str, name: str):
        self._logger.info(f'Retrieving package `{name}` for Buildroot {br_version}')
        text, status = await self._text_from_url(session,
                                                 f'https://git.buildroot.net/buildroot/plain/package/{name}/{name}.mk?h={br_version}.x')

        if status != 200 or 'Invalid branch' in text:
            self._logger.info(f'Invalid Buildroot version {br_version}')
            return

        m = re.search(r'^LTTNG_.+_VERSION\s+=\s+([^\s]+)', text, re.M)

        if m:
            return _Pkg(name, packaging.version.parse(m.group(1)))

    async def _distro_version_from_br_pkg_mks(self, session: aiohttp.ClientSession,
                                              br_version: str) -> lttngmouse.pub.DistroVersion | None:
        self._logger.info(f'Retrieving all LTTng packages for Buildroot {br_version}')

        tools_pkg, ust_pkg, modules_pkg = await asyncio.gather(
            self._pkg_from_br_pkg_mk(session, br_version, 'lttng-tools'),
            self._pkg_from_br_pkg_mk(session, br_version, 'lttng-libust'),
            self._pkg_from_br_pkg_mk(session, br_version, 'lttng-modules'),
        )

        if tools_pkg is None:
            self._logger.info(f'No LTTng packages for Buildroot {br_version}')
            return

        distro_version = _DistroVersion(packaging.version.parse(br_version), br_version, None)

        if tools_pkg is not None:
            distro_version._set_tools_pkg(tools_pkg)

        if ust_pkg is not None:
            distro_version._set_ust_pkg(ust_pkg)

        if modules_pkg is not None:
            distro_version._set_modules_pkg(modules_pkg)

        return distro_version

    async def _buildroot_distro(self):
        now = datetime.datetime.now()
        cur_yr = now.year
        cur_month = now.month
        yr = 2019
        month = 2
        distro_versions = []
        br_versions = []

        while (yr, month) <= (cur_yr, cur_month):
            br_versions.append(f'{yr}.{month:02}')
            month += 3

            if month > 11:
                yr += 1
                month = 2

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120),
                                         connector=aiohttp.TCPConnector(limit=16)) as session:
            coros = [self._distro_version_from_br_pkg_mks(session, br_v) for br_v in br_versions]
            distro_versions = [dv for dv in await asyncio.gather(*coros) if dv is not None]

        return _Distro('Buildroot', self._sorted_distro_versions(distro_versions))

    @staticmethod
    def _yocto_name_map_from_table(soup: bs4.BeautifulSoup, selector: str):
        tag = soup.select_one(selector)
        assert tag is not None
        name_map = {}

        for tr_el in tag.select('table tr'):
            td_els = tr_el.select('td')

            if len(td_els) == 0:
                continue

            name_map[td_els[0].get_text(strip=True)] = td_els[1].get_text(strip=True)

        return name_map

    async def _yocto_name_map(self, session: aiohttp.ClientSession):
        self._logger.info('Retrieving Yocto release names')
        soup, _ = await self._soup_from_url(session, 'https://www.yoctoproject.org/development/releases/')
        return (self._yocto_name_map_from_table(soup, '#current') |
                self._yocto_name_map_from_table(soup, '#previous'))

    async def _distro_version_from_yocto_gw(self, session: aiohttp.ClientSession, ver_name: str,
                                            ver_number: str) -> lttngmouse.pub.DistroVersion | None:
        self._logger.info(f'Retrieving Yocto GitWeb page for Yocto {ver_number} ({ver_name})')
        text, status = await self._text_from_url(session,
                                                 f'https://git.openembedded.org/openembedded-core/tree/meta/recipes-kernel/lttng?h={ver_name.lower()}')

        if status != 200:
            self._logger.info(f'No LTTng packages for Yocto {ver_number} ({ver_name})')
            return

        distro_version = _DistroVersion(packaging.version.parse(ver_number), ver_number, ver_name)
        m = re.search(r'lttng-tools_(\d+\.\d+\.\d+)\.bb', text)

        if m:
            distro_version._set_tools_pkg(_Pkg('lttng-tools', packaging.version.parse(m.group(1))))
        else:
            self._logger.info(f'No LTTng packages for Yocto {ver_number} ({ver_name})')
            return

        m = re.search(r'lttng-ust_(\d+\.\d+\.\d+)\.bb', text)

        if m:
            distro_version._set_ust_pkg(_Pkg('lttng-ust', packaging.version.parse(m.group(1))))

        m = re.search(r'lttng-modules_(\d+\.\d+\.\d+)\.bb', text)

        if m:
            distro_version._set_modules_pkg(_Pkg('lttng-modules', packaging.version.parse(m.group(1))))

        return distro_version

    async def _yocto_distro(self):
        headers = {
            'User-Agent': 'lttngmouse/0.1.0 (+https://lttng.org/)',
        }

        async with aiohttp.ClientSession(headers=headers,
                                         connector=aiohttp.TCPConnector(limit_per_host=2)) as session:
            distro_versions = []

            for ver_name, ver_number in (await self._yocto_name_map(session)).items():
                await asyncio.sleep(.25)
                distro_version = await self._distro_version_from_yocto_gw(session, ver_name,
                                                                          ver_number)

                if distro_version is not None:
                    distro_versions.append(distro_version)

        return _Distro('Yocto', self._sorted_distro_versions(distro_versions))

    async def _distros_from_repology_repos(self):
        self._logger.info('Retrieving Repology data')

        headers = {
            'User-Agent': 'lttngmouse/0.1.0 (+https://lttng.org/)',
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with self._session_get(session, 'https://repology.org/api/v1/projects/?search=ltt') as resp:
                json = await resp.json()

        repology_repos = json['lttng-tools'] + json['lttng-ust'] + json['lttng-modules']

        return await asyncio.gather(
            self._ubuntu_distro(repology_repos),
            self._debian_distro(repology_repos),
            self._fedora_distro(repology_repos),
            self._opensuse_distro(repology_repos),
            self._arch_distro(repology_repos),
            self._alpine_distro(repology_repos),
        )

    @property
    async def distros(self):
        (
            (
                ubuntu_distro,
                debian_distro,
                fedora_distro,
                opensuse_distro,
                arch_distro,
                alpine_distro,
            ),
            ubuntu_ppa_distro,
            buildroot_distro,
            yocto_distro
        ) = await asyncio.gather(
            self._distros_from_repology_repos(),
            self._ubuntu_ppa_distro(),
            self._buildroot_distro(),
            self._yocto_distro(),
        )

        self._logger.info(f'Made {self._req_count} HTTP requests')
        return _Distros(ubuntu=ubuntu_distro,
                        ubuntu_ppa=ubuntu_ppa_distro,
                        debian=debian_distro,
                        fedora=fedora_distro,
                        opensuse=opensuse_distro,
                        arch=arch_distro,
                        alpine=alpine_distro,
                        buildroot=buildroot_distro,
                        yocto=yocto_distro)


async def distros():
    return await _DistrosBuilder().distros
