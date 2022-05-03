#!/usr/bin/env python

"""Main application"""
import os

import tornado.web
import tornado.ioloop

import service

import logging

LOG_FORMAT = '%(levelname) -10s %(asctime)s %(name) -15s %(lineno) -5d: %(message)s'
LOGGER = logging.getLogger(__name__)


def make_app() -> tornado.web.Application:
    version_path = r"/v[0-9]"
    return tornado.web.Application([
        (version_path + r"/health", service.HealthHandler),
        (version_path + r"/oas3", service.Oas3Handler),
    ])


def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    # Service Configuration
    service_port = os.getenv('SERVICE_PORT', 8080)

    # Setup ioloop
    service.platform_setup()
    ioloop = tornado.ioloop.IOLoop.current()
    guard = service.TerminationGuard(ioloop)

    # Setup Service Management endpoint
    mgmt_ep = service.ServiceEndpoint(listen_port=service_port)
    guard.add_termination_handler(mgmt_ep.stop)
    app = make_app()
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
