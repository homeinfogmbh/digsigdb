#! /usr/bin/env python3

from setuptools import setup


setup(
    name="digsigdb",
    use_scm_version={"local_scheme": "node-and-timestamp"},
    setup_requires=["setuptools_scm"],
    author="HOMEINFO - Digitale Informationssysteme GmbH",
    author_email="info@homeinfo.de",
    maintainer="Richard Neumann",
    maintainer_email="r.neumann@homeinfo.de",
    requires=["hwdb", "peewee", "peeweeplus"],
    py_modules=["digsigdb"],
    description="Digital Sigange Database bindings.",
)
