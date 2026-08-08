import contextlib
import functools
import re
import requests
import xmlrpc.client

from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)
TIMEOUT = 15


class FallbackToXmlrpc(Exception):
    pass


class ApiError(Exception):
    pass


class OdooDatabaseXmlrpcApi:
    def __init__(self, host, database, login, apikey):
        self.host = host
        self.database = database
        self.login = login
        self.apikey = apikey

    @contextlib.contextmanager
    def _handle_xmlrpc_errors(self):
        try:
            yield
        except xmlrpc.client.Fault as e:
            if f'FATAL:  database "{self.database}" does not exist' in e.faultString:
                raise ApiError(_lt('Database "%s" not found', self.database)) from e
            raise ApiError(e.faultString) from e
        except xmlrpc.client.Error as e:
            raise ApiError(str(e)) from e

    @functools.cached_property
    def xmlrpc_proxy(self):
        with self._handle_xmlrpc_errors():
            uid = xmlrpc.client.ServerProxy(f'{self.host}/xmlrpc/2/common').authenticate(self.database, self.login, self.apikey, {})

        proxy = xmlrpc.client.ServerProxy(f'{self.host}/xmlrpc/2/object')
        return uid, proxy

    def execute_kw(self, model, method, *args, **kwargs):
        uid, proxy = self.xmlrpc_proxy
        arguments = [self.database, uid, self.apikey, model, method, list(args)]
        if kwargs:
            arguments.append(kwargs)
        with self._handle_xmlrpc_errors():
            return proxy.execute_kw(*arguments)

    def list_internal_users(self):
        return self.execute_kw('res.users', 'search_read',
            [('share', '=', False)],  # internal users only
            ['name', 'login', 'login_date'],
        )

    def get_kpi_summary(self):
        return self.execute_kw('kpi.provider', 'get_kpi_summary')

    def get_database_uuid(self):
        return self.execute_kw('ir.config_parameter', 'get_param', 'database.uuid')

    def invite_users(self, emails):
        return self.execute_kw('res.users', 'web_create_users', emails=emails, context={'no_reset_password': True})

    def remove_users(self, logins):
        user_ids = self.execute_kw('res.users', 'search', [('login', 'in', logins)])
        return self.execute_kw('res.users', 'write', user_ids, {'active': False})


class BaseApi:
    def __init__(self, host, database, apikey):
        self.host = host
        self.database = database
        self.apikey = apikey

    def post_json2(self, model, method, **kwargs):
        try:
            headers = {'Authorization': f'Bearer {self.apikey}'}
            if self.database:
                headers['X-Odoo-Database'] = self.database

            response = requests.post(
                f'{self.host}/json/2/{model}/{method}',
                headers=headers,
                allow_redirects=False,
                json=kwargs,
                timeout=TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise ApiError(str(e)) from e

        try:
            if response.status_code == 200:
                return response.json()
            if 300 <= response.status_code < 400 or response.status_code == 404:
                raise FallbackToXmlrpc()

            raise ApiError(response.json()['message'])
        except ValueError as e:
            raise ApiError(f"{response.status_code} {response.reason}") from e


class OdooComApi(BaseApi):
    def list_databases(self):
        return self.post_json2('odoo.database', 'list')


class OdooDatabaseApi(BaseApi):
    def __init__(self, host, database, login, apikey):
        super().__init__(host, database, apikey)
        self.fallback = OdooDatabaseXmlrpcApi(host, database, login, apikey)
        self.use_fallback = False

    @classmethod
    def fetch_version(cls, database_url):
        try:
            response = requests.get(f'{database_url}/json/version', allow_redirects=False, timeout=TIMEOUT)
            if response.status_code == 200:
                if version := response.json().get('version'):
                    return _humanize_version(version)

            # Fallback to XML RPC call to common.version
            version = xmlrpc.client.ServerProxy(f'{database_url}/xmlrpc/2/common').version().get('server_serie')
            return _humanize_version(version)
        except (requests.exceptions.RequestException, xmlrpc.client.Error):
            return None

    @staticmethod
    def fallback_to_xmlrpc(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.use_fallback:
                try:
                    return method(self, *args, **kwargs)
                except FallbackToXmlrpc:
                    self.use_fallback = True

            fallback_method = getattr(self.fallback, method.__name__)
            return fallback_method(*args, **kwargs)
        return wrapper

    @fallback_to_xmlrpc
    def list_internal_users(self):
        return self.post_json2('res.users', 'search_read',
                               domain=[('share', '=', False)],  # internal users only
                               fields=['name', 'login', 'login_date'])

    @fallback_to_xmlrpc
    def get_kpi_summary(self):
        return self.post_json2('kpi.provider', 'get_kpi_summary')

    @fallback_to_xmlrpc
    def get_database_uuid(self):
        return self.post_json2('ir.config_parameter', 'get_param', key='database.uuid')

    @fallback_to_xmlrpc
    def invite_users(self, emails):
        return self.post_json2('res.users', 'web_create_users', emails=emails, context={'no_reset_password': True})

    @fallback_to_xmlrpc
    def remove_users(self, logins):
        user_ids = self.post_json2('res.users', 'search', domain=[('login', 'in', logins)])
        return self.post_json2('res.users', 'write', ids=user_ids, values={'active': False})


def _humanize_version(version):
    # only keep the series part from the version, e.g. 18.5a1+e becomes 18.5
    if m := re.match(r'^((:?saas[~-])?\d+.\d+)', version):
        return m.group(1).replace('-', '~')
