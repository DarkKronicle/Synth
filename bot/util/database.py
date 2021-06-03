# Lots of classes are very small data objects.
"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

# I am pretty dang new to databases, but here is my third attempt at making this easier and more likely to succeed later
# down the line.

import datetime
# Lots of inspiration came from https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/db.py (which is under MPL)
import decimal
import inspect
import json
import pydoc
import random
import string
from collections import OrderedDict

import asyncpg


def random_key(*, min_num=5, max_num=10, forced_num=-1):
    if forced_num <= 0:
        length = random.SystemRandom().randint(min_num, max_num)
    else:
        length = forced_num
    return ''.join(
        ''.join(
            random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(length)
        ),
    )


class SchemaError(Exception):
    """An exception thrown if table can't exist"""


class SQLType:
    python = None

    def to_dict(self):
        sql_copy = self.__dict__.copy()
        class_obj = self.__class__
        sql_copy['__meta__'] = '{0}.{1}'.format(class_obj.__module__, class_obj.__qualname__)  # noqa: WPS609
        return sql_copy

    @classmethod
    def from_dict(cls, previous_dict):
        meta = previous_dict.pop('__meta__')
        given = '{0}.{1}'.format(cls.__module__, cls.__qualname__)
        sql_class = cls
        if given != meta:
            sql_class = pydoc.locate(meta)
            if sql_class is None:
                raise RuntimeError("Could not locate '{0}.'".format(meta))

        self_object = sql_class.__new__(sql_class)  # noqa:  WPS609
        self_object.__dict__.update(previous_dict)  # noqa:  WPS609
        return self_object

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__  # noqa:  WPS609

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_sql(self):
        raise NotImplementedError()

    def is_real_type(self):
        return True


class Binary(SQLType):
    python = bytes

    def to_sql(self):
        return 'BYTEA'


class Boolean(SQLType):
    python = bool

    def to_sql(self):
        return 'BOOLEAN'


class Date(SQLType):
    python = datetime.date

    def to_sql(self):
        return 'DATE'


class Datetime(SQLType):
    python = datetime.datetime

    def __init__(self, *, timezone=False):
        self.timezone = timezone

    def to_sql(self):
        if self.timezone:
            return 'TIMESTAMP WITH TIME ZONE'
        return 'TIMESTAMP'


class Double(SQLType):
    python = float

    def to_sql(self):
        return 'REAL'


class Float(SQLType):
    python = float

    def to_sql(self):
        return 'FLOAT'


class Integer(SQLType):
    python = int

    def __init__(self, *, big=False, small=False, auto_increment=False):
        self.big = big
        self.small = small
        self.auto_increment = auto_increment

        if big and small:
            raise SchemaError('Integer column type cannot be both big and small.')

    def to_sql(self):
        if self.auto_increment:
            return self._auto_inc()

        if self.big:
            return 'BIGINT'

        if self.small:
            return 'SMALLINT'

        return 'INTEGER'

    def is_real_type(self):
        return not self.auto_increment

    def _auto_inc(self):
        if self.big:
            return 'BIGSERIAL'
        if self.small:
            return 'SMALLSERIAL'
        return 'SERIAL'


class Interval(SQLType):
    python = datetime.timedelta
    fields = [
        'YEAR',
        'MONTH',
        'DAY',
        'HOUR',
        'MINUTE',
        'SECOND',
        'YEAR TO MONTH',
        'DAY TO HOUR',
        'DAY TO MINUTE',
        'DAY TO SECOND',
        'HOUR TO MINUTE',
        'HOUR TO SECOND',
        'MINUTE TO SECOND',
    ]

    def __init__(self, field=None):
        if field:
            field = field.upper()
            if field not in self.fields:
                raise SchemaError('invalid interval specified')
            self.field = field
        else:
            self.field = None

    def to_sql(self):
        if self.field:
            return 'INTERVAL {0}'.format(self.field)
        return 'INTERVAL'


