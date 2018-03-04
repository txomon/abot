# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from setuptools import find_packages, setup

setup(
    name='abot',
    version='0.0.1a1',
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
