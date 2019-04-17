#! /usr/bin/env python3

from distutils.core import setup


setup(
    name='digsigdb',
    version='latest',
    author='HOMEINFO - Digitale Informationssysteme GmbH',
    author_email='<info at homeinfo dot de>',
    maintainer='Richard Neumann',
    maintainer_email='<r dot neumann at homeinfo priod de>',
    requires=['mdb'],
    packages=['digsigdb'],
    scripts=['files/chkstats'],
    data_files=[
        ('/usr/lib/systemd/system',
         ['files/refresh-termstats.service',
          'files/refresh-termstats.timer'])],
    description='Digital Sigange Database bindings.')
