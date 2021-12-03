"""Digital signage database ORM models.

Provides ORM models for digital signage
data that is not part of dscms4.
"""
from datetime import datetime

from peewee import CharField, DateTimeField, ForeignKeyField

from hwdb import Deployment
from peeweeplus import MySQLDatabaseProxy, JSONModel


__all__ = ['DigsigdbModel', 'Statistics', 'ProxyHost']


DATABASE = MySQLDatabaseProxy('digsigdb')


def create_tables():
    """Creates the tables."""

    for model in MODELS:
        model.create_table()


class DigsigdbModel(JSONModel):
    """Abstract common model."""

    class Meta:     # pylint: disable=C0111,R0903
        database = DATABASE
        schema = database.database


class Statistics(DigsigdbModel):
    """Usage statistics entries."""

    deployment = ForeignKeyField(
        Deployment, column_name='deployment', on_delete='CASCADE',
        on_update='CASCADE')
    document = CharField(255)
    timestamp = DateTimeField(default=datetime.now)

    @classmethod
    def add(cls, deployment, document):
        """Adds a new statistics entry."""
        record = cls()
        record.deployment = deployment
        record.document = document
        record.save()
        return record

    @classmethod
    def truncate(cls, tdelta):
        """Removes all entries older than now minus the given timedelta."""
        timestamp = datetime.now() - tdelta
        return cls.delete().where(cls.timestamp < timestamp).execute()

    @classmethod
    def latest(cls, deployment):
        """Returns the latest statistics
        record for the respective deployment.
        """
        return cls.select().where(cls.deployment == deployment).order_by(
            cls.timestamp.desc()).get()

    def to_csv(self, sep=','):
        """Converts the record into a CSV entry."""
        address = self.deployment.address
        timestamp = self.timestamp.isoformat()  # pylint: disable=E1101
        fields = (
            timestamp, address.street, address.house_number, address.zip_code,
            address.city, self.document)
        return sep.join(fields)


class ProxyHost(DigsigdbModel):
    """Valid proxy hosts."""

    class Meta:     # pylint: disable=C0111,R0903
        table_name = 'proxy_hosts'

    hostname = CharField(255)


MODELS = (Statistics, ProxyHost)
