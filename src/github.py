""" Module for GitHub API access

There are available libraries for accessing the GitHub API.
However, there is not a lot of documentation. It turned out to be easier to call the API directly.
"""

from dataclasses import dataclass
from typing import Optional

import base64
import json
import os

import logging

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

LOGGER = logging.getLogger(__name__)


def _assert_value(value, name):
    if not value:
        raise ValueError(f"Attribute %s is required, but was None!" % name)


@dataclass(frozen=True)
class GithubConfiguration(object):
    DEFAULT_BRANCH = "main"
    DEFAULT_AUTHOR = "comment2gh Bot"

    user: str
    token: str
    repository: str
    email: str
    author: str = DEFAULT_AUTHOR
    branch: str = DEFAULT_BRANCH
    label: str = None

    @staticmethod
    def from_environment():
        return GithubConfiguration(
            user=os.getenv("GITHUB_USER", None),
            token=os.getenv("GITHUB_TOKEN", None),
            repository=os.getenv("GITHUB_REPOSITORY", None),
            email=os.getenv("GITHUB_EMAIL", None),
            author=os.getenv("GITHUB_AUTHOR", GithubConfiguration.DEFAULT_AUTHOR),
            branch=os.getenv("GITHUB_DEFAULT_BRANCH", GithubConfiguration.DEFAULT_BRANCH),
            label=os.getenv("GITHUB_LABEL", None)
        )

    def __post_init__(self):
        for attr in [
            'user',
            'token',
            'repository',
            'email',
            'author',
            'branch'
        ]:
            _assert_value(self.__getattribute__(attr), attr)

    def create_auth_header(self):
        auth = f"%s:%s" % (self.user, self.token)
        b64 = base64.b64encode(auth.encode("utf-8"))
        return {
            "Authorization": f"Basic %s" % b64.decode("utf-8")
        }


class GithubApiFunction(object):

    @staticmethod
    def assert_cfg(cfg: GithubConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")

    def __init__(
            self,
            cfg: GithubConfiguration,
            url: str,
            method="GET",
            body=None
    ):
        GithubApiFunction.assert_cfg(cfg)
        self._cfg = cfg

        if not url:
            raise ValueError("URL must be provided!")
        self._url = url

        self._method = method
        self._body = body

    def _headers(self):
        return self._cfg.create_auth_header() | {
            "Accept": "application/vnd.github.v3+json"
        }

    def _request(self):
        return HTTPRequest(
            method=self._method,
            url=self._url,
            headers=self._headers(),
            body=self._body
        )

    async def _fetch(self):
        result = await AsyncHTTPClient().fetch(
            self._request(),
            raise_error=False
        )

        body = json.loads(result.body.decode("utf-8")) if result.body is not None else None
        return result.code, body


class GithubDefaultRef(GithubApiFunction):
    def __init__(self,
                 cfg: GithubConfiguration):
        GithubApiFunction.assert_cfg(cfg)
        super().__init__(
            cfg,
            url=f"https://api.github.com/repos/%s/%s/git/matching-refs/%s" % (
                cfg.user,
                cfg.repository,
                f"heads/%s" % cfg.branch  # Could be optimized, but that would hide the API endpoint URL
            )
        )

    async def default_head(self) -> Optional[str]:
        code, body = await self._fetch()

        if code != 200:
            LOGGER.error("Error %i when fetching ref id: %s", code, str(body))
            return None

        return GithubDefaultRef._sha(body)

    @staticmethod
    def _sha(body):
        try:
            return body[0]["object"]["sha"] if len(body) else None
        except KeyError as e:
            LOGGER.warning("Got weird result from GitHub, error: %s", e)
            return None


class GithubCreateBranch(GithubApiFunction):
    def __init__(self,
                 cfg: GithubConfiguration,
                 sha: str,
                 branch: str):
        GithubApiFunction.assert_cfg(cfg)
        super().__init__(
            cfg,
            url=f"https://api.github.com/repos/%s/%s/git/refs" % (
                cfg.user,
                cfg.repository
            ),
            method="POST",
            body=json.dumps({
                "ref": f"refs/heads/%s" % branch,
                "sha": sha
            })
        )

    async def create_branch(self) -> bool:
        code, body = await self._fetch()

        if code != 201:
            LOGGER.error("Error %i when creating ref id: %s", code, str(body))

        return code == 201


class GithubUpload(GithubApiFunction):
    def __init__(self,
                 cfg: GithubConfiguration,
                 branch: str,
                 path: str,
                 message: str,
                 committer_name: str, committer_email: str,
                 content: str):
        GithubApiFunction.assert_cfg(cfg)
        b64 = base64.b64encode(content.encode("utf-8"))
        super().__init__(
            cfg,
            url=f"https://api.github.com/repos/%s/%s/contents/%s" % (
                cfg.user,
                cfg.repository,
                path
            ),
            method="PUT",
            body=json.dumps({
                "branch": branch,
                "message": message,
                "committer": {
                    "name": committer_name,
                    "email": committer_email
                },
                "content": b64.decode("utf-8")
            })
        )

    async def upload(self):
        code, body = await self._fetch()

        if code != 201:
            LOGGER.error("Error %i when uploading content: %s", code, str(body))

        return code == 201


class GithubPR(GithubApiFunction):
    def __init__(self,
                 cfg: GithubConfiguration,
                 title: str,
                 head: str, base: str,
                 body: str,
                 maintainer_can_modify: Optional[bool] = True):
        GithubApiFunction.assert_cfg(cfg)
        super().__init__(
            cfg,
            url=f"https://api.github.com/repos/%s/%s/pulls" % (
                cfg.user,
                cfg.repository
            ),
            method="POST",
            body=json.dumps({
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "maintainer_can_modify": maintainer_can_modify
            })
        )

    async def create(self) -> Optional[int]:
        code, body = await self._fetch()

        if code != 201:
            LOGGER.error("Error %i when creating PR: %s", code, str(body))
            return None

        return self._issue(body)

    @staticmethod
    def _issue(body):
        return body.get("number", None)


class GithubLabel(GithubApiFunction):
    @staticmethod
    def applicable(cfg: GithubConfiguration) -> bool:
        return cfg is not None and cfg.label

    def __init__(self,
                 cfg: GithubConfiguration,
                 issue: int):
        GithubApiFunction.assert_cfg(cfg)
        if not GithubLabel.applicable(cfg):
            raise ValueError("Cannot create label handler without configured label!")
        super().__init__(
            cfg,
            url=f"https://api.github.com/repos/%s/%s/issues/%s/labels" % (
                cfg.user,
                cfg.repository,
                str(issue)
            ),
            method="POST",
            body=json.dumps({
                "labels": [cfg.label]
            })
        )

    async def add(self) -> bool:
        code, body = await self._fetch()

        if code == 410:
            LOGGER.error("Add label: Issue is gone! %s", str(body))
            return False

        if code == 422:
            LOGGER.error("Add label: Validation failed! %s", str(body))

        return code == 200
