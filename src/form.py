""" Module for the form receiver """

from abc import ABCMeta
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import tornado.web

import os

import logging

LOG_FORMAT = '%(levelname) -10s %(asctime)s %(name) -15s %(lineno) -5d: %(message)s'
LOGGER = logging.getLogger(__name__)


def _assert_value(value, name):
    if not value:
        raise ValueError(f"Attribute %s is required, but was None!" % name)


@dataclass(frozen=True)
class FormConfiguration(object):
    """Configuration data for the comment handler"""
    DEFAULT_CORS_ORIGIN = "*"
    DEFAULT_SLUG_FIELD = "cmt_slug"
    DEFAULT_NAME_FIELD = "cmt_name"
    DEFAULT_EMAIL_FIELD = "cmt_email"
    DEFAULT_URL_FIELD = "cmt_url"
    DEFAULT_MESSAGE_FIELD = "cmt_message"

    origin: str = DEFAULT_CORS_ORIGIN
    form_slug: str = DEFAULT_SLUG_FIELD
    form_name: str = DEFAULT_NAME_FIELD
    form_email: str = DEFAULT_EMAIL_FIELD
    form_url: str = DEFAULT_URL_FIELD
    form_message: str = DEFAULT_MESSAGE_FIELD

    @staticmethod
    def from_environment():
        return FormConfiguration(
            origin=os.getenv("CORS_ORIGIN", FormConfiguration.DEFAULT_CORS_ORIGIN),
            form_slug=os.getenv("FORM_SLUG", FormConfiguration.DEFAULT_SLUG_FIELD),
            form_name=os.getenv('FORM_NAME', FormConfiguration.DEFAULT_NAME_FIELD),
            form_email=os.getenv('FORM_EMAIL', FormConfiguration.DEFAULT_EMAIL_FIELD),
            form_url=os.getenv("FORM_URL", FormConfiguration.DEFAULT_URL_FIELD),
            form_message=os.getenv('FORM_MESSAGE', FormConfiguration.DEFAULT_MESSAGE_FIELD)
        )

    def __post_init__(self):
        if self.origin is None:
            object.__setattr__(self, 'origin', '*')

        req = [
            'form_slug',
            'form_name',
            'form_email',
            'form_url',
            'form_message'
        ]
        for attr in req:
            _assert_value(self.__getattribute__(attr), attr)


@dataclass(frozen=True)
class Comment:
    cid: int = field(init=False, default=0)
    date: str = field(init=False, default="")
    slug: str
    name: str
    email: str
    message: str
    url: Optional[str] = None

    def __post_init__(self):
        _assert_value(self.slug, "Post ID")
        _assert_value(self.name, "name")
        _assert_value(self.email, "e-mail")
        _assert_value(self.message, "message")

        super().__setattr__('date', str(datetime.now().isoformat()))
        super().__setattr__('cid', self.__hash__() % 1000000000)


class CommentHandler(tornado.web.RequestHandler, metaclass=ABCMeta):
    # noinspection PyAttributeOutsideInit,PyMethodOverriding
    def initialize(self, cfg: FormConfiguration, comment_cb: Callable[[Comment], bool]) -> None:
        """

        :param cfg: Handler configuration
        :param comment_cb: Callback to handle comments
        """
        self._cfg = cfg
        self._cb = comment_cb

    def set_default_headers(self) -> None:
        # CORS headers have to be set here so that they are also available for error responses.
        # (Tornado clears the headers in case of an error and then calls this method.)

        # This weird behaviour is necessary because apparently this method is also called before initialize,
        # but we are supposed to not overwrite __init__ to create the attribute.
        if hasattr(self, "_cfg"):
            if self._cfg.origin:
                self.set_header("Access-Control-Allow-Origin", self._cfg.origin)
                self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def options(self):
        self.set_default_headers()  # Because it's not always happening
        self._validate_origin()
        self.set_status(204)
        self.finish()

    def post(self):
        self.set_default_headers()  # Because it's not always happening
        self._validate_origin()

        try:
            comment = self._cmt_from_body()
            LOGGER.info("Processing comment %s", comment)
            self._call_cb(comment)
        except ValueError as e:
            LOGGER.error("Invalid input from client: %s", str(e))
            raise tornado.web.HTTPError(status_code=400,
                                        reason=str(e))

        self.finish("OK")

    def _validate_origin(self):
        if self._cfg.origin == "*":
            return

        # Check if origin matches and match if none is provided
        if self._cfg.origin == self.request.headers.get("Origin", self._cfg.origin):
            return

        raise tornado.web.HTTPError(status_code=400,
                                    reason="Invalid origin!")

    def _call_cb(self, comment):
        if not self._cb:
            raise tornado.web.HTTPError(status_code=500,
                                        reason="Comment processing not set up")

        if not self._cb(comment):
            raise tornado.web.HTTPError(status_code=500,
                                        reason="Commend processing failed")

    def _cmt_from_body(self) -> Comment:
        return Comment(
            slug=self._arg_or_default(self._cfg.form_slug),
            name=self._arg_or_default(self._cfg.form_name),
            email=self._arg_or_default(self._cfg.form_email),
            message=self._arg_or_default(self._cfg.form_message),
            url=self._arg_or_default(self._cfg.form_url)
        )

    def _arg_or_default(self, key, default=None):
        return default \
            if key not in self.request.body_arguments.keys() \
            else self.get_body_argument(key)
