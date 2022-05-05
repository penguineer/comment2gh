""" Test the processor module """

import pytest

# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import form
# noinspection PyUnresolvedReferences
# noinspection PyPackageRequirements
import processor


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


class TestCommentProcessor:
    def test_null_cfg(self):
        with pytest.raises(ValueError):
            processor.CommentProcessor(None)

# TODO mock tests here
