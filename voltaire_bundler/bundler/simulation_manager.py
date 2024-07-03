import asyncio
import logging
import os
from typing import Any

from eth_abi import decode, encode
from eth_utils import keccak, to_checksum_address

from voltaire_bundler.bundler.exceptions import (ValidationException,
                                                 ValidationExceptionCode)
from voltaire_bundler.bundler.gas_manager import GasManager
from voltaire_bundler.utils.encode import encode_handleops_calldata
from voltaire_bundler.user_operation.models import (FailedOpRevertData,
                                                    ReturnInfo, StakeInfo,
                                                    DataRequirement)
from voltaire_bundler.user_operation.user_operation import UserOperation
from voltaire_bundler.user_operation.user_operation_handler import \
    UserOperationHandler
from voltaire_bundler.utils.decode import decode_FailedOp_event
from voltaire_bundler.utils.encode import encode_simulate_validation_calldata
from voltaire_bundler.utils.eth_client_utils import (
    Call, DebugEntityData, DebugTraceCallData, send_rpc_request_to_eth_client)
from voltaire_bundler.typing import Address


DATA_CONSUMED_TOPIC = '15115630875334050528119854500631546305795158188988926959829948410173647413744'
USER_OP_REVERT_TOPIC = '12805539188701497113405772294394028637842369425345398187799062004237924934145'
class SimulationManager:
    ethereum_node_url: str
    bundler_address: str
    bundler_collector_tracer: str
    ethereum_node_debug_trace_call_url: str

    def __init__(
        self,
        ethereum_node_url: str,
        bundler_address: str,
        ethereum_node_debug_trace_call_url: str,
    ):
        self.ethereum_node_url = ethereum_node_url
        self.bundler_address = bundler_address
        self.ethereum_node_debug_trace_call_url = ethereum_node_debug_trace_call_url
        package_directory = os.path.dirname(os.path.abspath(__file__))
        BundlerCollectorTracer_file = os.path.join(
            package_directory, "..", "utils", "BundlerCollectorTracer.js"
        )
        with open(BundlerCollectorTracer_file) as keyfile:
            self.bundler_collector_tracer = keyfile.read()

    async def discard_unpaid_data_dependent_user_operations(
        self,
        user_operations: list[UserOperation],
        entrypoint: str,
        oracle_address: str,
        gas_price_hex: str,
    ) -> list[UserOperation]:
        call_data = encode_handleops_calldata(
            [user_op.to_list() for user_op in user_operations], self.bundler_address
        )
        params = [
            {
                "from": self.bundler_address,
                "to": entrypoint,
                "data": call_data,
                "gasLimit": 0,
                "gasPrice": gas_price_hex,
            },
            'latest',
            {
                "tracer": "{\n" +
                    "    data: [],\n" +
                    "    fault: function (log) {\n" +
                    "    },\n" +
                    "    step: function (log) {\n" +
                    "        var topicCount = (log.op.toString().match(/LOG(\\d)/) || [])[1];\n" +
                    "        if (topicCount) {\n" +
                    "            var res = {\n" +
                    "                address: log.contract.getAddress(),\n" +
                    "                data: log.memory.slice(parseInt(log.stack.peek(0)), parseInt(log.stack.peek(0)) + parseInt(log.stack.peek(1))),\n" +
                    "            };\n" +
                    "            for (var i = 0; i < topicCount; i++)\n" +
                    "                res['topic' + i.toString()] = log.stack.peek(i + 2);\n" +
                    "            this.data.push(res);\n" +
                    "        }\n" +
                    "    },\n" +
                    "    result: function () {\n" +
                    "        return this.data;\n" +
                    "    }\n" +
                    "}", 
            }
        ]

        res: Any = await send_rpc_request_to_eth_client(
            self.ethereum_node_debug_trace_call_url, "debug_traceCall", params
        ) 

        paid_requirements = []
        user_ops_reverted = []
        for log in res["result"]:
            byte_list = [log["address"][str(i)] for i in range(len(log["address"]))]
            hex_string = '0x' + ''.join(f'{byte:02x}' for byte in byte_list).lower()
            if hex_string == oracle_address.lower() and log["topic0"] == DATA_CONSUMED_TOPIC:
                byte_list = [log["data"][str(i)] for i in range(len(log["data"]))]
                hex_string = ''.join(f'{byte:02x}' for byte in byte_list).lower()
                provider = '0x' + hex_string[24:64].lower()
                requester = '0x' + hex_string[88:128].lower()
                data_key = '0x' + hex_string[128:].lower()
                paid_requirements.append(DataRequirement(data_key, provider, requester))
            if hex_string == entrypoint.lower() and log["topic0"] == USER_OP_REVERT_TOPIC:
                user_ops_reverted.append(hex(int(log["topic1"])))

        new_user_operations: list[UserOperation] = []
        deleted_user_operations_hashes = []
        for user_op in user_operations:
            if not user_op.is_data_dependent():
                new_user_operations.append(user_op)
                continue
            user_op_reqs = user_op.data_requirements
            if len(user_op_reqs) > len([0 for req in user_op_reqs if req in paid_requirements]):
                logging.info("Dropping user operation for missing payment! [" + user_op.user_operation_hash + ']')
                deleted_user_operations_hashes.append(user_op.user_operation_hash)
            elif user_op.user_operation_hash.lower() in user_ops_reverted:
                logging.info("Dropping user operation for reverting! [" + user_op.user_operation_hash + ']')
                deleted_user_operations_hashes.append(user_op.user_operation_hash)
            else:
                new_user_operations.append(user_op)

        user_operations = []
        for user_op in new_user_operations:
            if not user_op.is_data_user_op() or user_op.data_dependent_user_op_hash not in deleted_user_operations_hashes:
                user_operations.append(user_op)
            else:
                logging.info("Dropping data user op [" + user_op.user_operation_hash +
                                '] relative to [' + user_op.data_dependent_user_op_hash + ']')
        return user_operations
