"""Digital signage database ORM models.

Provides ORM models for digital signage
data that is not part of dscms4.
"""
from datetime import datetime
from uuid import uuid4

from peewee import ForeignKeyField, TextField, DateTimeField, BooleanField, \
    IntegerField, CharField, DateField, BlobField, UUIDField

from configlib import INIParser
from mdb import Address, Customer
from mimeutil import mimetype
from peeweeplus import MySQLDatabase, JSONModel, CascadingFKField
from terminallib import Terminal

from digsigdb import dom
from digsigdb.exceptions import DuplicateUserError


__all__ = [
    'Command',
    'Statistics',
    'LatestStats',
    'CleaningUser',
    'CleaningDate',
    'TenantMessage',
    'DamageReport',
    'ProxyHost',
    'Screenshot',
    'ScreenshotLog']


CONFIG = INIParser('/etc/digsigdb.conf')
DATABASE = MySQLDatabase.from_config(CONFIG['db'])


class _ApplicationModel(JSONModel):
    """Abstract common model."""

    class Meta:
        database = DATABASE
        schema = database.database


class Command(_ApplicationModel):
    """Command entries."""

    customer = ForeignKeyField(Customer, column_name='customer')
    vid = IntegerField()
    task = CharField(16)
    created = DateTimeField()
    completed = DateTimeField(null=True, default=None)

    @classmethod
    def add(cls, customer, vid, task):
        """Creates a new command task."""
        try:
            return cls.get(
                (cls.customer == customer) & (cls.vid == vid) &
                (cls.task == task))
        except cls.DoesNotExist:
            record = cls()
            record.customer = customer
            record.vid = vid
            record.task = task
            record.created = datetime.now()
            record.save()
            return record

    def complete(self, force=False):
        """Completes the command."""
        if force or self.completed is None:
            self.completed = datetime.now()
            self.save()


class Statistics(_ApplicationModel):
    """Usage statistics entries."""

    customer = ForeignKeyField(Customer, column_name='customer')
    vid = IntegerField()
    tid = IntegerField(null=True, default=None)
    document = CharField(255)
    timestamp = DateTimeField()

    @classmethod
    def add(cls, customer, vid, tid, document):
        """Adds a new statistics entry."""
        record = cls()
        record.customer = customer
        record.vid = vid
        record.tid = tid
        record.document = document
        record.timestamp = datetime.now()
        record.save()
        return record

    @classmethod
    def truncate(cls, tdelta):
        """Removes all entries older than now minus the given timedelta."""
        timestamp = datetime.now() - tdelta
        return cls.delete().where(cls.timestamp < timestamp).execute()

    @classmethod
    def latest(cls, terminal):
        """Returns the latest statistics
        record for the respective terminal.
        """
        return cls.select().where(
            (cls.customer == terminal.customer)
            & (cls.tid == terminal.tid)).order_by(
                cls.timestamp.desc()).get()

    @property
    def terminal(self):
        """Returns the appropriate terminal."""
        if self.tid is None:
            return None

        return Terminal.by_ids(self.customer.id, self.tid)


class LatestStats(_ApplicationModel):
    """Stores the last statistics of the respective terminal."""

    class Meta:
        table_name = 'latest_stats'

    terminal = CascadingFKField(Terminal, column_name='terminal')
    statistics = CascadingFKField(
        Statistics, column_name='statistics', null=True)

    @classmethod
    def refresh(cls, terminal=None):
        """Refreshes the stats for the respective terminal."""
        if terminal is None:
            for terminal in Terminal:
                cls.refresh(terminal=terminal)

            return

        try:
            current = cls.get(cls.terminal == terminal)
        except cls.DoesNotExist:
            current = cls()
            current.terminal = terminal

        try:
            current.statistics = Statistics.latest(terminal)
        except Statistics.DoesNotExist:
            current.delete_instance()
        else:
            current.save()


