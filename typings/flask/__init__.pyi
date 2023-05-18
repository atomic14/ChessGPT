from typing import Any, Callable, Dict, Optional, Union
from werkzeug.local import LocalProxy
from logging import Logger
from werkzeug.datastructures import EnvironHeaders

class Flask:
    def __init__(self, import_name: str, **kwargs: Any) -> None: ...
    logger: Logger
    before_request: Callable[..., Any]
    after_request: Callable[..., Any]
    dynamodb_client: Any
    GAMES_TABLE: str
    route: Callable[..., Any]
    errorhandler: Callable[..., Any]

def jsonify(*args: Any, **kwargs: Any) -> "Response": ...
def send_from_directory(directory: str, filename: str) -> Response: ...  # type: ignore
def make_response(*args: Any, **kwargs: Any) -> Response: ...  # type: ignore

class _request_obj:
    method: str
    headers: EnvironHeaders
    args: Dict[str, str]

    @classmethod
    def get_json(
        cls, force: bool = False, silent: bool = False, cache: bool = True
    ) -> Optional[Dict[str, Any]]: ...

request: LocalProxy = LocalProxy(_request_obj)

class Response:
    status_code: int
    headers: Dict[str, str]
    data: bytes

    def __init__(
        self,
        response: Optional[Union[str, Dict[str, Any]]] = None,
        status: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        mimetype: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None: ...
