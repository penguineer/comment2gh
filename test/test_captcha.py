""" Test the recaptcha module """

from unittest import mock
import pytest

import os

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import captcha


class TestRecaptchaConfiguration:
    @mock.patch.dict(os.environ, {
        "RECAPTCHA_SECRET": "1"
    }, clear=True)
    def test_full_config(self):
        cfg = captcha.RecaptchaConfiguration.from_environment()

        assert cfg.is_enabled()
        assert cfg.secret == "1"

    @mock.patch.dict(os.environ, {
    }, clear=True)
    def test_empty_config(self):
        cfg = captcha.RecaptchaConfiguration.from_environment()

        assert not cfg.is_enabled()
        assert cfg.secret is None


class TestRecaptcha:
    def test_req_create_normal(self):
        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        req = recaptcha._create_request("2")

        assert req.url == "https://www.google.com/recaptcha/api/siteverify?secret=1&response=2"

    def test_req_response_missing(self):
        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        with pytest.raises(ValueError):
            recaptcha._create_request(None)

    def test_res_positive(self):
        body = b"""
{
    "success": true
}        
        """
        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        assert recaptcha._process_result(body)

    def test_res_negative(self):
        body = b"""
{
    "success": false
}        
        """

        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        assert not recaptcha._process_result(body)

    def test_res_missing(self):
        body = b"{}"

        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        assert not recaptcha._process_result(body)

    def test_res_invalid_json(self):
        body = b"not json"

        cfg = captcha.RecaptchaConfiguration(secret="1")
        recaptcha = captcha.Recaptcha(cfg)

        assert not recaptcha._process_result(body)

# TODO mock test for captcha verification call
