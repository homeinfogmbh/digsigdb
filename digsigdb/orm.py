"""Digital signage database ORM models.

Provides ORM models for digital signage
data that is not part of dscms4.
"""
from datetime import datetime
from uuid import uuid4

from peewee import BlobField
from peewee import BooleanField
from peewee import CharField
from peewee import DateTimeField
from peewee import ForeignKeyField
from peewee import IntegerField
from peewee import UUIDField

from mdb import Address, Customer
from mimeutil import mimetype
from peeweeplus import MySQLDatabase, JSONModel
from terminallib import System

from digsigdb import dom
from digsigdb.config import CONFIG
from digsigdb.exceptions import DuplicateUserError


__all__ = [
    'Statistics',
    'CleaningUser',
    'CleaningDate',
    'CleaningAnnotation',
    'ProxyHost',
    'Screenshot',
    'ScreenshotLog']


DATABASE = MySQLDatabase.from_config(CONFIG['db'])


class _ApplicationModel(JSONModel):
    """Abstract common model."""

    class Meta:     # pylint: disable=C0111
        database = DATABASE
        schema = database.database


class Statistics(_ApplicationModel):
    """Usage statistics entries."""

    system = ForeignKeyField(System, column_name='system', on_delete='CASCADE')
    document = CharField(255)
    timestamp = DateTimeField(default=datetime.now)

    @classmethod
    def add(cls, system, document):
        """Adds a new statistics entry."""
        record = cls()
        record.system = system
        record.document = document
        record.save()
        return record

    @classmethod
    def truncate(cls, tdelta):
        """Removes all entries older than now minus the given timedelta."""
        timestamp = datetime.now() - tdelta
        return cls.delete().where(cls.timestamp < timestamp).execute()

    @classmethod
    def latest(cls, system):
        """Returns the latest statistics
        record for the respective system.
        """
        return cls.select().where(cls.system == system).order_by(
            cls.timestamp.desc()).get()

    def to_csv(self, sep=','):
        """Converts the record into a CSV entry."""
        address = self.system.location.address
        timestamp = self.timestamp.isoformat()
        fields = (timestamp, str(address), self.document)
        return sep.join(fields)


class CleaningUser(_ApplicationModel):
    """Accounts for valet service employees."""

    class Meta:     # pylint: disable=C0111
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

    class Meta:     # pylint: disable=C0111
        table_name = 'cleaning_date'

    user = ForeignKeyField(CleaningUser, column_name='user')
    address = ForeignKeyField(Address, column_name='address')
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

    class Meta:     # pylint: disable=C0111
        table_name = 'cleaning_annotation'

    cleaning_date = ForeignKeyField(
        CleaningDate, column_name='cleaning_date', backref='annotations',
        on_delete='CASCADE')
    text = CharField(255)


class ProxyHost(_ApplicationModel):
    """Valid proxy hosts."""

    class Meta:     # pylint: disable=C0111
        table_name = 'proxy_hosts'

    hostname = CharField(255)


class Screenshot(_ApplicationModel):
    """Stores screenshots."""

    uuid = UUIDField(default=uuid4)
    customer = ForeignKeyField(Customer, column_name='customer')
    address = ForeignKeyField(Address, column_name='address')
    _bytes = BlobField(column_name='bytes')

    @classmethod
    def add(cls, uuid, customer, address, bytes_):
        """Adds a screenshot."""
        try:
            return cls.fetch(uuid, customer, address)
        except cls.DoesNotExist:
            screenshot = cls()
            screenshot.uuid = uuid
            screenshot.customer = customer
            screenshot.address = address
            screenshot.bytes = bytes_
            screenshot.save()
            return screenshot

    @classmethod
    def fetch(cls, uuid, customer, address):
        """Returns a screenshot by uuid, customer and address."""
        return cls.get(
            (cls.uuid == uuid)
            & (cls.customer == customer)
            & (cls.address == address))

    @property
    def bytes(self):
        """Returns the respective bytes."""
        return self._bytes

    @bytes.setter
    def bytes(self, bytes_):
        """Returns the respective bytes."""
        self._bytes = bytes_

    @property
    def mimetype(self):
        """Returns the data's mime type."""
        return mimetype(self._bytes)

    @property
    def log_entries(self):
        """Yields raw log entry records for this screenshot."""
        return ScreenshotLog.select().where(
            (ScreenshotLog.uuid == self.uuid)
            & (ScreenshotLog.customer == self.customer)
            & (ScreenshotLog.address == self.address))

    @property
    def readouts(self):
        """Yields readouts when this screenshot was shown."""
        for log_entry in self.log_entries:
            yield (log_entry.begin, log_entry.end)


class ScreenshotLog(_ApplicationModel):
    """Logs displayed screenshots."""

    class Meta:     # pylint: disable=C0111
        table_name = 'screenshot_log'

    uuid = UUIDField()
    customer = ForeignKeyField(Customer, column_name='customer')
    address = ForeignKeyField(Address, column_name='address')
    begin = DateTimeField(default=datetime.now)
    end = DateTimeField(null=True)

    @classmethod
    def add(cls, uuid, customer, address):
        """Adds a screenshot log entry."""
        record = cls()
        record.uuid = uuid
        record.customer = customer
        record.address = address
        record.save()
        return record

    @classmethod
    def close(cls, uuid, customer, address):
        """Closes the latest screenshot log entry
        of the provided uuid, customer and address.
        """
        record = cls.get(
            (cls.uuid == uuid)
            & (cls.customer == customer)
            & (cls.address == address)
            & (cls.end >> None)).order_by(cls.begin.desc()).get()
        record.end = datetime.now()
        record.save()
        return record
