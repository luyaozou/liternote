#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='liternote',
      version='1.0.0',
      description='Simple Literature Note Editor',
      author='Luyao Zou',
      packages=find_packages('.'),
      entry_points={
        'gui_scripts': [
            'liternote = liternote:launch',
        ]},
      install_requires=[
            'PyQt5>=5.10',
        ],
      extras_require={
        ':python_version<"3.7"': ['importlib_resources'],
      },
      license='MIT',
)
