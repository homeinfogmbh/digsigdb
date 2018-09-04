"""Common functions."""

from datetime import timedelta

from digsigdb.orm import Statistics, LatestStats


__all__ = ['refresh_termstats']


def refresh_termstats(truncate=365):
    """Refreshes the terminal statistics, truncating the statistics
    entries to the amount of days specified by truncate beforehand.
    """

    tdelta = timedelta(days=truncate)
    Statistics.truncate(tdelta)
    LatestStats.refresh()
