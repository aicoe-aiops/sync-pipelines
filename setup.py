"""Solgate package setup."""

import os
import sys
from distutils.core import setup
from setuptools import find_packages
from pathlib import Path

sys.path[0:0] = ["solgate"]
from version import __version__ as _version  # noqa: E402

setup(
    name="solgate",
    version=_version,
    description="A CLI tool for S3 data synchronizations.",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Tom Coufal",
    author_email="tcoufal@redhat.com",
    maintainer="Tom Coufal",
    maintainer_email="tcoufal@redhat.com",
    url="https://github.com/aicoe-aiops/sync-pipelines",
    license="GPLv3+",
    packages=find_packages(),
    package_data={"solgate": [os.path.join("utils", "*.txt"), os.path.join("utils", "*.html")]},
    include_package_data=True,
    install_requires=["logstash-formatter>=0.5.17", "s3fs==0.4.*", "jinja2>=2.11", "click", "pyyaml"],
    entry_points={"console_scripts": ["solgate=solgate.cli:cli"]},
)
