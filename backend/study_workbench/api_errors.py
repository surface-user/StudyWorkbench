"""Add safe API error metadata without changing business status or successful bodies."""
import secrets

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

ERRORS = {
    400: ('bad_request', '请求格式无效'),
    401: ('unauthorized', '本地会话未授权，请重新连接'),
    403: ('forbidden', '此请求不被允许'),
    404: ('not_found', '目标不存在或不可访问'),
    405: ('method_not_allowed', '此请求方式不受支持'),
    409: ('conflict', '内容或状态已变化，请核对后重试'),
    413: ('payload_too_large', '请求超过允许的大小或数量'),
    416: ('range_not_satisfiable', '请求范围无效'),
    422: ('validation_failed', '请求参数无效，请核对输入'),
    429: ('resource_busy', '处理容量已满，请稍后重试'),
    500: ('internal_error', '请求未完成，请稍后重试'),
    503: ('unavailable', '所需服务暂不可用'),
    507: ('insufficient_storage', '可用存储空间不足'),
}


def is_api(scope):
    return scope['type'] == 'http' and scope['path'].startswith('/api/')


def request_id(scope):
    # Scope state is server-owned; never use an incoming header or business idempotency key.
    return scope.setdefault('state', {}).setdefault('api_request_id', secrets.token_hex(16))


def validation_detail(errors):
    result = []
    for issue in errors[:100]:
        location = issue.get('loc', ())
        origin = location[0] if location and location[0] in {'body', 'query', 'path', 'header', 'cookie'} else 'body'
        result.append(dict(loc=[origin, *[part if type(part) is int else 'field' for part in location[1:]]],
                           msg='请求参数无效', type='value_error'))
    return result


def error_response(scope, status, detail, headers=None):
    if not is_api(scope):
        return JSONResponse({'detail': detail}, status_code=status, headers=headers)
    code, message = ERRORS.get(status, ('http_error', '请求未完成'))
    identifier = request_id(scope)
    if isinstance(detail, list):
        detail = validation_detail(detail)
    response = JSONResponse({'detail': detail, 'error': dict(code=code, message=message, request_id=identifier)},
                            status_code=status, headers=headers)
    response.headers['X-Request-ID'] = identifier
    return response


class ApiTrustedHost:
    def __init__(self, app):
        self.app = TrustedHostMiddleware(app, allowed_hosts=['127.0.0.1'])

    async def __call__(self, scope, receive, send):
        # Match the existing fixed TrustedHost rule and position; non-API responses stay untouched.
        if is_api(scope) and Headers(scope=scope).get('host', '').split(':')[0] != '127.0.0.1':
            return await error_response(scope, 400, 'Invalid host header')(scope, receive, send)
        await self.app(scope, receive, send)


def install_error_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        if not is_api(request.scope) or error.status_code < 400:
            return await http_exception_handler(request, error)
        return error_response(request.scope, error.status_code, error.detail, error.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if not is_api(request.scope):
            return await request_validation_exception_handler(request, error)
        return error_response(request.scope, 422, error.errors())
