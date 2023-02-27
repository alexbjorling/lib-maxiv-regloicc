#!/usr/bin/env python
"""Python package setup."""
from setuptools import setup

setup(name="python-regloicclib",
      version="0.3.0",
      description=("Library for driving the Ismatec Reglo ICC peristaltic pump."
                   "Communication is done over direct RS232 or through a serial server."),
      author="Alexander Bjoerling",
      author_email="alexander.bjorling@maxiv.lu.se",
      license="GPLv3",
      url="http://www.maxiv.lu.se",
      packages=['regloicclib'],
      package_dir={'': 'src'},
      install_requires=[
          'pyserial',
      ],
      classifiers=[
          "Development Status :: 4 - Beta",
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          "Natural Language :: English",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Topic :: Scientific/Engineering :: Human Machine Interfaces",
          "Topic :: Scientific/Engineering :: Chemistry"
      ]
      )