class Numeric(SQLType):
    python = decimal.Decimal

    def __init__(self, *, precision=None, scale=None):
        if precision is not None:
            if precision < 0 or precision > 1000:
                raise SchemaError('precision must be greater than 0 and below 1000')
            if scale is None:
                scale = 0

        self.precision = precision
        self.scale = scale

    def to_sql(self):
        if self.precision is not None:
            return 'NUMERIC({0.precision}, {0.scale})'.format(self)
        return 'NUMERIC'


class String(SQLType):
    python = str

    def __init__(self, *, length=None, fixed=False):
        self.length = length
        self.fixed = fixed

        if fixed and length is None:
            raise SchemaError('Cannot have fixed string with no length')

    def to_sql(self):
        if self.length is None:
            return 'TEXT'
        if self.fixed:
            return 'CHAR({0.length})'.format(self)
        return 'VARCHAR({0.length})'.format(self)


class Time(SQLType):
    python = datetime.time

    def __init__(self, *, timezone=False):
        self.timezone = timezone

    def to_sql(self):
        if self.timezone:
            return 'TIME WITH TIME ZONE'
        return 'TIME'


class JSON(SQLType):
    python = None

    def to_sql(self):
        return 'JSONB'


class ForeignKey(SQLType):
    valid_actions = {
        'NO ACTION',
        'RESTRICT',
        'CASCADE',
        'SET NULL',
        'SET DEFAULT',
    }

    def __init__(self, table, column, **kwargs):  # noqa: WPS238
        if not table or not isinstance(table, str):
            raise SchemaError('missing table to reference (must be string)')

        self.on_update = kwargs.pop('on_update', 'NO ACTION').upper()
        self.on_delete = kwargs.pop('on_delete', 'CASCADE').upper()

        if self.on_delete not in self.valid_actions:
            raise TypeError('on_delete must be one of {0}.'.format(self.valid_actions))

        if self.on_update not in self.valid_actions:
            raise TypeError('on_update must be one of {0}.'.format(self.valid_actions))

        self.table = table
        self.column = column

        self.sql_type = self._check_sql_type(kwargs.pop('sql_type', None))

    def is_real_type(self):
        return False

    def to_sql(self):
        fmt = '{0.sql_type} REFERENCES {0.table} ({0.column}) ON DELETE {0.on_delete} ON UPDATE {0.on_update}'
        return fmt.format(self)

    def _check_sql_type(self, sql_type):
        if sql_type is None:
            sql_type = Integer

        if inspect.isclass(sql_type):
            sql_type = sql_type()

        if not isinstance(sql_type, SQLType):
            raise TypeError('Cannot have non-SQLType derived sql_type')

        if not sql_type.is_real_type():
            raise SchemaError("sql_type must be a 'real' type")

        return sql_type.to_sql()


class Array(SQLType):
    python = list

    def __init__(self, sql_type):
        if inspect.isclass(sql_type):
            sql_type = sql_type()

        if not isinstance(sql_type, SQLType):
            raise TypeError('Cannot have non-SQLType derived sql_type')

        if not sql_type.is_real_type():
            raise SchemaError("sql_type must be a 'real' type")

        self.sql_type = sql_type.to_sql()

    def to_sql(self):
        return '{0.sql_type} ARRAY'.format(self)

    def is_real_type(self):
        # technically, it is a real type
        # however, it doesn't play very well with migrations
        # so we're going to pretend that it isn't
        return False


class Column:   # noqa: WPS230
    __slots__ = ('column_type', 'index', 'primary_key', 'nullable', 'default', 'unique', 'name', 'index_name')

    def __init__(self, column_type, **kwargs):
        if inspect.isclass(column_type):
            column_type = column_type()

        if not isinstance(column_type, SQLType):
            raise TypeError('Cannot have a non-SQLType derived column_type')

        self.column_type = column_type
        self.index = kwargs.pop('index', False)
        self.unique = kwargs.pop('unique', False)
        self.primary_key = kwargs.pop('primary_key', False)
        self.nullable = kwargs.pop('nullable', True)
        self.default = kwargs.pop('default', None)
        self.name = kwargs.pop('name', None)
        self.index_name = None

    def create_statement(self):
        builder = [self.name, self.column_type.to_sql()]

        default = self.default
        if default is not None:
            builder.append('DEFAULT')
            if isinstance(default, str) and isinstance(self.column_type, String):
                builder.append("'{0}'".format(default))
            elif isinstance(default, bool):
                builder.append(str(default).upper())
            else:
                builder.append('({0})'.format(default))
        elif self.unique:
            builder.append('UNIQUE')
        if not self.nullable:
            builder.append('NOT NULL')

        return ' '.join(builder)


