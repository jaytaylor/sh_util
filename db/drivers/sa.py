# -*- coding: utf-8 -*-

"""SqlAlchemy sh_util db driver."""

__author__ = 'Jay Taylor [@jtaylor]'

import logging, re, settings
from sqlalchemy.sql.expression import bindparam, text


_argRe = re.compile(r'%s')

def sqlAndArgsToText(sql, args=None):
    """
    Convert plain old combination of sql/args to SqlAlchemy `text` instance.

    It seems ridiculous to have to do this, but I really want to use the `text` instances to turn off auto-commit.
    """
    if not args:
        return text(sql)

    bindparams = []
    i = [-1] # Using a list since we need to mutate the variable which isn't allowed with a direct variable reference.

    def nextBindSub(*_):
        i[0] += 1
        binding = '${0}'.format(i[0])
        bindparams.append(bindparam(binding, args[i[0]]))
        return ':{0}'.format(binding)

    transformedSql = _argRe.sub(nextBindSub, sql)
    return text(transformedSql, bindparams=bindparams)


_transactions = {}


def connections():
    """Infer and return appropriate set of connections."""
    from app import app
    #from flask.globals import current_app
    return app.engines


def switchDefaultDatabase(name):
    """Swap in a different default database."""
    pass


def _getRealShardConnectionName(using):
    """Lookup and return the ACTUAL connection name, never use 'default'."""
    if using == 'default':
        using = connections().keys()[0]

    return using


def _dictfetchall(resultProxy):
    """Returns all rows from a cursor as a dict."""
    desc = resultProxy.keys()
    return [dict(zip([col for col in desc], row)) for row in resultProxy.fetchall()]


def db_query(sql, args=None, as_dict=False, using='default', debug=False):
    """
    Execute raw select queries.  Not tested or guaranteed to work with any
    other type of query.
    """
    from ..import DEBUG

    if args is None:
        args = tuple()

    using = _getRealShardConnectionName(using)

    if DEBUG is True or debug is True:
        logging.info(u'-- [DEBUG] DB_QUERY, using={0} ::\n{1}'.format(using, sql))

    resultProxy = connections()[using].execute(sqlAndArgsToText(sql, args).execution_options(autocommit=False))

    res = _dictfetchall(resultProxy) if as_dict is True else resultProxy.fetchall()
    resultProxy.close()
    return res


def db_exec(sql, args=None, using='default', debug=False):
    """Execute a raw query on the requested database connection."""
    from ..import DEBUG

    if args is None:
        args = tuple()

    using = _getRealShardConnectionName(using)

#    txCandidate = sql.strip().rstrip(';').strip().lower()
#    if txCandidate == 'begin':
#        logging.info('OPENING NEW TXN ......................')
#        _transactions[using] = connections()[using].begin()
#    elif txCandidate == 'rollback':
#        logging.info('ROLLING BACK TXN ......................')
#        _transactions[using].rollback()
#        del _transactions[using]
#    elif txCandidate == 'commit':
#        logging.info('COMMITTING TXN ......................')
#        _transactions[using].commit()
#        del _transactions[using]

    if DEBUG is True or debug is True:
        logging.info(u'-- [DEBUG] DB_EXEC, using={0} ::\n{1}'.format(using, sql))

    statement = sqlAndArgsToText(sql, args).execution_options(autocommit=False)
    #connections()[using].execute(statement)
    from app import ScopedSessions
    ScopedSessions[using]().execute(statement)


_saAttrsToPsql = (
    ('database', 'dbname', 'sendhub'),
    ('username', 'user', None),
    ('password', 'password', None),
    ('host', 'host', None),
    ('port', 'port', '5432'),
)


def getPsqlConnectionString(connectionName, secure=True):
    """Generate a PSQL-format connection string for a given connection."""
    assert connectionName in settings.DATABASE_URLS

    engine = connections()[connectionName]

    out = 'sslmode=require' if secure is True else ''

    psqlTuples = map(lambda (key, param, default): '{0}={1}'.format(param, getattr(engine.url, key) or default), _saAttrsToPsql)

    out = ' '.join(psqlTuples) + (' sslmode=require' if secure is True else '')
    return out
