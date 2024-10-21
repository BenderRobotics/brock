import os

from os.path import join, dirname, abspath
from setuptools import setup, find_packages


def read(rel_path):
    # type: (str) -> str
    here = abspath(dirname(__file__))
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with open(join(here, rel_path)) as fp:
        return fp.read()


def get_version(rel_path):
    # type: (str) -> str
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            # __version__ = "0.9"
            delimiter = '"' if '"' in line else "'"
            return line.split(delimiter)[1]
    raise RuntimeError('Unable to find version string.')


def package_files(directory):
    """ Loads recursively files in given directory """
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(join('..', path, filename))
    return paths


long_description = read('README.md')

setup(
    name='brock',
    version=get_version('src/brock/__init__.py'),
    description='Brock',
    long_description=long_description,
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Testers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    keywords='build docker toolchain',
    url='',
    project_urls={
        'Source': '',
    },
    author='Bender Robotics s.r.o.',
    author_email='hrbacek.r@benderrobotics.com',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    entry_points={
        'console_scripts': ['brock=brock.cli.main:main',],
    },
    python_requires='>=3.6',
    install_requires=[
        'markupsafe==2.0.1',
        'colorama>=0.4.1',
        'click',
        'hiyapyco',
        'schema',
        'munch',
        'fabric',
        'docker',
    ],
    zip_safe=False
)
