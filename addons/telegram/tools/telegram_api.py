import logging

import requests

_logger = logging.getLogger(__name__)

API_URL = 'https://api.telegram.org'
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


class TelegramError(Exception):
    """ ``code`` is Telegram's error_code (0 for network errors); ``retry``
    tells the send queue to keep the message and try again later. """

    def __init__(self, description, code=0, retry=False):
        super().__init__(description)
        self.code = code
        self.retry = retry


class TelegramApi:
    """ Thin wrapper over the Bot API. Every call goes through the proxy set
    in ``telegram.proxy_url`` (api.telegram.org is filtered on our network). """

    def __init__(self, bot):
        bot.ensure_one()
        self.token = bot.sudo().token
        proxy = bot.env['ir.config_parameter'].sudo().get_param('telegram.proxy_url')
        self.proxies = {'http': proxy, 'https': proxy} if proxy else None

    def _mask(self, text):
        # requests puts the URL (and so the token) in its exception messages
        return str(text).replace(self.token, '***') if self.token else str(text)

    def _call(self, method, files=None, http_timeout=20, **payload):
        # http_timeout is the HTTP request's; a `timeout` in payload is Telegram's (getUpdates long poll)
        url = f'{API_URL}/bot{self.token}/{method}'
        try:
            if files:
                response = requests.post(url, data=payload, files=files, proxies=self.proxies, timeout=http_timeout)
            else:
                response = requests.post(url, json=payload, proxies=self.proxies, timeout=http_timeout)
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            raise TelegramError(self._mask(e), retry=True) from None
        if not data.get('ok'):
            code = data.get('error_code') or response.status_code
            raise TelegramError(data.get('description') or 'Unknown error', code, retry=code == 429 or code >= 500)
        return data['result']

    def get_me(self):
        return self._call('getMe')

    def get_updates(self, offset=0):
        return self._call('getUpdates', offset=offset, timeout=0, allowed_updates=['message'])

    def send_message(self, chat_id, text):
        return self._call('sendMessage', chat_id=chat_id, text=text[:MAX_TEXT_LENGTH])

    def send_document(self, chat_id, attachment, caption=''):
        files = {'document': (attachment.name, attachment.raw, attachment.mimetype)}
        return self._call('sendDocument', files=files, http_timeout=60, chat_id=chat_id, caption=caption[:MAX_CAPTION_LENGTH])

    def download_file(self, file_id):
        file_path = self._call('getFile', file_id=file_id)['file_path']
        try:
            response = requests.get(f'{API_URL}/file/bot{self.token}/{file_path}', proxies=self.proxies, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            raise TelegramError(self._mask(e), retry=True) from None
        return response.content
