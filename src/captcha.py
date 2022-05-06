""" Module for Google reCaptcha v2 processing """

from dataclasses import dataclass

import json
import os

from tornado.escape import url_escape
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

import logging

LOGGER = logging.getLogger(__name__)


def _assert_value(value, name):
    if not value:
        raise ValueError(f"Attribute %s is required, but was None!" % name)


@dataclass(frozen=True)
class RecaptchaConfiguration(object):
    secret: str = None

    @staticmethod
    def from_environment():
        return RecaptchaConfiguration(
            secret=os.getenv("RECAPTCHA_SECRET", None)
        )

    def is_enabled(self):
        return self.secret is not None


class Recaptcha(object):
    RESPONSE_KEY = "g-recaptcha-response"

    def __init__(self, cfg: RecaptchaConfiguration):
        if cfg is None:
            raise ValueError("Recaptcha configuration must be provided!")
        self._cfg = cfg

    async def verify(self, captcha_response: str) -> bool:
        response = await AsyncHTTPClient().fetch(
            self._create_request(captcha_response)
        )

        return Recaptcha._process_result(response.body)

    def _create_request(self, captcha_response: str):
        if not captcha_response:
            raise ValueError("Captcha Response must be provided!")

        return HTTPRequest(
            method="POST",
            url=f"https://www.google.com/recaptcha/api/siteverify?secret=%s&response=%s" % (
                url_escape(self._cfg.secret),
                url_escape(captcha_response)
            ),
            allow_nonstandard_methods=True
        )

    @staticmethod
    def _process_result(body) -> bool:
        try:
            response = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            LOGGER.warning("Error when decoding reCAPTCHA response: %s", str(e))
            return False

        success = bool(response.get("success", False))

        if not success:
            LOGGER.warning("Failed captcha: %s" + str(response))

        return success
