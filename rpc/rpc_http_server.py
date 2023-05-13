import logging
from functools import partial
from aiohttp import web
from jsonrpcserver import (
    method,
    Result,
    Success,
    async_dispatch,
    Error,
    InvalidParams,
)
from typing import Any

from event_bus_manager.endpoint import Client
from rpc.events import RPCCallRequestEvent, RPCCallResponseEvent
from user_operation.user_operation import (
    UserOperation,
    verify_and_get_address,
    is_user_operation_hash,
)
from bundler.exceptions import (
    ValidationException,
    ExecutionException,
    ValidationExceptionCode,
)


async def _handle_rpc_request(
    endpoint_id: str, request_type: str, request_arguments: Any
) -> Any:
    rpcClient: Client = Client(endpoint_id)
    requestEvent = RPCCallRequestEvent(request_type, request_arguments)
    resp: RPCCallResponseEvent = await rpcClient.request(requestEvent)

    logging.debug(f"{request_type} RPC served")
    if resp.is_error:
        error: ValidationException | ExecutionException = resp.payload
        error_code = error.exception_code.value
        error_message = str(error.message)
        revert_message = bytes.fromhex(error.data[-64:]).decode("ascii")
        if revert_message == "":
            return Error(error_code, error_message)
        else:
            return Error(error_code, error_message + " " + revert_message)
    else:
        return Success(resp.payload)


@method
async def eth_chainId() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_chainId",
        request_arguments="",
    )
    return result


@method
async def eth_supportedEntryPoints() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_supportedEntryPoints",
        request_arguments="",
    )
    return result


@method
async def eth_estimateUserOperationGas(
    userOperationJson, entrypoint
) -> Result:
    try:
        userOperation: UserOperation = UserOperation(userOperationJson)
        verify_and_get_address(entrypoint)
    except ValidationException as exp:
        return InvalidParams(exp.message)

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_estimateUserOperationGas",
        request_arguments=[userOperation, entrypoint],
    )
    return result


@method
async def eth_sendUserOperation(userOperationJson, entrypoint) -> Result:
    try:
        userOperation: UserOperation = UserOperation(userOperationJson)
        verify_and_get_address(entrypoint)
    except ValidationException as exp:
        return InvalidParams(exp.message)

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_sendUserOperation",
        request_arguments=[userOperation, entrypoint],
    )
    return result


@method
async def eth_getUserOperationReceipt(userOperationHash) -> Result:
    if not is_user_operation_hash(userOperationHash):
        return Error(
            ValidationExceptionCode.INVALID_USEROPHASH.value,
            "Missing/invalid userOpHash",
        )

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_getUserOperationReceipt",
        request_arguments=[userOperationHash],
    )
    return result


@method
async def eth_getUserOperationByHash(userOperationHash) -> Result:
    if not is_user_operation_hash(userOperationHash):
        return Error(
            ValidationExceptionCode.INVALID_USEROPHASH.value,
            "Missing/invalid userOpHash",
        )

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_getUserOperationByHash",
        request_arguments=[userOperationHash],
    )
    return result


@method
async def debug_bundler_sendBundleNow() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_sendBundleNow",
        request_arguments="",
    )
    return result


@method
async def debug_bundler_clearState() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_clearState",
        request_arguments="",
    )
    return result


@method
async def debug_bundler_dumpMempool(entrypoint) -> Result:
    try:
        verify_and_get_address(entrypoint)
    except ValidationException as exp:
        return InvalidParams(exp.message)

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_dumpMempool",
        request_arguments=[entrypoint],
    )
    return result


@method
async def debug_bundler_setReputation(
    entitiy: str, ops_seen: int, ops_included: int, status: int
) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_setReputation",
        request_arguments=[entitiy, ops_seen, ops_included, status],
    )
    return result


@method
async def debug_bundler_dumpReputation(entrypoint) -> Result:
    try:
        verify_and_get_address(entrypoint)
    except ValidationException as exp:
        return InvalidParams(exp.message)

    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_dumpReputation",
        request_arguments=[entrypoint],
    )
    return result


async def handle(is_debug, request):
    res = await request.text()
    methods = {
        "eth_chainId": eth_chainId,
        "eth_supportedEntryPoints": eth_supportedEntryPoints,
        "eth_estimateUserOperationGas": eth_estimateUserOperationGas,
        "eth_sendUserOperation": eth_sendUserOperation,
        "eth_getUserOperationReceipt": eth_getUserOperationReceipt,
        "eth_getUserOperationByHash": eth_getUserOperationByHash,
    }

    if is_debug:
        debug_methods = {
            "debug_bundler_sendBundleNow": debug_bundler_sendBundleNow,
            "debug_bundler_clearState": debug_bundler_clearState,
            "debug_bundler_dumpMempool": debug_bundler_dumpMempool,
            "debug_bundler_setReputation": debug_bundler_clearState,
            "debug_bundler_dumpReputation": debug_bundler_dumpReputation,
        }
        methods.update(debug_methods)

    return web.Response(
        text=await async_dispatch(res, methods=methods),
        content_type="application/json",
    )


async def run_rpc_http_server(host="localhost", port=3000, is_debug=False):
    logging.info(f"Starting HTTP RPC Server at: {host}:{port}/rpc")
    app = web.Application()
    handle_func = partial(handle, is_debug)
    app.router.add_post("/rpc", handle_func)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
