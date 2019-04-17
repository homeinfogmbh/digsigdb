"""Digital signage database ORM models.

Provides ORM models for digital signage
data that is not part of dscms4.
"""
from datetime import datetime

from peewee import BooleanField
from peewee import CharField
from peewee import DateTimeField
from peewee import ForeignKeyField

from mdb import Address, Customer
from peeweeplus import MySQLDatabase, JSONModel
from terminallib import Deployment

from digsigdb import dom
from digsigdb.config import CONFIG
from digsigdb.exceptions import DuplicateUserError


__all__ = [
    'Statistics',
    'CleaningUser',
    'CleaningDate',
    'CleaningAnnotation',
    'ProxyHost']


DATABASE = MySQLDatabase.from_config(CONFIG['db'])


def create_tables():
    """Creates the tables."""

    for model in MODELS:
        model.create_table()


class _ApplicationModel(JSONModel):
    """Abstract common model."""

    class Meta:     # pylint: disable=C0111,R0903
        database = DATABASE
        schema = database.database


class Statistics(_ApplicationModel):
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
        fields = (timestamp, str(address), self.document)
        return sep.join(fields)


class CleaningUser(_ApplicationModel):
    """Accounts for valet service employees."""

    class Meta:     # pylint: disable=C0111,R0903
        table_name = 'cleaning_user'

    name = CharField(64)
    type_ = CharField(64, column_name='type', null=True)
    customer = ForeignKeyField(Customer, column_name='customer')
    pin = CharField(4)
    annotation = CharField(255, null=True, default=None)
    created = DateTimeField()
    enabled = BooleanField(default=False)

    @classmethod
    def add(cls, name, customer, pin, annotation=None, enabled=None):
        """Adds a new cleaning user."""
        try:
            cls.get((cls.name == name) & (cls.customer == customer))
        except cls.DoesNotExist:
            record = cls()
            record.name = name
            record.customer = customer
            record.pin = pin
            record.annotation = annotation
            record.created = datetime.now()

            if enabled is not None:
                record.enabled = enabled

            record.save()
            return record

        raise DuplicateUserError()

    def to_json(self, short=False, **kwargs):
        """Returns a JSON-ish dictionary."""
        if short:
            if self.type_ is None:
                return self.name    # Compat.

            return {'name': self.name, 'type': self.type_}

        return super().to_json(**kwargs)


class CleaningDate(_ApplicationModel):
    """Cleaning chart entries."""

    class Meta:     # pylint: disable=C0111,R0903
        table_name = 'cleaning_date'

    user = ForeignKeyField(CleaningUser, column_name='user')
    address = ForeignKeyField(Address, column_name='address')
    deployment = ForeignKeyField(
        Deployment, null=True, column_name='deployment', on_delete='CASCADE',
        on_update='CASCADE')
    timestamp = DateTimeField()

    @classmethod
    def add(cls, user, address, annotations=None):
        """Adds a new cleaning record."""
        record = cls()
        record.user = user
        record.address = address
        record.timestamp = datetime.now()
        record.save()

        if annotations:
            for annotation in annotations:
                annotation = CleaningAnnotation(
                    cleaning_date=record, text=annotation)
                annotation.save()

        return record

    @classmethod
    def by_address(cls, address, limit=None):
        """Returns a dictionary for the respective address."""
        for counter, cleaning_date in enumerate(cls.select().where(
                cls.address == address).order_by(cls.timestamp.desc())):
            if limit is not None and counter >= limit:
                return

            yield cleaning_date

    def to_json(self, short=False, **kwargs):
        """Returns a JSON compliant dictionary."""
        user = self.user.to_json(short=short)
        annotations = [annotation.text for annotation in self.annotations]

        if short:
            return {
                'timestamp': self.timestamp.isoformat(),
                'user': user,
                'annotations': annotations}

        json = super().to_json(**kwargs)
        json['user'] = user
        json['address'] = self.address.to_json(autofields=False)
        json['annotations'] = annotations
        return json

    def to_dom(self):
        """Converts the ORM model into an XML DOM."""
        xml = dom.Cleaning()
        xml.timestamp = self.timestamp
        user = dom.User(self.user.name)
        user.type = self.user.type_
        xml.user = user

        for annotation in self.annotations:
            xml.annotation.append(annotation.text)

        return xml


class CleaningAnnotation(_ApplicationModel):
    """Optional annotations for cleaning log entries."""

    class Meta:     # pylint: disable=C0111,R0903
        table_name = 'cleaning_annotation'

    cleaning_date = ForeignKeyField(
        CleaningDate, column_name='cleaning_date', backref='annotations',
        on_delete='CASCADE')
    text = CharField(255)


class ProxyHost(_ApplicationModel):
    """Valid proxy hosts."""

    class Meta:     # pylint: disable=C0111,R0903
        table_name = 'proxy_hosts'

    hostname = CharField(255)


MODELS = (
    Statistics, CleaningUser, CleaningDate, CleaningAnnotation, ProxyHost)
