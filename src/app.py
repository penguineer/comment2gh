#!/usr/bin/env python

"""Main application"""
import os

import tornado.web
import tornado.ioloop

import service
import github
import processor

import logging

import form
import captcha

LOG_FORMAT = '%(levelname) -10s %(asctime)s %(name) -15s %(lineno) -5d: %(message)s'
LOGGER = logging.getLogger(__name__)


def make_app(cmt_cfg, comment_cb, recaptcha=None) -> tornado.web.Application:
    version_path = r"/v[0-9]"
    return tornado.web.Application([
        (version_path + r"/health", service.HealthHandler),
        (version_path + r"/oas3", service.Oas3Handler),
        (version_path + r"/comment", form.CommentHandler, {"cfg": cmt_cfg,
                                                           "comment_cb": comment_cb,
                                                           "recaptcha": recaptcha}),
    ])


def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    # Service Configuration
    service_port = os.getenv('SERVICE_PORT', 8080)
    cmt_cfg = form.FormConfiguration.from_environment()

    # Comment Processor
    github_cfg = github.GithubConfiguration.from_environment()
    comment_processor = processor.CommentProcessor(github_cfg)

    # reCAPTCHA
    recaptcha_cfg = captcha.RecaptchaConfiguration.from_environment()
    recaptcha = None
    if recaptcha_cfg.is_enabled():
        LOGGER.info("reCAPTCHA setup has been recognized.")
        recaptcha = captcha.Recaptcha(recaptcha_cfg)

    # Setup ioloop
    service.platform_setup()
    ioloop = tornado.ioloop.IOLoop.current()
    guard = service.TerminationGuard(ioloop)

    # Setup Service Management endpoint
    mgmt_ep = service.ServiceEndpoint(listen_port=service_port)
    guard.add_termination_handler(mgmt_ep.stop)
    app = make_app(cmt_cfg, comment_processor.comment_to_github_pr, recaptcha)
    mgmt_ep.setup(app)

    # Health Provider map uses weak references, so make sure to store this instance in a variable
    git_health_provider = service.GitHealthProvider()
    service.HealthHandler.add_health_provider('git-version', git_health_provider.get_health)

    # Run
    LOGGER.info("Starting ioloop")
    while not guard.is_terminated():
        try:
            ioloop.start()
        except KeyboardInterrupt:
            LOGGER.info("Keyboard interrupt")
            guard.terminate()

    # Restart ioloop for clean-up
    ioloop.start()

    # Teardown
    LOGGER.info("Service terminated")


if __name__ == "__main__":
    main()
