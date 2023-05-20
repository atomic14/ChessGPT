import os
from flask import jsonify, request, send_from_directory, Response

from chessgpt.logging.logging import exclude_from_log
import json


def static_routes(app):
    @app.route("/.well-known/ai-plugin.json")
    @exclude_from_log
    def serve_ai_plugin():
        with open(".well-known/ai-plugin.json", "r") as f:
            data = f.read()
            # replace the string PLUGIN_HOSTNAME with the actual hostname
            data = data.replace("PLUGIN_HOSTNAME", request.host)
            data = data.replace("PROTOCOL", request.scheme)
            # get the json
            json_response = json.loads(data)
            # fill in the auth settings
            # for localhost we can only do "none"
            if "localhost" in request.host:
                json_response["auth"] = {"type": "none"}
            else:
                json_response["auth"] = {
                    "type": "service_http",
                    "authorization_type": "bearer",
                    "verification_tokens": {
                        "openai": os.environ.get("OPENAI_VERIFY_TOKEN")
                    },
                }
            return jsonify(json_response)

    @app.route("/openapi.yaml")
    @exclude_from_log
    def serve_openai_yaml():
        # read in the file
        with open("openapi.yaml", "r") as f:
            data = f.read()
            # replace the string PLUGIN_HOSTNAME with the actual hostname
            data = data.replace("PLUGIN_HOSTNAME", request.host)
            data = data.replace("PROTOCOL", request.scheme)
            # return the modified file
            response = Response(data, mimetype="text/yaml")
            response.headers["Cache-Control"] = "public, max-age=86400"
            return response

    @app.route("/")
    @app.route("/index.html")
    @exclude_from_log
    def index():
        return send_from_directory("static", "index.html")

    @app.route("/terms.html")
    @exclude_from_log
    def terms():
        response = send_from_directory("static", "terms.html")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.route("/site.webmanifest")
    @exclude_from_log
    def site_manifest():
        return send_from_directory("static", "site.webmanifest")

    @app.route("/images/<path:path>")
    @exclude_from_log
    def send_image(path):
        response = send_from_directory("static/images", path)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.route("/logo.png")
    @exclude_from_log
    def serve_logo():
        # cache for 24 hours
        response = send_from_directory("static", "logo.png")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.route("/robots.txt")
    @exclude_from_log
    def serve_robots():
        # cache for 24 hours
        response = send_from_directory("static", "robots.txt")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.route("/favicon.ico")
    @exclude_from_log
    def serve_favicon():
        # cache for 24 hours
        response = send_from_directory("static/images/", "favicon.ico")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response
