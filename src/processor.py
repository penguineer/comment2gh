""" Module for comment processing """

import form
from github import GithubConfiguration, GithubUpload, GithubPR, GithubDefaultRef, GithubCreateBranch, GithubLabel

from typing import Optional

import logging

LOGGER = logging.getLogger(__name__)


class CommentFormatter(object):
    def __init__(self, cmt: form.Comment):
        if cmt is None:
            raise ValueError("Comment must not be None!")
        self._cmt = cmt

    def branch_name(self) -> str:
        return "comment-%s" % self._cmt.cid

    def file_content(self) -> str:
        return f"""\
id: %s
name: %s
email: %s
url: %s
date: %s
message: |
    %s

""" \
               % (self._cmt.cid,
                  self._cmt.name,
                  self._cmt.email,
                  self._cmt.url,
                  self._cmt.date,
                  self._cmt.message.rstrip('\n').replace('\n', '\n    '))

    def commit_path(self) -> str:
        return "_data/comments/%s/%s.yml" % (self._cmt.slug, self._cmt.cid)

    def commit_message(self) -> str:
        return "Comment %s" % self._cmt.cid

    def pr_title(self) -> str:
        return "Blog Comment %s" % self._cmt.cid

    def pr_body(self) -> str:
        return f"""\
Please consider this blog comment.

## Meta Data

Slug: %s
Date: %s
Name: %s
E-Mail: %s
URL: %s

## Message

%s""" % (
            self._cmt.slug,
            self._cmt.date,
            self._cmt.name,
            self._cmt.email,
            self._cmt.url,
            self._cmt.message
        )


class CommentProcessor(object):
    def __init__(self, cfg: GithubConfiguration):
        if cfg is None:
            raise ValueError("Configuration must be provided!")
        self._cfg = cfg

    async def comment_to_github_pr(self, cmt: form.Comment) -> Optional[int]:
        formatter = CommentFormatter(cmt)

        if not await self._create_branch(formatter):
            return None

        if not await self._upload_file(formatter):
            return None

        issue = await self._create_pr(formatter)

        # Failed label does not kill the whole process
        if issue and GithubLabel.applicable(self._cfg):
            if not await GithubLabel(self._cfg, issue).add():
                LOGGER.error("Could not add label!")

        return issue

    async def _create_branch(self, formatter) -> bool:
        main_head = await GithubDefaultRef(self._cfg).default_head()
        return await GithubCreateBranch(
            self._cfg,
            branch=formatter.branch_name(),
            sha=main_head
        ).create_branch()

    async def _upload_file(self, formatter) -> bool:
        return await GithubUpload(
            self._cfg,
            branch=formatter.branch_name(),
            path=formatter.commit_path(),
            message=formatter.commit_message(),
            committer_name=self._cfg.author,
            committer_email=self._cfg.email,
            content=formatter.file_content()
        ).upload()

    async def _create_pr(self, formatter) -> Optional[int]:
        return await GithubPR(
            cfg=self._cfg,
            head=formatter.branch_name(),
            base=self._cfg.branch,
            title=formatter.pr_title(),
            body=formatter.pr_body()
        ).create()