class PrimaryKeyColumn(Column):
    """Shortcut for a SERIAL PRIMARY KEY column."""

    def __init__(self):
        super().__init__(Integer(auto_increment=True), primary_key=True)


class MaybeAcquire:

    def __init__(self, connection=None, cleanup=True, *, pool):
        self.connection = connection
        self._cleanup = cleanup
        self._connection = None
        self.pool = pool

    async def __aenter__(self):
        if self.connection is None:
            self._cleanup = True
            self._connection = c = await self.pool.acquire()
            return c
        return self.connection

    async def __aexit__(self, *args):
        if self._cleanup and self._connection:
            await self.pool.release(self._connection)


class TableMeta(type):

    def __new__(cls, name, parents, attributes, **kwargs):
        columns = []

        try:
            table_name = kwargs['table_name']
        except KeyError:
            table_name = name.lower()

        attributes['__tablename__'] = table_name
        tablename = table_name

        for attribute, attribute_value in attributes.items():
            if isinstance(attribute_value, Column):
                if attribute_value.name is None:
                    attribute_value.name = attribute

                if attribute_value.index:
                    attribute_value.index_name = '{0}_{1}_idx'.format(table_name, attribute_value.name)

                columns.append(attribute_value)

        attributes['columns'] = columns
        attributes['tablename'] = tablename
        return super().__new__(cls, name, parents, attributes)

    def __init__(cls, name, parents, dct, **kwargs):
        super().__init__(name, parents, dct)

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        return OrderedDict()


class Table(metaclass=TableMeta):

    @classmethod
    async def create_pool(cls, uri, **kwargs):
        """Sets up and returns the PostgreSQL connection pool that is used.
        .. note::
            This must be called at least once before doing anything with the tables.
            And must be called on the ``Table`` class.
        Parameters
        -----------
        uri: str
            The PostgreSQL URI to connect to.
        \*\*kwargs
            The arguments to forward to asyncpg.create_pool.
        """

        def _encode_jsonb(value):
            return json.dumps(value)

        def _decode_jsonb(value):
            return json.loads(value)

        old_init = kwargs.pop('init', None)

        async def init(con):
            await con.set_type_codec('jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb,
                                     format='text')
            if old_init is not None:
                await old_init(con)

        cls._pool = pool = await asyncpg.create_pool(uri, init=init, **kwargs)
        return pool

    @classmethod
    def acquire_connection(cls, connection=None):
        return MaybeAcquire(connection, pool=cls._pool)

    @classmethod
    def create_table(cls, overwrite=False):
        statements = []
        builder = ['CREATE TABLE']

        if not overwrite:
            builder.append('IF NOT EXISTS')

        builder.append(cls.tablename)

        column_creations = []
        primary_keys = []
        for col in cls.columns:
            column_creations.append(col.create_statement())
            if col.primary_key:
                primary_keys.append(col.name)

        if primary_keys:
            column_creations.append('PRIMARY KEY ({0})'.format(', '.join(primary_keys)))
        builder.append('({0})'.format(', '.join(column_creations)))
        statements.append('{0};'.format(' '.join(builder)))

        for column in cls.columns:
            if column.index:
                fmt = 'CREATE INDEX IF NOT EXISTS {1.index_name} ON {0} ({1.name});'.format(cls.tablename, column)
                statements.append(fmt)

        return '\n'.join(statements)

    @classmethod
    async def create(cls, connection=None):
        sql = cls.create_table(overwrite=False)
        async with MaybeAcquire(connection=connection, pool=cls._pool) as con:
            await con.execute(sql)

    @classmethod
    def all_tables(cls):
        return cls.__subclasses__()
