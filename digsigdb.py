"""Digital signage database ORM models.

Provides ORM models for miscellaneous digital
signage data that is not part of dscms4.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Union

from peewee import CharField, DateTimeField, ForeignKeyField

from hwdb import Deployment
from peeweeplus import MySQLDatabaseProxy, JSONModel


__all__ = ['DigsigdbModel', 'Statistics', 'ProxyHost', 'create_tables']


DATABASE = MySQLDatabaseProxy('application', 'digsigdb.conf')


class DigsigdbModel(JSONModel):
    """Abstract common model."""

    class Meta:
        database = DATABASE
        schema = database.database


class Statistics(DigsigdbModel):
    """Usage statistics entries."""

    deployment = ForeignKeyField(
        Deployment, column_name='deployment', on_delete='CASCADE',
        on_update='CASCADE'
    )
    document = CharField(255)
    timestamp = DateTimeField(default=datetime.now)

    @classmethod
    def add(
            cls,
            deployment: Union[Deployment, int],
            document: str
    ) -> Statistics:
        """Adds a new statistics entry."""
        record = cls()
        record.deployment = deployment
        record.document = document
        record.save()
        return record

    @classmethod
    def truncate(cls, period: timedelta) -> None:
        """Removes all entries older than now minus the given timedelta."""
        timestamp = datetime.now() - period
        return cls.delete().where(cls.timestamp < timestamp).execute()

    @classmethod
    def latest(cls, deployment: Union[Deployment, int]) -> Statistics:
        """Returns the latest statistics
        record for the respective deployment.
        """
        return cls.select().where(
            cls.deployment == deployment
        ).order_by(
            cls.timestamp.desc()
        ).get()

    def to_csv(self, sep: str = ',') -> str:
        """Converts the record into a CSV entry."""
        return sep.join([
            self.timestamp.isoformat(),
            (address := self.deployment.address).street,
            address.house_number,
            address.zip_code,
            address.city, self.document
        ])


class ProxyHost(DigsigdbModel):
    """Valid proxy hosts."""

    class Meta:
        table_name = 'proxy_hosts'

    hostname = CharField(255)


MODELS = (Statistics, ProxyHost)


def create_tables():
    """Creates the tables."""

    for model in MODELS:
        model.create_table()
