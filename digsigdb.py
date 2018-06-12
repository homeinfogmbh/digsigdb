"""Digital signage database ORM models.

Provides ORM models for digital signage
data that is not part of dscms4.
"""

from datetime import datetime
from peewee import PrimaryKeyField, ForeignKeyField, TextField, DateTimeField,\
    BooleanField, IntegerField, CharField, DateField

from configlib import INIParser
from homeinfo.crm import Address, Customer
from peeweeplus import MySQLDatabase, JSONModel
from terminallib import Terminal


__all__ = [
    'Command',
    'Statistics',
    'CleaningUser',
    'CleaningDate',
    'TenantMessage',
    'DamageReport',
    'ProxyHost']


CONFIG = INIParser('/etc/digsigdb.conf')
DATABASE = MySQLDatabase.from_config(CONFIG['db'])


class DuplicateUserError(Exception):
    """Indicates a duplicate user entry."""

    pass


class _ApplicationModel(JSONModel):
    """Abstract common model."""

    class Meta:
        database = DATABASE
        schema = database.database

    id = PrimaryKeyField()


class Command(_ApplicationModel):
    """Command entries."""

    customer = ForeignKeyField(Customer, db_column='customer')
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

    customer = ForeignKeyField(Customer, db_column='customer')
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

    @property
    def terminal(self):
        """Returns the appropriate terminal."""
        if self.tid is None:
            return None

        return Terminal.by_ids(self.customer.id, self.tid)


class CleaningUser(_ApplicationModel):
    """Accounts for valet service employees."""

    class Meta:
        db_table = 'cleaning_user'

    name = CharField(64)
    customer = ForeignKeyField(Customer, db_column='customer')
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

    def to_dict(self, *args, short=False, **kwargs):
        """Returns a JSON-ish dictionary."""
        if short:
            return {'id': self.id, 'name': self.name}

        return super().to_dict(*args, **kwargs)


class CleaningDate(_ApplicationModel):
    """Cleaning chart entries."""

    class Meta:
        db_table = 'cleaning_date'

    user = ForeignKeyField(CleaningUser, db_column='user')
    address = ForeignKeyField(Address, db_column='address')
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

    def to_dict(self, *args, short=False, **kwargs):
        """Returns a JSON compliant dictionary."""
        if short:
            return {
                'timestamp': self.timestamp.isoformat(),
                'user': self.user.name}

        dictionary = super().to_dict(*args, **kwargs)
        dictionary['user'] = self.user.to_dict(short=True)
        dictionary['address'] = self.address.to_dict(primary_key=False)
        return dictionary


class TenantMessage(_ApplicationModel):
    """Tenant to tenant messages."""

    class Meta:
        db_table = 'tenant_message'

    address = ForeignKeyField(Address, db_column='address')
    message = TextField()
    created = DateTimeField(default=datetime.now)
    released = BooleanField(default=False)
    start_date = DateField(null=True, default=None)
    end_date = DateField(null=True, default=None)

    @classmethod
    def from_message(cls, address, message):
        """Creates a new entry for the respective address."""
        record = cls()
        record.address = address
        record.message = message
        return record


class DamageReport(_ApplicationModel):
    """Damage reports."""

    class Meta:
        db_table = 'damage_report'

    address = ForeignKeyField(Address, db_column='address')
    message = TextField()
    name = CharField(255)
    contact = CharField(255, null=True, default=None)
    damage_type = CharField(255)
    timestamp = DateTimeField(default=datetime.now)
    checked = BooleanField(default=False)

    @classmethod
    def from_dict(cls, address, dictionary):
        """Creates a new entry from the respective address and dictionary."""
        record = super().from_dict(dictionary)
        record.address = address
        return record


class ProxyHost(_ApplicationModel):
    """Valid proxy hosts."""

    class Meta:
        db_table = 'proxy_hosts'

    hostname = CharField(255)
