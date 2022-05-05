""" Test the processor module """
from unittest import mock
import pytest

import os

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import github


class TestGithubConfiguration:
    @mock.patch.dict(os.environ, {
        "GITHUB_USER": "1",
        "GITHUB_TOKEN": "2",
        "GITHUB_REPOSITORY": "3",
        "GITHUB_EMAIL": "4"
    }, clear=True)
    def test_minimal_config(self):
        cfg = github.GithubConfiguration.from_environment()

        assert cfg.user == "1"
        assert cfg.token == "2"
        assert cfg.repository == "3"
        assert cfg.email == "4"

        # default values
        assert cfg.author == "comment2gh Bot"
        assert cfg.branch == "main"

    @mock.patch.dict(os.environ, {
        "GITHUB_USER": "1",
        "GITHUB_TOKEN": "2",
        "GITHUB_REPOSITORY": "3",
        "GITHUB_AUTHOR": "4",
        "GITHUB_EMAIL": "5",
        "GITHUB_DEFAULT_BRANCH": "6"
    }, clear=True)
    def test_full_config(self):
        cfg = github.GithubConfiguration.from_environment()

        assert cfg.user == "1"
        assert cfg.token == "2"
        assert cfg.repository == "3"
        assert cfg.author == "4"
        assert cfg.email == "5"
        assert cfg.branch == "6"

    def test_missing_values(self):
        values = {
            "user": "1",
            "token": "2",
            "repository": "3",
            "email": "4"
        }
        for key in values.keys():
            args = dict(values)
            args[key] = None
            with pytest.raises(ValueError):
                github.GithubConfiguration(**args)

    def test_empty_required(self):
        values = {
            "user": "1",
            "token": "2",
            "repository": "3",
            "email": "4"
        }
        with pytest.raises(ValueError):
            github.GithubConfiguration(author=None, **values)
        with pytest.raises(ValueError):
            github.GithubConfiguration(branch=None, **values)

    @mock.patch.dict(os.environ, {
        "GITHUB_USER": "1",
        "GITHUB_TOKEN": "2",
        "GITHUB_REPOSITORY": "3",
        "GITHUB_EMAIL": "4"
    }, clear=True)
    def test_auth_headers(self):
        cfg = github.GithubConfiguration.from_environment()

        hdr = cfg.create_auth_header()

        assert len(hdr.keys()) == 1
        assert "Authorization" in hdr
        assert hdr["Authorization"] == "Basic MToy"  # Don't be a basic M toy with your credentials!


class TestGithubReferenceAccess:
    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubReferenceAccess(None)

# TODO mock tests here


class TestGithubUpload:
    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubUpload(None)

# TODO mock tests here


class TestGithubPR:
    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubPR(None)

# TODO mock tests here
