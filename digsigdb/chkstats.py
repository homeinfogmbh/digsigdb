#! /usr/bin/env python3
"""Checks statistics for the respective system."""

from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta

from hwdb import system

from digsigdb import Statistics


__all__ = ['main']


DESCRIPTION = 'Checks statistics for the respective system.'


def days(value: str) -> timedelta:
    """Returns a value in days."""

    return timedelta(days=int(value))


def get_args() -> Namespace:
    """Parses the options."""

    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument('system', type=system, help='the system to check')
    parser.add_argument('-w', '--warning', type=days, metavar='days')
    parser.add_argument('-c', '--critical', type=days, metavar='days')
    return parser.parse_args()


def main() -> int:
    """Checks the system's stats."""

    args = get_args()
    now = datetime.now()

    try:
        latest = Statistics.latest(system)
    except Statistics.DoesNotExist:
        print('Never.')
        return 2

    last = latest.timestamp
    print(last)

    if now - last <= args.warning:
        return 0

    if now - last <= args.critical:
        return 1

    return 2
