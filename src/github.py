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

    @staticmethod
    def from_environment():
        return GithubConfiguration(
            user=os.getenv("GITHUB_USER", None),
            token=os.getenv("GITHUB_TOKEN", None),
            repository=os.getenv("GITHUB_REPOSITORY", None),
            email=os.getenv("GITHUB_EMAIL", None),
            author=os.getenv("GITHUB_AUTHOR", GithubConfiguration.DEFAULT_AUTHOR),
            branch=os.getenv("GITHUB_DEFAULT_BRANCH", GithubConfiguration.DEFAULT_BRANCH),

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


class GithubReferenceAccess(object):
    def __init__(self, cfg: GithubConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")
        self._cfg = cfg

    async def retrieve_default_head(self) -> Optional[str]:
        http_client = AsyncHTTPClient()

        req = HTTPRequest(
            url=f"https://api.github.com/repos/%s/%s/git/matching-refs/%s" % (
                self._cfg.user,
                self._cfg.repository,
                f"heads/%s" % self._cfg.branch
            ),
            headers=self._cfg.create_auth_header() | {
                "Accept": "application/vnd.github.v3+json"
            }
        )

        response = await http_client.fetch(req, raise_error=False)

        sha = None

        if response.code == 200:
            result = json.loads(response.body.decode("utf-8"))
            if len(result):
                sha = result[0]["object"]["sha"]
        else:
            LOGGER.error("Error %i when fetching ref id: %s", response.code, response.body)

        return sha

    async def create_branch(self, sha: str, branch: str) -> bool:
        http_client = AsyncHTTPClient()

        req = HTTPRequest(
            method="POST",
            url=f"https://api.github.com/repos/%s/%s/git/refs" % (
                self._cfg.user,
                self._cfg.repository
            ),
            headers=self._cfg.create_auth_header() | {
                "Accept": "application/vnd.github.v3+json"
            },
            body=json.dumps({
                "ref": f"refs/heads/%s" % branch,
                "sha": sha
            })
        )

        response = await http_client.fetch(req, raise_error=False)

        if response.code != 201:
            LOGGER.error("Error %i when creating ref id: %s", response.code, response.body)

        return response.code == 201


class GithubUpload(object):
    def __init__(self, cfg: GithubConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")
        self._cfg = cfg

    async def upload(self,
                     branch: str,
                     path: str,
                     message: str,
                     committer_name: str, committer_email: str,
                     content: str):
        b64 = base64.b64encode(content.encode("utf-8"))

        http_client = AsyncHTTPClient()

        req = HTTPRequest(
            method="PUT",
            url=f"https://api.github.com/repos/%s/%s/contents/%s" % (
                self._cfg.user,
                self._cfg.repository,
                path
            ),
            headers=self._cfg.create_auth_header() | {
                "Accept": "application/vnd.github.v3+json"
            },
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

        response = await http_client.fetch(req, raise_error=False)

        if response.code != 201:
            LOGGER.error("Error %i when uploading content: %s", response.code, response.body)

        return response.code == 201


class GithubPR(object):
    def __init__(self, cfg: GithubConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")
        self._cfg = cfg

    async def create_pr(self,
                        title: str,
                        head: str, base: str,
                        body: str,
                        maintainer_can_modify: Optional[bool] = True) -> Optional[int]:
        http_client = AsyncHTTPClient()

        req = HTTPRequest(
            method="POST",
            url=f"https://api.github.com/repos/%s/%s/pulls" % (
                self._cfg.user,
                self._cfg.repository
            ),
            headers=self._cfg.create_auth_header() | {
                "Accept": "application/vnd.github.v3+json"
            },
            body=json.dumps({
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "maintainer_can_modify": maintainer_can_modify
            })
        )

        response = await http_client.fetch(req, raise_error=False)

        if response.code != 201:
            LOGGER.error("Error %i when creating PR: %s", response.code, response.body)

        issue = None

        if response.code == 201:
            result = json.loads(response.body.decode("utf-8"))
            issue = result.get("number", None)

        return issue
