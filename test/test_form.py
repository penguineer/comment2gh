""" Test the form module """

from unittest import mock
import pytest

import os

import tornado.testing
from urllib.parse import urlencode

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import form
# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
from app import make_app


class TestFormConfiguration:
    @staticmethod
    def _assert_default_values(cfg):
        assert cfg.origin == "*"
        assert cfg.form_slug == "cmt_slug"
        assert cfg.form_name == "cmt_name"
        assert cfg.form_email == "cmt_email"
        assert cfg.form_url == "cmt_url"
        assert cfg.form_message == "cmt_message"

    def test_default_init(self):
        cfg = form.FormConfiguration()
        TestFormConfiguration._assert_default_values(cfg)

    def test_empty_origin(self):
        cfg = form.FormConfiguration(
            origin=None
        )
        TestFormConfiguration._assert_default_values(cfg)

    def test_empty_required(self):
        with pytest.raises(ValueError):
            form.FormConfiguration(form_slug=None)
        with pytest.raises(ValueError):
            form.FormConfiguration(form_name=None)
        with pytest.raises(ValueError):
            form.FormConfiguration(form_email=None)
        with pytest.raises(ValueError):
            form.FormConfiguration(form_url=None)
        with pytest.raises(ValueError):
            form.FormConfiguration(form_message=None)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_empty_env(self):
        cfg = form.FormConfiguration.from_environment()
        TestFormConfiguration._assert_default_values(cfg)

    @mock.patch.dict(os.environ, {
        "CORS_ORIGIN": "1",
        "FORM_SLUG": "2",
        "FORM_NAME": "3",
        "FORM_EMAIL": "4",
        "FORM_URL": "5",
        "FORM_MESSAGE": "6",
    }, clear=True)
    def test_env(self):
        cfg = form.FormConfiguration.from_environment()
        assert cfg.origin == "1"
        assert cfg.form_slug == "2"
        assert cfg.form_name == "3"
        assert cfg.form_email == "4"
        assert cfg.form_url == "5"
        assert cfg.form_message == "6"


class TestComment:
    def test_empty_init(self):
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "message": "4"
        }
        for key in values.keys():
            args = dict(values)
            args[key] = None
            with pytest.raises(ValueError):
                form.Comment(**args)

    def test_minimal_init(self):
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "message": "4"
        }

        cmt = form.Comment(**values)

        assert cmt.slug == "1"
        assert cmt.name == "2"
        assert cmt.email == "3"
        assert cmt.message == "4"
        assert cmt.url is None
        # These are auto-generated. Check that they have values
        assert cmt.date is not None
        assert cmt.cid is not None

    def test_complete_init(self):
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "message": "4",
            "url": "5"
        }

        cmt = form.Comment(**values)

        assert cmt.slug == "1"
        assert cmt.name == "2"
        assert cmt.email == "3"
        assert cmt.message == "4"
        assert cmt.url == "5"
        # These are auto-generated. Check that they have values
        assert cmt.date is not None
        assert cmt.cid is not None


class TestCommentHandler(tornado.testing.AsyncHTTPTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cmt = None
        self._cmt_return = 1

    def comment_cb(self, cmt: form.Comment):
        self._cmt = cmt
        return self._cmt_return

    def get_app(self):
        return make_app(cmt_cfg=form.FormConfiguration(),
                        comment_cb=self.comment_cb)

    def test_form_post_ok(self):
        form = {
            "cmt_slug": "1",
            "cmt_name": "2",
            "cmt_email": "3",
            "cmt_message": "4",
            "cmt_url": "5"
        }
        self._cmt = None
        self._cmt_return = 1

        body = urlencode(form)
        response = self.fetch('/v0/comment',
                              method='POST',
                              body=body)
        assert response.code == 200
        assert self._cmt is not None

        assert self._cmt.slug == "1"
        assert self._cmt.name == "2"
        assert self._cmt.email == "3"
        assert self._cmt.message == "4"
        assert self._cmt.url == "5"
        # These are auto-generated. Check that they have values
        assert self._cmt.date is not None
        assert self._cmt.cid is not None

        assert response.headers['Access-Control-Allow-Origin'] == "*"
        assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"

    def test_form_processing_failed(self):
        form = {
            "cmt_slug": "1",
            "cmt_name": "2",
            "cmt_email": "3",
            "cmt_message": "4",
            "cmt_url": "5"
        }
        self._cmt = None
        self._cmt_return = None

        body = urlencode(form)
        response = self.fetch('/v0/comment',
                              method='POST',
                              body=body)
        assert response.code == 500
        assert self._cmt is not None

        assert response.headers['Access-Control-Allow-Origin'] == "*"
        assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"

    def test_missing_value(self):
        form = {
            "cmt_slug": "1",
            "cmt_name": "2",
            "cmt_email": "3",
            "cmt_message": "4"
        }
        self._cmt_return = 1

        for key in form.keys():
            reduced = dict(form)
            del reduced[key]

            self._cmt = None

            body = urlencode(reduced)
            response = self.fetch('/v0/comment',
                                  method='POST',
                                  body=body)
            assert response.code == 400
            assert self._cmt is None

            assert response.headers['Access-Control-Allow-Origin'] == "*"
            assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"

    def test_options_cors_ok(self):
        response = self.fetch('/v0/comment',
                              method='OPTIONS',
                              headers={
                                  "Origin": "localhost"
                              })

        assert response.code == 204
        assert response.headers['Access-Control-Allow-Origin'] == "*"
        assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"


class TestCommentHandlerSpecialOrigin(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        return make_app(cmt_cfg=form.FormConfiguration(origin="localhost"),
                        comment_cb=None)

    def test_options_cors_ok(self):
        response = self.fetch('/v0/comment',
                              method='OPTIONS',
                              headers={
                                  "Origin": "localhost"
                              })

        assert response.code == 204
        assert response.headers['Access-Control-Allow-Origin'] == "localhost"
        assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"

    def test_options_cors_invalid(self):
        response = self.fetch('/v0/comment',
                              method='OPTIONS',
                              headers={
                                  "Origin": "somewhere"
                              })

        assert response.code == 400
        assert response.headers['Access-Control-Allow-Origin'] == "localhost"
        assert response.headers['Access-Control-Allow-Methods'] == "POST, OPTIONS"
