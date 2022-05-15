""" Test the processor module """

import pytest
from unittest import mock

import os

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import form
# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import processor
# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import github


class TestCommentFormatter:
    def test_null_comment(self):
        with pytest.raises(ValueError):
            processor.CommentFormatter(None)

    def test_full_comment(self):
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "url": "4",
            "message": "5"
        }
        cmt = form.Comment(**values)
        formatter = processor.CommentFormatter(cmt)

        assert formatter.branch_name() == "comment-" + str(cmt.cid)
        assert formatter.file_content() == """\
id: """ + str(cmt.cid) + """
name: 2
email: 3
url: 4
date: """ + cmt.date + """
message: |
    5

"""
        assert formatter.commit_path() == "_data/comments/" + cmt.slug + "/" + str(cmt.cid) + ".yml"
        assert formatter.commit_message() == "Comment " + str(cmt.cid)
        assert formatter.pr_title() == "Blog Comment " + str(cmt.cid)
        assert formatter.pr_body() == """\
Please consider this blog comment.

## Meta Data

Slug: 1
Date: """ + cmt.date + """
Name: 2
E-Mail: 3
URL: 4

## Message

5"""

    def test_multiline_comment(self):
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "url": "4",
            "message": """\
This
is
a

multiline
message.
"""
        }
        cmt = form.Comment(**values)
        formatter = processor.CommentFormatter(cmt)

        assert formatter.file_content() == """\
id: """ + str(cmt.cid) + """
name: 2
email: 3
url: 4
date: """ + cmt.date + """
message: |
    This
    is
    a
    
    multiline
    message.

"""

        assert formatter.pr_body() == """\
Please consider this blog comment.

## Meta Data

Slug: 1
Date: """ + cmt.date + """
Name: 2
E-Mail: 3
URL: 4

## Message

This
is
a

multiline
message.
"""


MINIMAL_ENVIRONMENT = {
        "GITHUB_USER": "1",
        "GITHUB_TOKEN": "2",
        "GITHUB_REPOSITORY": "3",
        "GITHUB_EMAIL": "4"
    }


def setup_call_0arg(call_mock, result):
    def side_effect(**_kwargs):
        return result

    call_mock.side_effect = side_effect


def setup_call_1arg(call_mock, result):
    def side_effect(_formatter, **_kwargs):
        return result

    call_mock.side_effect = side_effect


class TestCommentProcessor:
    @staticmethod
    def _create_cfg():
        with mock.patch.dict(os.environ, MINIMAL_ENVIRONMENT | {
            "GITHUB_LABEL": "5"
        }, clear=True):
            return github.GithubConfiguration.from_environment()

    @staticmethod
    def _create_cmt():
        values = {
            "slug": "1",
            "name": "2",
            "email": "3",
            "url": "4",
            "message": "5"
        }
        return form.Comment(**values)

    def test_null_cfg(self):
        with pytest.raises(ValueError):
            processor.CommentProcessor(None)

    @pytest.mark.asyncio
    async def test_no_branch(self):
        cfg = TestCommentProcessor._create_cfg()
        cmt = TestCommentProcessor._create_cmt()

        with mock.patch.object(processor.CommentProcessor, '_create_branch') as branch_mock:
            setup_call_1arg(branch_mock, False)
            proc = processor.CommentProcessor(cfg)
            assert await proc.comment_to_github_pr(cmt) is None

    @pytest.mark.asyncio
    async def test_no_upload(self):
        cfg = TestCommentProcessor._create_cfg()
        cmt = TestCommentProcessor._create_cmt()
        with mock.patch.object(processor.CommentProcessor, '_create_branch') as branch_mock:
            setup_call_1arg(branch_mock, True)
            with mock.patch.object(processor.CommentProcessor, '_upload_file') as upload_mock:
                setup_call_1arg(upload_mock, False)
                proc = processor.CommentProcessor(cfg)
                issue = await proc.comment_to_github_pr(cmt)
                assert issue is None

    @pytest.mark.asyncio
    async def test_no_issue(self):
        cfg = TestCommentProcessor._create_cfg()
        cmt = TestCommentProcessor._create_cmt()
        with mock.patch.object(processor.CommentProcessor, '_create_branch') as branch_mock:
            setup_call_1arg(branch_mock, True)
            with mock.patch.object(processor.CommentProcessor, '_upload_file') as upload_mock:
                setup_call_1arg(upload_mock, True)
                with mock.patch.object(processor.CommentProcessor, '_create_pr') as pr_mock:
                    setup_call_1arg(pr_mock, None)
                    proc = processor.CommentProcessor(cfg)
                    issue = await proc.comment_to_github_pr(cmt)
                    assert issue is None

    @pytest.mark.asyncio
    async def test_with_issue(self):
        cfg = TestCommentProcessor._create_cfg()
        cmt = TestCommentProcessor._create_cmt()
        with mock.patch.object(processor.CommentProcessor, '_create_branch') as branch_mock:
            setup_call_1arg(branch_mock, True)
            with mock.patch.object(processor.CommentProcessor, '_upload_file') as upload_mock:
                setup_call_1arg(upload_mock, True)
                with mock.patch.object(processor.CommentProcessor, '_create_pr') as pr_mock:
                    setup_call_1arg(pr_mock, "1")
                    proc = processor.CommentProcessor(cfg)
                    issue = await proc.comment_to_github_pr(cmt)
                    assert issue == "1"

    @pytest.mark.asyncio
    async def test_with_label_fail(self):
        cfg = TestCommentProcessor._create_cfg()
        cmt = TestCommentProcessor._create_cmt()
        with mock.patch.object(processor.CommentProcessor, '_create_branch') as branch_mock:
            setup_call_1arg(branch_mock, True)
            with mock.patch.object(processor.CommentProcessor, '_upload_file') as upload_mock:
                setup_call_1arg(upload_mock, True)
                with mock.patch.object(processor.CommentProcessor, '_create_pr') as pr_mock:
                    setup_call_1arg(pr_mock, "1")
                    with mock.patch.object(github.GithubLabel, 'add') as label_mock:
                        setup_call_0arg(label_mock, False)

                    proc = processor.CommentProcessor(cfg)
                    issue = await proc.comment_to_github_pr(cmt)
                    assert issue == "1"
