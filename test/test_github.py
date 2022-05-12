""" Test the processor module """
import json
from unittest import mock
import pytest

import os
import io

from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPRequest
from tornado.httpclient import HTTPResponse

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import github

MINIMAL_ENVIRONMENT = {
        "GITHUB_USER": "1",
        "GITHUB_TOKEN": "2",
        "GITHUB_REPOSITORY": "3",
        "GITHUB_EMAIL": "4"
    }


def setup_fetch(fetch_mock, status_code, body=None):
    def side_effect(request, **_kwargs):
        if request is not HTTPRequest:
            request = HTTPRequest(request)
        buffer = io.BytesIO(body.encode())
        response = HTTPResponse(request, status_code, None, buffer)
        future = Future()
        future.set_result(response)
        return future

    fetch_mock.side_effect = side_effect


class TestGithubConfiguration:
    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_minimal_config(self):
        cfg = github.GithubConfiguration.from_environment()

        assert cfg.user == "1"
        assert cfg.token == "2"
        assert cfg.repository == "3"
        assert cfg.email == "4"

        # default values
        assert cfg.author == "comment2gh Bot"
        assert cfg.branch == "main"

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
        "GITHUB_AUTHOR": "5",
        "GITHUB_DEFAULT_BRANCH": "6",
        "GITHUB_LABEL": "7"
    }, clear=True)
    def test_full_config(self):
        cfg = github.GithubConfiguration.from_environment()

        assert cfg.user == "1"
        assert cfg.token == "2"
        assert cfg.repository == "3"
        assert cfg.email == "4"
        assert cfg.author == "5"
        assert cfg.branch == "6"
        assert cfg.label == "7"

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

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_auth_headers(self):
        cfg = github.GithubConfiguration.from_environment()

        hdr = cfg.create_auth_header()

        assert len(hdr.keys()) == 1
        assert "Authorization" in hdr
        assert hdr["Authorization"] == "Basic MToy"  # Don't be a basic M toy with your credentials!


class TestGithubApiFunction:
    def test_assert_none(self):
        with pytest.raises(ValueError):
            github.GithubApiFunction.assert_cfg(None)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_assert_valid(self):
        cfg = github.GithubConfiguration.from_environment()
        github.GithubApiFunction.assert_cfg(cfg)
        assert True

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubApiFunction(None, url=None)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_null_url(self):
        cfg = github.GithubConfiguration.from_environment()
        with pytest.raises(ValueError):
            github.GithubApiFunction(cfg, url=None)
        with pytest.raises(ValueError):
            github.GithubApiFunction(cfg, url="")

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_minimal_args(self):
        cfg = github.GithubConfiguration.from_environment()
        f = github.GithubApiFunction(cfg, url="5")

        assert f._url == "5"

        hdr = f._headers()

        assert len(hdr.keys()) == 2
        assert "Authorization" in hdr
        assert hdr["Authorization"] == "Basic MToy"  # Don't be a basic M toy with your credentials!
        assert "Accept" in hdr
        assert hdr["Accept"] == "application/vnd.github.v3+json"

        assert f._method == "GET"
        assert f._body is None

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_full_args(self):
        cfg = github.GithubConfiguration.from_environment()

        for method in ["GET", "POST", "PUT"]:
            f = github.GithubApiFunction(cfg,
                                         url="5",
                                         method=method,
                                         body="6")
            assert f._url == "5"
            assert f._method == method
            assert f._body == "6"

            r = f._request()
            assert r.url == "5"
            assert r.method == method
            assert len(r.headers) == 2
            assert r.body == b"6"

    @pytest.mark.asyncio
    async def test_fetch(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            f = github.GithubApiFunction(cfg, url="5")

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 200, "{}")
                code, body = await f._fetch()
                assert code == 200
                assert body == {}

                with pytest.raises(json.decoder.JSONDecodeError):
                    setup_fetch(fetch_mock, 200, "OK")
                    await f._fetch()


class TestGithubDefaultRef:
    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubDefaultRef(None)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_minimal_request(self):
        cfg = github.GithubConfiguration.from_environment()
        dr = github.GithubDefaultRef(cfg)

        r = dr._request()

        assert r.url == "https://api.github.com/repos/1/3/git/matching-refs/heads/main"
        assert r.method == "GET"
        assert r.body is None

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
        "GITHUB_DEFAULT_BRANCH": "6"
    }, clear=True)
    def test_full_request(self):
        cfg = github.GithubConfiguration.from_environment()
        dr = github.GithubDefaultRef(cfg)

        r = dr._request()

        assert r.url == "https://api.github.com/repos/1/3/git/matching-refs/heads/6"
        assert r.method == "GET"
        assert r.body is None

    @pytest.mark.asyncio
    async def test_fetch_found(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            dr = github.GithubDefaultRef(cfg)

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 200, json.dumps([{
                    "object": {
                        "sha": "123"
                    }
                }]))
                head = await dr.default_head()

                assert head == "123"

    @pytest.mark.asyncio
    async def test_fetch_not_found(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            dr = github.GithubDefaultRef(cfg)

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 404, "{}")
                head = await dr.default_head()

                assert head is None

    @pytest.mark.asyncio
    async def test_fetch_weird_structures(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            dr = github.GithubDefaultRef(cfg)

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 200, json.dumps({}))
                head = await dr.default_head()
                assert head is None

                setup_fetch(fetch_mock, 200, json.dumps([]))
                head = await dr.default_head()
                assert head is None

                setup_fetch(fetch_mock, 200, json.dumps({
                    "object": {}
                }))
                head = await dr.default_head()
                assert head is None

                setup_fetch(fetch_mock, 200, json.dumps([{
                    "object": {
                        "sha2": "123"
                    }
                }]))
                head = await dr.default_head()
                assert head is None

                setup_fetch(fetch_mock, 200, json.dumps([{
                    "object": {
                        "sha": None
                    }
                }]))
                head = await dr.default_head()
                assert head is None


