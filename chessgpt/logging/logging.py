import logging
import os
from logging.handlers import SysLogHandler

from flask import request


def setup_logging(app):
    # setup logging
    app.logger.setLevel(logging.INFO)
    # are we running locally?
    if os.environ.get("IS_OFFLINE") == "True":
        return
    papertrail_app_name = os.environ.get("PAPERTRAIL_APP_NAME")
    # set the name of the app for papertrail
    if papertrail_app_name:

        class RequestFormatter(logging.Formatter):
            def format(self, record):
                if hasattr(record, "pathname"):
                    # ensure we have a request context
                    if request:
                        record.pathname = request.path
                return super().format(record)

        app.logger.name = papertrail_app_name
        syslog = SysLogHandler(address=("logs6.papertrailapp.com", 47875))
        syslog.setLevel(logging.INFO)
        formatter = RequestFormatter(
            f"{papertrail_app_name}: chess %(levelname)s %(pathname)s %(message)s"
        )
        syslog.setFormatter(formatter)
        app.logger.addHandler(syslog)

    @app.before_request
    def log_request_info():
        if not getattr(request.endpoint, "_exclude_from_log", False):
            # dump the query params and body
            app.logger.info("Request: %s", request.url)
            # app.logger.info("Body: %s", request.get_data())

    @app.after_request
    def log_response_info(response):
        # # Only log if the response is JSON
        # if (
        #     not getattr(request.endpoint, "_exclude_from_log", False)
        #     and response.mimetype == "application/json"
        # ):
        #     app.logger.info("Response: %s", response.get_data(as_text=True))
        return response


def exclude_from_log(route_func):
    route_func._exclude_from_log = True
    return route_func
