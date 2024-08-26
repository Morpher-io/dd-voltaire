import logging
from functools import partial
from importlib.metadata import version
from typing import Any, List

import aiohttp_cors
from aiohttp import web
from jsonrpcserver import Error, Result, Success, async_dispatch, method
from prometheus_client import Summary

from voltaire_bundler.bundler.exceptions import (ExecutionException,
                                                 ValidationException,
                                                 DataProviderException)
from voltaire_bundler.event_bus_manager.endpoint import Client, RequestEvent

# TODO(mic) add new rpc to show supported data keys

REQUEST_TIME_eth_chainId = Summary(
    "request_processing_seconds_eth_chainId",
    "Time spent processing request eth_chainId",
)
REQUEST_TIME_eth_supportedEntryPoints = Summary(
    "request_processing_seconds_eth_supportedEntryPoints",
    "Time spent processing request eth_supportedEntryPoints",
)
REQUEST_TIME_eth_estimateUserOperationGas = Summary(
    "request_processing_seconds_eth_estimateUserOperationGas",
    "Time spent processing request eth_estimateUserOperationGas",
)
REQUEST_TIME_eth_estimateDataDependentUserOperationGas = Summary(
    "request_processing_seconds_eth_estimateDataDependentUserOperationGas",
    "Time spent processing request eth_estimateDataDependentUserOperationGas",
)
REQUEST_TIME_chainId_eth_sendUserOperation = Summary(
    "request_processing_seconds_eth_sendUserOperation",
    "Time spent processing request eth_sendUserOperation",
)
REQUEST_TIME_chainId_eth_sendDataDependentUserOperation = Summary(
    "request_processing_seconds_eth_sendDataDependentUserOperation",
    "Time spent processing request eth_sendDataDependentUserOperation",
)
REQUEST_TIME_chainId_eth_getUserOperationReceipt = Summary(
    "request_processing_seconds_eth_getUserOperationReceipt",
    "Time spent processing request eth_getUserOperationReceipt",
)
REQUEST_TIME_chainId_eth_getUserOperationByHash = Summary(
    "request_processing_seconds_eth_getUserOperationByHash",
    "Time spent processing request eth_getUserOperationByHash",
)
REQUEST_TIME_chainId_eth_oracleDataKeys = Summary(
    "request_processing_seconds_eth_oracleDataKeys",
    "Time spent processing request eth_oracleDataKeys",
)
REQUEST_TIME_chainId_eth_oracleDataPreview = Summary(
    "request_processing_seconds_eth_oracleDataPreview",
    "Time spent processing request eth_oracleDataPreview",
)


rpcClient: Client = Client("bundler_endpoint")


async def _handle_rpc_request(
    endpoint_id: str, request_type: str, request_arguments: Any = ""
) -> Any:
    requestEvent: RequestEvent = {
        "request_type": request_type,
        "request_arguments": request_arguments,
    }
    resp = await rpcClient.request(requestEvent)

    logging.debug(f"{request_type} RPC served")

    if resp is not None and "is_error" in resp and resp["is_error"]:
        error: ValidationException | ExecutionException | DataProviderException = resp["payload"]
        error_code = error.exception_code.value
        error_message = str(error.message)

        return Error(error_code, error_message)
    else:
        return Success(resp)


@REQUEST_TIME_eth_chainId.time()
@method
async def eth_chainId() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_chainId",
    )
    return result


@REQUEST_TIME_eth_supportedEntryPoints.time()
@method
async def eth_supportedEntryPoints() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_supportedEntryPoints",
    )
    return result


@REQUEST_TIME_eth_estimateUserOperationGas.time()
@method
async def eth_estimateUserOperationGas(
    userOperationJson: dict[str, Any],
    entrypoint: str,
    state_override_set: dict[str, Any] | None = None,
) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_estimateUserOperationGas",
        request_arguments=[userOperationJson, entrypoint, state_override_set],
    )
    return result