class TestGithubCreateBranch:
    ARGS = {
        "cfg": None,
        "sha": "7",
        "branch": "8"
    }

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubCreateBranch(**TestGithubCreateBranch.ARGS)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_request(self):
        cfg = github.GithubConfiguration.from_environment()
        cb = github.GithubCreateBranch(**TestGithubCreateBranch.ARGS | {"cfg": cfg})

        r = cb._request()

        assert r.url == "https://api.github.com/repos/1/3/git/refs"
        assert r.method == "POST"
        assert r.body == b'{"ref": "refs/heads/8", "sha": "7"}'

    @pytest.mark.asyncio
    async def test_fetch(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            cb = github.GithubCreateBranch(**TestGithubCreateBranch.ARGS | {"cfg": cfg})

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 201, "{}")
                success = await cb.create_branch()
                assert success

                setup_fetch(fetch_mock, 400, "{}")
                success = await cb.create_branch()
                assert not success


class TestGithubUpload:
    ARGS = {
        "cfg": None,
        "branch": "7",
        "path": "8/a.yml",
        "message": "9",
        "committer_name": "10",
        "committer_email": "11",
        "content": "12"
    }

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubUpload(**TestGithubUpload.ARGS)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_request(self):
        cfg = github.GithubConfiguration.from_environment()
        u = github.GithubUpload(**TestGithubUpload.ARGS | {"cfg": cfg})

        r = u._request()

        assert r.url == "https://api.github.com/repos/1/3/contents/8/a.yml"
        assert r.method == "PUT"
        assert r.body == \
               b'{"branch": "7", "message": "9", "committer": {"name": "10", "email": "11"}, "content": "MTI="}'

    @pytest.mark.asyncio
    async def test_fetch(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            u = github.GithubUpload(**TestGithubUpload.ARGS | {"cfg": cfg})

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 201, "{}")
                success = await u.upload()
                assert success

                setup_fetch(fetch_mock, 400, "{}")
                success = await u.upload()
                assert not success


class TestGithubPR:
    ARGS = {
        "cfg": None,
        "title": "7",
        "head": "8",
        "base": "9",
        "body": "10",
        "maintainer_can_modify": True
    }

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubPR(**TestGithubPR.ARGS)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_request(self):
        cfg = github.GithubConfiguration.from_environment()
        pr = github.GithubPR(**TestGithubPR.ARGS | {"cfg": cfg})

        r = pr._request()

        assert r.url == "https://api.github.com/repos/1/3/pulls"
        assert r.method == "POST"
        assert r.body == \
               b'{"title": "7", "head": "8", "base": "9", "body": "10", "maintainer_can_modify": true}'

    @pytest.mark.asyncio
    async def test_fetch(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            pr = github.GithubPR(**TestGithubPR.ARGS | {"cfg": cfg})

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 201, json.dumps({
                    "number": 123
                }))
                issue = await pr.create()
                assert issue == 123

                setup_fetch(fetch_mock, 201, "{}")
                issue = await pr.create()
                assert issue is None

                setup_fetch(fetch_mock, 400, "{}")
                issue = await pr.create()
                assert issue is None


class TestGithubLabel:
    ARGS = {
        "cfg": None,
        "issue": 4
    }

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_not_applicable(self):
        assert not github.GithubLabel.applicable(None)
        assert not github.GithubLabel.applicable(
            github.GithubConfiguration.from_environment())

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
        "GITHUB_LABEL": "5"
    }, clear=True)
    def test_applicable(self):
        assert github.GithubConfiguration.from_environment()

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            github.GithubLabel(**TestGithubLabel.ARGS)

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT, clear=True)
    def test_null_label(self):
        cfg = github.GithubConfiguration.from_environment()
        with pytest.raises(ValueError):
            github.GithubLabel(**TestGithubLabel.ARGS | {"cfg": cfg})

    @mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
        "GITHUB_LABEL": "5"
    }, clear=True)
    def test_request(self):
        cfg = github.GithubConfiguration.from_environment()
        lab = github.GithubLabel(**TestGithubLabel.ARGS | {"cfg": cfg})

        r = lab._request()

        assert r.url == "https://api.github.com/repos/1/3/issues/4/labels"
        assert r.method == "POST"
        assert r.body == \
               b'{"labels": ["5"]}'

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
            "GITHUB_LABEL": "5"
        }, clear=True):
            cfg = github.GithubConfiguration.from_environment()
            lab = github.GithubLabel(**TestGithubLabel.ARGS | {"cfg": cfg})

            with mock.patch.object(AsyncHTTPClient, 'fetch') as fetch_mock:
                setup_fetch(fetch_mock, 200, "{}")
                assert await lab.add()

                setup_fetch(fetch_mock, 410, "{}")
                assert not await lab.add()

                setup_fetch(fetch_mock, 422, "{}")
                assert not await lab.add()
