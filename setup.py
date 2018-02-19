# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from setuptools import find_packages, setup

setup(
    name='abot',
    version='0.0.1a',
    description='Slack bot creation library',
    long_description=open('README.rst').read(),
    url='https://github.com/Ridee/slackery',
    author='Javier Domingo Cansino',
    author_email='javier@jinnapp.com',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(),
    python_requires='>=3.6',
    include_package_data=True,
    zip_safe=False,
    keywords=['slack', 'bot'],
)
