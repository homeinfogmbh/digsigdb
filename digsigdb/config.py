"""Configuration parsing."""

from configlib import loadcfg


__all__ = ['CONFIG']


CONFIG = loadcfg('digsigdb.conf')