class CleaningUser(_ApplicationModel):
    """Accounts for valet service employees."""

    class Meta:
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

    class Meta:
        table_name = 'cleaning_date'

    user = ForeignKeyField(CleaningUser, column_name='user')
    address = ForeignKeyField(Address, column_name='address')
    timestamp = DateTimeField()

    @classmethod
    def add(cls, user, address):
        """Adds a new cleaning record."""
        record = cls()
        record.user = user
        record.address = address
        record.timestamp = datetime.now()
        record.save()
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

        if short:
            return {'timestamp': self.timestamp.isoformat(), 'user': user}

        json = super().to_json(**kwargs)
        json['user'] = user
        json['address'] = self.address.to_json(autofields=False)
        return json


class TenantMessage(_ApplicationModel):
    """Tenant to tenant messages."""

    class Meta:
        table_name = 'tenant_message'

    customer = ForeignKeyField(Customer, column_name='customer')
    address = ForeignKeyField(Address, column_name='address')
    message = TextField()
    created = DateTimeField(default=datetime.now)
    released = BooleanField(default=False)
    start_date = DateField(null=True, default=None)
    end_date = DateField(null=True, default=None)
    JSON_KEYS = {'startDate': start_date, 'endDate': end_date}

    @classmethod
    def add(cls, customer, address, message):
        """Creates a new entry for the respective customer and address."""
        record = cls()
        record.customer = customer
        record.address = address
        record.message = message
        return record

    @classmethod
    def from_terminal(cls, terminal, message):
        """Creates a new entry for the respective terminal."""
        return cls.add(terminal.customer, terminal.address, message)

    @classmethod
    def by_customer_address(cls, customer, address, released=True):
        """Yields records of the respective customer and address."""
        condition = cls.released == 1 if released else True
        condition &= cls.customer == customer
        condition &= cls.address == address
        return cls.select().where(condition)

    @classmethod
    def json_for_terminal(cls, terminal, released=True):
        """Returns a JSON list for the respective terminal."""
        return cls.json_for_customer_address(
            terminal.customer, terminal.address, released=released)

    @classmethod
    def json_for_customer_address(cls, customer, address, released=True):
        """Returns a JSON list for the respective customer and address."""
        json = []

        for record in cls.by_customer_address(
                customer, address, released=released):
            json.append(record.to_json())

        return json

    @classmethod
    def dom_for_terminal(cls, terminal, released=True):
        """Returns the DOM for the respective terminal."""
        return cls.dom_for_customer_address(
            terminal.customer, terminal.address, released=released)

    @classmethod
    def dom_for_customer_address(cls, customer, address, released=True):
        """Returns the dom for the respective customer and address."""
        xml = dom.tenant2tenant()

        for record in cls.by_customer_address(
                customer, address, released=released):
            xml.message.append(record.to_dom())

        return xml

    def to_json(self, address=True, **kwargs):
        """Adds the address to the dictionary."""
        json = super().to_json(**kwargs)

        if address:
            json['address'] = self.address.to_json()

        return json

    def to_dom(self):
        """Returns the tenant message as XML DOM."""
        xml = dom.TenantMessage(self.message)
        xml.created = self.created
        xml.released = self.released
        xml.startDate = self.start_date
        xml.endDate = self.end_date
        return xml


class DamageReport(_ApplicationModel):
    """Damage reports."""

    class Meta:
        table_name = 'damage_report'

    customer = ForeignKeyField(Customer, column_name='customer')
    address = ForeignKeyField(Address, column_name='address')
    message = TextField()
    name = CharField(255)
    contact = CharField(255, null=True, default=None)
    damage_type = CharField(255)
    timestamp = DateTimeField(default=datetime.now)
    checked = BooleanField(default=False)
    JSON_KEYS = {'damageType': damage_type}

    @classmethod
    def from_json(cls, json, customer, address):
        """Creates a new entry from the respective
        customer, address and dictionary.
        """
        record = super().from_json(json)
        record.customer = customer
        record.address = address
        return record

    def to_json(self, address=True, **kwargs):
        """Returns a JSON-ish dictionary."""
        json = super().to_json(**kwargs)

        if address:
            json['address'] = self.address.to_json()

        return json


class ProxyHost(_ApplicationModel):
    """Valid proxy hosts."""

    class Meta:
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

    class Meta:
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
