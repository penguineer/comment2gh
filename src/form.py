""" Module for the form receiver """

from abc import ABCMeta
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Awaitable

import tornado.web

import os

from captcha import Recaptcha

import logging


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

    MAIL_OPTIONS = ["optional", "none", "required"]  # First value is used as default

    origin: str = DEFAULT_CORS_ORIGIN
    form_slug: str = DEFAULT_SLUG_FIELD
    form_name: str = DEFAULT_NAME_FIELD
    form_email: str = DEFAULT_EMAIL_FIELD
    form_url: str = DEFAULT_URL_FIELD
    form_message: str = DEFAULT_MESSAGE_FIELD
    mail_option: str = MAIL_OPTIONS[0]

    @staticmethod
    def from_environment():
        return FormConfiguration(
            origin=os.getenv("CORS_ORIGIN", FormConfiguration.DEFAULT_CORS_ORIGIN),
            form_slug=os.getenv("FORM_SLUG", FormConfiguration.DEFAULT_SLUG_FIELD),
            form_name=os.getenv('FORM_NAME', FormConfiguration.DEFAULT_NAME_FIELD),
            form_email=os.getenv('FORM_EMAIL', FormConfiguration.DEFAULT_EMAIL_FIELD),
            form_url=os.getenv("FORM_URL", FormConfiguration.DEFAULT_URL_FIELD),
            form_message=os.getenv('FORM_MESSAGE', FormConfiguration.DEFAULT_MESSAGE_FIELD),
            mail_option=os.getenv('FORM_EMAIL_CHECK', FormConfiguration.MAIL_OPTIONS[0])
        )

    def __post_init__(self):
        if self.origin is None:
            object.__setattr__(self, 'origin', '*')

        self._assert_field_values()
        self._assert_single_line_fields()

        if self.mail_option not in FormConfiguration.MAIL_OPTIONS:
            raise ValueError("FORM_EMAIL_CHECK (mail_option) must be one of %s", str(FormConfiguration.MAIL_OPTIONS))

    def _assert_field_values(self):
        req = [
            'form_slug',
            'form_name',
            'form_email',
            'form_url',
            'form_message',
            'mail_option'
        ]
        for attr in req:
            _assert_value(self.__getattribute__(attr), attr)

    def _assert_single_line_fields(self):
        sl = [
            'form_slug',
            'form_name',
            'form_email',
            'form_url'
        ]
        for attr in sl:
            val = self.__getattribute__(attr)
            if val is not None and '\n' in val:
                raise ValueError("Field %s must not have newlines!")


@dataclass(frozen=True)
class Comment:
    cid: int = field(init=False, default=0)
    date: str = field(init=False, default="")
    slug: str
    name: str
    message: str
    email: str = field(repr=False, default=None)
    url: Optional[str] = None

    def __post_init__(self):
        _assert_value(self.slug, "Post ID")
        _assert_value(self.name, "name")
        _assert_value(self.message, "message")

        super().__setattr__('date', str(datetime.now().isoformat()))
        super().__setattr__('cid', self.__hash__() % 1000000000)

    def delete_email(self):
        super().__setattr__('email', None)


class CommentHandler(tornado.web.RequestHandler, metaclass=ABCMeta):
    # noinspection PyAttributeOutsideInit,PyMethodOverriding
    def initialize(self,
                   cfg: FormConfiguration,
                   comment_cb: Callable[[Comment], Awaitable[int]],
                   recaptcha: Optional[Recaptcha] = None) -> None:
        """

        :param cfg: Handler configuration
        :param comment_cb: Callback to handle comments
        :param recaptcha: (Optional) Recaptcha verification handler
        """
        self._cfg = cfg
        self._cb = comment_cb
        self._recaptcha = recaptcha

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

    async def post(self):
        self.set_default_headers()  # Because it's not always happening
        self._validate_origin()

        try:
            comment = self._cmt_from_body()
            LOGGER.info("Processing comment %s", comment)

            self._handle_comment_mail(comment)

            if self._recaptcha:
                if not await self._validate_recaptcha():
                    LOGGER.warning("Could not validate reCAPTCHA response!")
                    raise tornado.web.HTTPError(status_code=400,
                                                reason="Invalid reCAPTCHA response!")
                else:
                    LOGGER.info("reCAPTCHA validation successful")

            pr = await self._call_cb(comment)

            self.set_status(201)
            await self.finish({
                "cid": comment.cid,
                "date": comment.date,
                "pr": pr
            })
        except ValueError as e:
            LOGGER.error("Invalid input from client: %s", str(e))
            raise tornado.web.HTTPError(status_code=400,
                                        reason=str(e))

    def _validate_origin(self):
        if self._cfg.origin == "*":
            return

        # Check if origin matches and match if none is provided
        if self._cfg.origin == self.request.headers.get("Origin", self._cfg.origin):
            return

        raise tornado.web.HTTPError(status_code=400,
                                    reason="Invalid origin!")

    async def _call_cb(self, comment):
        if not self._cb:
            raise tornado.web.HTTPError(status_code=500,
                                        reason="Comment processing not set up")

        pr = await self._cb(comment)
        if pr is None:
            raise tornado.web.HTTPError(status_code=500,
                                        reason="Comment processing failed")
        return pr

    async def _validate_recaptcha(self) -> bool:
        if not self._recaptcha:
            LOGGER.warning("reCAPTCHA check is not configured")
            return False

        response = self.get_body_argument(Recaptcha.RESPONSE_KEY, None)
        return await self._recaptcha.verify(response)

    def _cmt_from_body(self) -> Comment:
        return Comment(
            slug=self._arg_or_default(self._cfg.form_slug),
            name=self._arg_or_default(self._cfg.form_name),
            email=self._arg_or_default(self._cfg.form_email),
            message=self._arg_or_default(self._cfg.form_message),
            url=self._arg_or_default(self._cfg.form_url)
        )

    def _handle_comment_mail(self, comment):
        if self._cfg.mail_option == "required" and \
                not comment.email:
            raise ValueError("E-Mail address is required!")

        if self._cfg.mail_option == "none":
            comment.delete_email()

    def _arg_or_default(self, key, default=None):
        return default \
            if key not in self.request.body_arguments.keys() \
            else self.get_body_argument(key)
