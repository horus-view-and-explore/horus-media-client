"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='horus-media-client',

    version='0.5.1',

    description='Horus Media Server Client',

    long_description=long_description,

    long_description_content_type='text/markdown',

    url='https://github.com/horus-view-and-explore/horus-media-client',

    author_email="info@horus.nu",

    author='Horus View and Explore B.V.',

    license='MIT',

    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],

    packages=find_packages(where='.'),

    python_requires='>=3.6, <4',

    install_requires=[
        "psycopg2>=2.8.4",
        "numpy>=1.17.4",
        "pymap3d>=2.1.0",
        "pillow>=6.2.1",
        "scipy>=1.3.3",
    ],

    extras_require={
        'dev': [],
        'test': [],
    },
)
