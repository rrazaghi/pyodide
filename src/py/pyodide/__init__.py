# When the pyodide package is imported, both the js and the pyodide_js modules
# will be available to import from. Not all functions in pyodide_js will work
# until after pyodide is first imported, imported functions from pyodide_js
# should not be used at import time. It is fine to use js functions at import
# time.
#
# All pure Python code that does not require js or pyodide_js should go in
# the _pyodide package.
#
# This package is imported by the test suite as well, and currently we don't use
# pytest mocks for js or pyodide_js, so make sure to test "if IN_BROWSER" before
# importing from these.

from ._core import (
    JsProxy,
    JsException,
    create_once_callable,
    create_proxy,
    to_js,
    IN_BROWSER,
    ConversionError,
    destroy_proxies,
)
from _pyodide._base import (
    eval_code,
    eval_code_async,
    find_imports,
    CodeRunner,
    should_quiet,
)
from .http import open_url
from . import _state  # noqa

from _pyodide._importhook import register_js_module, unregister_js_module

if IN_BROWSER:
    import asyncio
    from .webloop import WebLoopPolicy

    asyncio.set_event_loop_policy(WebLoopPolicy())


__version__ = "0.20.0dev0"

__all__ = [
    "open_url",
    "eval_code",
    "eval_code_async",
    "CodeRunner",
    "find_imports",
    "JsProxy",
    "JsException",
    "to_js",
    "register_js_module",
    "unregister_js_module",
    "create_once_callable",
    "create_proxy",
    "console",
    "should_quiet",
    "ConversionError",
    "destroy_proxies",
]
