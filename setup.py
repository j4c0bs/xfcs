#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script for installing xfcs.

To install, run:

    python setup.py install

"""

# Modified from https://github.com/pypa/sampleproject/blob/master/setup.py

from setuptools import setup, find_packages
from codecs import open
from os import path
import sys

from xfcs.version import VERSION

if sys.argv[-1] == 'setup.py':
    print("To install xfcs, run 'python setup.py install'\n")

if sys.version_info[:3] < (3, 5):
    print('xfcs requires Python 3.5 or later ({}.{}.{} detected)'.format(*sys.version_info[:3]))
    sys.exit(-1)


here = path.abspath(path.dirname(__file__))


setup(
    name='xfcs',
    version=VERSION,
    description='Extract Flow Cytometry data from FCS files version 3+.',
    long_description=open('README.rst').read(),
    url='https://github.com/j4c0bs/xfcs',
    author='Jeremy Jacobs',
    author_email='pub@j4c0bs.net',
    license='BSD',
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Utilities'
    ],

    keywords='FCS FCS3.0 FCS3.1 flow cytometry',
    packages=find_packages(exclude=['docs']),
    python_requires='>3.5',
    install_requires=['numpy', 'pandas'],
    extras_require={},
    package_data={'':['LICENSE.txt', 'MANIFEST.in', 'docs/*']},
    data_files=[],
    entry_points={
        'console_scripts':[
            'xfcs=xfcs.commands:main'
        ],
    },
)
