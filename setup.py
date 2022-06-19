################################################################################
#
# Copyright 2022 Vincent Dary
#
# This file is part of ghidra-pipe.
#
# ghidra-pipe is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# setup.cfg is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# setup.cfg If not, see <https://www.gnu.org/licenses/>.
#
################################################################################

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ghidra_pipe",
    version="1.0.5",
    author="Vincent Dary",
    author_email="",
    description="ghidra-pipe: Teleport Python code from CPython to Jython",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vincentdary/ghidra-pipe",
    project_urls={
        "Bug Tracker": "https://github.com/vincentdary/ghidra-pipe/issues"
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.5.0",
    extras_require={
        "DEV": ["psutil", "pytest", "pytest-cov", "pytest-order"]
    },
    entry_points={
        'console_scripts': ['ghidra-pipe=scripts.ghidra_pipe:main']
    }
)