@REQUEST_TIME_eth_estimateDataDependentUserOperationGas.time()
@method
async def eth_estimateDataDependentUserOperationGas(
    userOperationJson: dict[str, Any],
    entrypoint: str,
    requirements: List[dict[str, Any]],
    state_override_set: dict[str, Any] | None = None,
) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_estimateDataDependentUserOperationGas",
        request_arguments=[userOperationJson, entrypoint, requirements, state_override_set],
    )
    return result


@REQUEST_TIME_chainId_eth_sendUserOperation.time()
@method
async def eth_sendUserOperation(
    userOperationJson: dict[str, Any], entrypoint: str
) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_sendUserOperation",
        request_arguments=[userOperationJson, entrypoint],
    )
    return result


@REQUEST_TIME_chainId_eth_sendDataDependentUserOperation.time()
@method
async def eth_sendDataDependentUserOperation(
    userOperationJson: dict[str, Any], entrypoint: str, requirements: List[dict[str, Any]]
) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_sendDataDependentUserOperation",
        request_arguments=[userOperationJson, entrypoint, requirements],
    )
    return result


@REQUEST_TIME_chainId_eth_getUserOperationReceipt.time()
@method
async def eth_getUserOperationReceipt(userOperationHash: str) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_getUserOperationReceipt",
        request_arguments=[userOperationHash],
    )
    return result


@REQUEST_TIME_chainId_eth_getUserOperationByHash.time()
@method
async def eth_getUserOperationByHash(userOperationHash: str) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_getUserOperationByHash",
        request_arguments=[userOperationHash],
    )
    return result


@REQUEST_TIME_chainId_eth_oracleDataKeys.time()
@method
async def eth_oracleDataKeys() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_oracleDataKeys",
    )
    return result


@REQUEST_TIME_chainId_eth_oracleDataPreview.time()
@method
async def eth_oracleDataPreview(dataKey: str) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="rpc_oracleDataPreview",
        request_arguments=[dataKey],
    )
    return result


@method
async def debug_bundler_sendBundleNow() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_sendBundleNow",
    )
    return result


@method
async def debug_bundler_clearState() -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_clearState",
    )
    return result


@method
async def debug_bundler_dumpMempool(entrypoint: str) -> Result:
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
async def debug_bundler_dumpReputation(entrypoint: str) -> Result:
    result = await _handle_rpc_request(
        endpoint_id="bundler_endpoint",
        request_type="debug_bundler_dumpReputation",
        request_arguments=[entrypoint],
    )
    return result


#
@method
async def web3_bundlerVersion() -> Result:
    return Success(version("voltaire_bundler"))


async def handle(is_debug: bool, request: web.Request) -> web.Response:
    res = await request.text()
    methods = {
        "eth_chainId": eth_chainId,
        "eth_supportedEntryPoints": eth_supportedEntryPoints,
        "eth_estimateUserOperationGas": eth_estimateUserOperationGas,
        "eth_estimateDataDependentUserOperationGas": eth_estimateDataDependentUserOperationGas,
        "eth_sendUserOperation": eth_sendUserOperation,
        "eth_sendDataDependentUserOperation": eth_sendDataDependentUserOperation,
        "eth_getUserOperationReceipt": eth_getUserOperationReceipt,
        "eth_getUserOperationByHash": eth_getUserOperationByHash,
        "eth_oracleDataKeys": eth_oracleDataKeys,
        "eth_oracleDataPreview": eth_oracleDataPreview,
        "web3_bundlerVersion": web3_bundlerVersion,
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


async def health(_: web.Request) -> web.Response:
    return web.Response(text="OK")


async def run_rpc_http_server(
    host: str = "localhost",
    rpc_cors_domain: str = "*",
    port: int = 3000,
    is_debug: bool = False,
) -> None:
    logging.info(f"Starting HTTP RPC Server at: {host}:{port}/rpc")
    app = web.Application()
    handle_func = partial(handle, is_debug)
    app.router.add_post("/rpc", handle_func)

    app.router.add_post("/health", health)

    cors = aiohttp_cors.setup(
        app,
        defaults={
            rpc_cors_domain: aiohttp_cors.ResourceOptions(
                allow_credentials=True, expose_headers="*", allow_headers="*"
            )
        },
    )
    for route in list(app.router.routes()):
        cors.add(route)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
