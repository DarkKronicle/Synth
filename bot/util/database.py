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
import pydoc
import random
import string
from collections import OrderedDict

import psycopg2
import psycopg2.extras


def random_key(*, min_num=5, max_num=10):
    length = random.SystemRandom().randint(min_num, max_num)
    return '$' + ''.join(''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(length))) + '$'


class SchemaError(Exception):
    pass


class SQLType:
    python = None

    def to_dict(self):
        o = self.__dict__.copy()
        cls = self.__class__
        o['__meta__'] = cls.__module__ + '.' + cls.__qualname__
        return o

    @classmethod
    def from_dict(cls, data):
        meta = data.pop('__meta__')
        given = cls.__module__ + '.' + cls.__qualname__
        if given != meta:
            cls = pydoc.locate(meta)
            if cls is None:
                raise RuntimeError("Could not locate '{0}.'".format(meta))

        self = cls.__new__(cls)
        self.__dict__.update(data)
        return self

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

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
            if self.big:
                return 'BIGSERIAL'
            if self.small:
                return 'SMALLSERIAL'
            return 'SERIAL'
        if self.big:
            return 'BIGINT'
        if self.small:
            return 'SMALLINT'
        return 'INTEGER'

    def is_real_type(self):
        return not self.auto_increment


class Interval(SQLType):
    python = datetime.timedelta

    def __init__(self, field=None):
        if field:
            field = field.upper()
            if field not in ('YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND',
                             'YEAR TO MONTH', 'DAY TO HOUR', 'DAY TO MINUTE', 'DAY TO SECOND',
                             'HOUR TO MINUTE', 'HOUR TO SECOND', 'MINUTE TO SECOND'):
                raise SchemaError('invalid interval specified')
            self.field = field
        else:
            self.field = None

    def to_sql(self):
        if self.field:
            return 'INTERVAL ' + self.field
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
    def __init__(self, table, column, *, sql_type=None, on_delete='CASCADE', on_update='NO ACTION'):
        if not table or not isinstance(table, str):
            raise SchemaError('missing table to reference (must be string)')

        valid_actions = (
            'NO ACTION',
            'RESTRICT',
            'CASCADE',
            'SET NULL',
            'SET DEFAULT',
        )

        on_delete = on_delete.upper()
        on_update = on_update.upper()

        if on_delete not in valid_actions:
            raise TypeError('on_delete must be one of %s.' % valid_actions)

        if on_update not in valid_actions:
            raise TypeError('on_update must be one of %s.' % valid_actions)


        self.table = table
        self.column = column
        self.on_update = on_update
        self.on_delete = on_delete

        if sql_type is None:
            sql_type = Integer

        if inspect.isclass(sql_type):
            sql_type = sql_type()

        if not isinstance(sql_type, SQLType):
            raise TypeError('Cannot have non-SQLType derived sql_type')

        if not sql_type.is_real_type():
            raise SchemaError("sql_type must be a 'real' type")

        self.sql_type = sql_type.to_sql()

    def is_real_type(self):
        return False

    def to_sql(self):
        fmt = '{0.sql_type} REFERENCES {0.table} ({0.column})' \
              ' ON DELETE {0.on_delete} ON UPDATE {0.on_update}'
        return fmt.format(self)


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


class Column:
    __slots__ = ('column_type', 'index', 'primary_key', 'nullable',
                 'default', 'unique', 'name', 'index_name')

    def __init__(self, column_type, *, index=False, primary_key=False,
                 nullable=True, unique=False, default=None, name=None):

        if inspect.isclass(column_type):
            column_type = column_type()

        if not isinstance(column_type, SQLType):
            raise TypeError('Cannot have a non-SQLType derived column_type')

        self.column_type = column_type
        self.index = index
        self.unique = unique
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default
        self.name = name
        self.index_name = None

        # if sum(map(bool, (unique, primary_key, default is not None))) > 1:
        #     raise SchemaError(''unique', 'primary_key', and 'default' are mutually exclusive.')

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
                builder.append('(%s)' % default)
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

    def release(self):
        if self.connection is not None:
            self.connection.commit()
            self.connection.cursor().close()
            self.connection.close()
        if self._connection is not None:
            self._connection.commit()
            self._connection.close()

    def cursor(self):
        if self.connection is not None:
            return self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if self._connection is not None:
            return self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return None

    def __init__(self, connection=None, cleanup=True):
        self.connection = connection
        self._connection = None
        self._cleanup = cleanup

    async def __aenter__(self):
        if self.connection is None:
            self._cleanup = True
            self._connection = psycopg2.connect(f'dbname={Table.name} user={Table.user} password={Table.password}')
            c = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            return c
        return self.connection.cursor()

    async def __aexit__(self, *args):
        if self._cleanup:
            if self._connection is not None:
                self._connection.commit()
                self._connection.close()


class TableMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        return OrderedDict()

    def __new__(mcs, name, parents, attributes, **kwargs):
        columns = []

        try:
            table_name = kwargs['table_name']
        except KeyError:
            table_name = name.lower()

        attributes['__tablename__'] = table_name
        tablename = table_name

        for elem, value in attributes.items():
            if isinstance(value, Column):
                if value.name is None:
                    value.name = elem

                if value.index:
                    value.index_name = '%s_%s_idx' % (table_name, value.name)

                columns.append(value)

        attributes['columns'] = columns
        attributes['tablename'] = tablename
        return super().__new__(mcs, name, parents, attributes)

    def __init__(cls, name, parents, dct, **kwargs):
        super().__init__(name, parents, dct)


class Table(metaclass=TableMeta):

    @classmethod
    def acquire_connection(cls, connection=None):
        return MaybeAcquire(connection)

    @classmethod
    def create_data(cls, name, user, password):
        cls.name = name
        cls.user = user
        cls.password = password

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

        if len(primary_keys) > 0:
            column_creations.append('PRIMARY KEY ({})'.format(', '.join(primary_keys)))
        builder.append('({})'.format(', '.join(column_creations)))
        statements.append(' '.join(builder) + ';')

        for column in cls.columns:
            if column.index:
                fmt = 'CREATE INDEX IF NOT EXISTS {1.index_name} ON {0} ({1.name});'.format(cls.tablename, column)
                statements.append(fmt)

        return '\n'.join(statements)

    @classmethod
    async def create(cls, connection=None):
        sql = cls.create_table(overwrite=False)
        async with MaybeAcquire(connection=connection) as con:
            con.execute(sql)

    @classmethod
    async def insert(cls, connection=None, **kwargs):
        """Inserts an element to the table."""

        # verify column names:
        verified = {}
        for column in cls.columns:
            try:
                value = kwargs[column.name]
            except KeyError:
                continue

            check = column.column_type.python
            if value is None and not column.nullable:
                raise TypeError('Cannot pass None to non-nullable column %s.' % column.name)
            elif not check or not isinstance(value, check):
                fmt = 'column {0.name} expected {1.__name__}, received {2.__class__.__name__}'
                raise TypeError(fmt.format(column, check, value))

            if not isinstance(value, int):
                formatted = f'$${str(value)}$$'
            else:
                formatted = str(value)
            verified[column.name] = formatted

        sql = 'INSERT INTO {0} ({1}) VALUES ({2});'.format(cls.tablename, ', '.join(verified),
                                                           ', '.join(str(i) for i, _ in enumerate(verified, 1)))

        async with MaybeAcquire(connection=connection) as con:
            con.execute(sql, *verified.values())

    @classmethod
    async def remove(cls, connection=None, **kwargs):
        # verify column names:
        verified = {}
        for column in cls.columns:
            try:
                value = kwargs[column.name]
            except KeyError:
                continue

            check = column.column_type.python
            if value is None and not column.nullable:
                raise TypeError('Cannot pass None to non-nullable column %s.' % column.name)
            elif not check or not isinstance(value, check):
                fmt = 'column {0.name} expected {1.__name__}, received {2.__class__.__name__}'
                raise TypeError(fmt.format(column, check, value))

            verified[column.name] = value
        statements = []
        for col in verified:
            statements.append('{0} = $${1}$$'.format(col, verified[col]))

        sql = 'REMOVE FROM {0} WHERE {1};'.format(cls.tablename, ' AND '.join(statements))

        async with MaybeAcquire(connection=connection) as con:
            con.execute(sql)

    @classmethod
    def all_tables(cls):
        return cls.__subclasses__()
