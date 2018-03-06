# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import subprocess

from setuptools import find_packages, setup

import abot


def git_remote_tags():
    tags = subprocess.check_output('git ls-remote git://github.com/txomon/abot --tags v*'.split()).decode()
    valid_tags = {}
    for tag in tags.splitlines():
        # 8626062a1526fdf239fd52d35d91cf7896729e8f        refs/tags/test^{}
        if tag.endswith('^{}'):
            splits = [p for p in tag.split() if p]
            commit, tagname = splits
            tagname = tagname[len('refs/tags/'):-len('^{}')]
            valid_tags[commit] = tagname

    return valid_tags


def git_remote_commits():
    subprocess.check_output('git fetch git://github.com/txomon/abot master:refs/reference'.split()).decode()
    git_log = subprocess.check_output('git log --format=%H refs/reference'.split()).decode()
    return git_log.splitlines()


def git_get_closest_commit(valid_tags, remote_commits):
    git_log = subprocess.check_output('git log --format=%H'.split()).decode()
    common_commit = None
    common_to_current = None
    current_commit = None
    for number, commit in enumerate(git_log.splitlines()):
        if not current_commit:
            current_commit = commit
        if not common_commit and commit in remote_commits:
            common_commit = commit
            common_to_current = number
        if commit in valid_tags:
            return {
                'tag': valid_tags[commit],
                'tag_to_current': number,
                'commit': current_commit,
                'common_commit': common_commit,
                'common_to_current': common_to_current,
            }


def get_version():
    # Badass revision v1.2.9a1.dev40+20.ab31d12b-dirty
    #                 ********######@@@@@@@@@@@@++++++
    #          ----------/  ----/        /         \---
    #         /            /            /              \
    # {version_string}{dev_string}{local_string}{status_string}
    try:
        dev_string = local_string = status_string = ''
        # Get dirtiness
        valid_tags = git_remote_tags()
        remote_commits = git_remote_commits()
        info = git_get_closest_commit(valid_tags, remote_commits)
        if not info:  # If there is no match, just go to offline mode
            raise Exception()

        # First, public release string (v1.2.12a3) AKA version_string
        version_string = info["tag"]
        code_version = f'v{abot.__version__}'
        if version_string != code_version:
            raise TypeError(f'ABot version in abot/__init__.py needs to be updated to {version_string}')

        common_to_current = info['common_to_current']
        if common_to_current is None:
            raise TypeError(f'This repo and upstream are messy, no common commits. Report this situation!')

        tag_to_current = info['tag_to_current']
        if common_to_current > tag_to_current:
            raise TypeError(f'This is an impossible situation, no tag can exist in uncommon path')
        tag_to_common = tag_to_current - common_to_current

        # Second, official non-public dev release string (.dev30) AKA dev_string
        if tag_to_common != 0:
            dev_string = f'.dev{tag_to_common}'

        # Third, non-official non-public user release number (+29-ab38ecd99)
        if common_to_current:
            local_string = f'+{common_to_current}.{info["commit"][:8]}'

        # Fourth, dirtiness flag
        is_dirty = bool(subprocess.check_output('git status -s'.split()).decode())
        if is_dirty:
            status_string = '.dirty'

        return f'{version_string}{dev_string}{local_string}{status_string}'
    except TypeError:
        raise
    except Exception:
        version = abot.__version__
        return f'v{version}+unknown'


setup(
    name='abot',
    version=get_version(),
    description='Bot creation library',
    long_description=open('README.rst').read(),
    url='https://github.com/txomon/abot',
    author='Javier Domingo Cansino',
    author_email='javierdo1@gmail.com',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(exclude=['tests']),
    license='MIT',
    python_requires='>=3.6',
    include_package_data=True,
    zip_safe=False,
    keywords=['slack', 'dubtrack', 'bot', 'async', 'asyncio'],
)
