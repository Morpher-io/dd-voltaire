from typing import Any, List
import traceback
import logging
import aiohttp
import json

from eth_abi import encode
from eth_abi.packed import encode_packed
from eth_keys import keys
from eth_utils import keccak

from voltaire_bundler.bundle.exceptions import DataProviderException, \
    DataProviderExceptionCode, ValidationException, ValidationExceptionCode
from voltaire_bundler.gas.v6.gas_manager_v6 import GasManagerV6
from voltaire_bundler.gas.v7.gas_manager_v7 import GasManagerV7
from voltaire_bundler.mempool.v6.mempool_manager_v6 import LocalMempoolManagerV6
from voltaire_bundler.mempool.v7.mempool_manager_v7 import LocalMempoolManagerV7
from voltaire_bundler.user_operation.models import DataRequirement
from voltaire_bundler.user_operation.user_operation import UserOperation
from voltaire_bundler.user_operation.v6.user_operation_v6 import UserOperationV6, \
    get_user_operation_hash as get_user_operation_hash_v6
from voltaire_bundler.user_operation.v7.user_operation_v7 import UserOperationV7, \
    get_user_operation_hash as get_user_operation_hash_v7
from voltaire_bundler.user_operation.user_operation_handler import \
    UserOperationHandler
from voltaire_bundler.utils.eth_client_utils import (send_rpc_request_to_eth_client)


ORACLE_DATA_STORAGE_SLOT = 2
SAFE_MODULE_ADDRESS_V6 = '0xa581c4A4DB7175302464fF3C06380BC3270b4037'
SAFE_MODULE_ADDRESS_V7 = '0x75cf11467937ce3F2f357CE24ffc3DBF8fD5c226'


class DataManager:
    ethereum_node_url: str
    data_provider_url: str
    gas_manager_v6: GasManagerV6
    gas_manager_v7: GasManagerV7
    bundler_private_key: str
    bundler_address: str
    bundler_smart_account_address_v6: str
    bundler_smart_account_address_v7: str
    oracle_address: str
    chain_id: int
    cut_slot_leading_zeros: bool

    def __init__(
        self,
        ethereum_node_url: str,
        data_provider_url: str,
        gas_manager_v6: GasManagerV6,
        gas_manager_v7: GasManagerV7,
        bundler_private_key: str,
        bundler_address: str,
        bundler_smart_account_address_v6: str,
        bundler_smart_account_address_v7: str,
        oracle_address: str,
        chain_id: int,
        cut_slot_leading_zeros: bool,
    ):
        self.ethereum_node_url = ethereum_node_url
        self.data_provider_url = data_provider_url
        self.gas_manager_v6 = gas_manager_v6
        self.gas_manager_v7 = gas_manager_v7
        self.bundler_private_key = bundler_private_key
        self.bundler_address = bundler_address
        self.bundler_smart_account_address_v6 = bundler_smart_account_address_v6
        self.bundler_smart_account_address_v7 = bundler_smart_account_address_v7
        self.oracle_address = oracle_address
        self.chain_id = chain_id
        self.cut_slot_leading_zeros = cut_slot_leading_zeros

    async def provide_latest_data_value_for_key(self, data_key: str) -> str:
        value = await self._call_data_provider('/fetch?key=' + data_key)
        return value

    async def provide_list_of_provider_keys(self) -> list:
        keys = await self._call_data_provider('/keys')
        return keys

    async def extend_state_overrides(
            self,
            current_state_overrides: dict[str, Any],
            requirements: List[DataRequirement]
    ) -> dict[str, Any]:
        current_state_overrides[self.oracle_address] = { "stateDiff": {} }
        for requirement in requirements:
            current_state_overrides = await self._override_data_slot(requirement, current_state_overrides)
        return current_state_overrides

    async def inject_data_operations(
            self,
            user_operations: List[UserOperation],
            entryPoint: str
    ) -> str:
        new_user_operations_list: List[UserOperation] = []
        max_fee_per_gas, max_priority_fee_per_gas = None, None
        for user_op in user_operations:
            if not user_op.is_data_dependent():
                new_user_operations_list.append(user_op)
                continue
            if max_fee_per_gas is None:
                (max_fee_per_gas, max_priority_fee_per_gas) = await self._get_gas_price()
            requirements = user_op.data_requirements
            try:
                new_user_op = await self._build_data_op(
                    user_op.user_operation_hash, requirements, entryPoint,
                    max_fee_per_gas, max_priority_fee_per_gas
                )
                new_user_operations_list.append(new_user_op)
                new_user_operations_list.append(user_op)
            except Exception:
                logging.error("Cannot include the following data dependent user operation in the bundle: " + user_op.user_operation_hash)
                logging.error(traceback.format_exc())
        return new_user_operations_list

    async def _build_data_op(
            self,
            linked_op: str,
            requirements: List[DataRequirement],
            entrypoint: str,
            maxFeePerGas: str,
            maxPriorityFeePerGas: str
    ) -> UserOperation:
        # costs = await self._get_data_costs(requirements)
        nonce = await self._get_bundler_nonce(entrypoint)
        meta_transactions = await self._build_meta_transactions(requirements)
        calldata = self._create_user_op_calldata(meta_transactions)
        (callGasLimit, preVerificationGas, verificationGasLimit) = await self._get_gas_limits(
            nonce, calldata, entrypoint
        )
        jsonDict = {
            "nonce": hex(nonce),
            "callData": calldata,
            "callGasLimit":callGasLimit,
            "verificationGasLimit": hex(round(int(verificationGasLimit, 0) * 2)),
            "preVerificationGas": preVerificationGas,
            "maxFeePerGas": maxFeePerGas,
            "maxPriorityFeePerGas": maxPriorityFeePerGas,
            "signature": None
        }
        if entrypoint.lower() == LocalMempoolManagerV6.entrypoint_lowercase:
            jsonDict["sender"] = self.bundler_smart_account_address_v6
            jsonDict["initCode"] = "0x"
            jsonDict["paymasterAndData"] = "0x"
            jsonDict["signature"] = self._sign_user_op_for_safe_wallet(jsonDict, entrypoint)
            user_op = UserOperationV6(jsonDict, [], linked_op)
            user_operation_hash = get_user_operation_hash_v6(
                user_op.to_list(), entrypoint, self.chain_id
            )
        elif entrypoint.lower() == LocalMempoolManagerV7.entrypoint_lowercase:
            jsonDict["sender"] = self.bundler_smart_account_address_v7
            jsonDict["factory"] = None
            jsonDict["factoryData"] = None
            jsonDict["paymaster"] = None
            jsonDict["paymasterVerificationGasLimit"] = None
            jsonDict["paymasterPostOpGasLimit"] = None
            jsonDict["paymasterData"] = None
            jsonDict["signature"] = self._sign_user_op_for_safe_wallet(jsonDict, entrypoint)
            user_op = UserOperationV7(jsonDict, [], linked_op)
            user_operation_hash = get_user_operation_hash_v7(
                user_op.to_list(), entrypoint, self.chain_id
            )
        else:
            raise ValidationException(
                ValidationExceptionCode.InvalidFields,
                "Unsupported entrypoint",
            )
        user_op.user_operation_hash = user_operation_hash
        return user_op

    # HERE we assume that provider (=bundler) is using a SAFE smart wallet
    def _create_user_op_calldata(self, meta_transactions: List[str]) -> str:
        if len(meta_transactions) == 1:
            return self._create_user_op_calldata_single(meta_transactions[0])
        else:
            return self._create_user_op_calldata_multi(meta_transactions)

    def _create_user_op_calldata_single(self, meta_transaction: str) -> str:
        return self._create_exectute_safe_calldata(self.oracle_address, meta_transaction, 0)
 
    def _create_user_op_calldata_multi(self, meta_transactions: List[str]) -> str:
        # should be the same on any chain
        safeMultisendContractAddress = "0x38869bf66a61cF6bDB996A6aE40D5853Fd43B526"
        mutisendSelector = "0x8d80ff0a"
        multi_data = self._pack_meta_transactions(meta_transactions)
        multi_send_calldata = mutisendSelector + encode(["bytes"], [multi_data]).hex()
        return self._create_exectute_safe_calldata(safeMultisendContractAddress, multi_send_calldata, 1)

    def _pack_meta_transactions(self, meta_transactions: List[str]) -> bytes:
        packedMetaTxs = bytes()
        for meta_tx in meta_transactions:
            abi = ["uint8", "address", "uint256", "uint256", "bytes"]
            encoded = encode_packed(abi, [
                0, # operation
                bytes.fromhex(self.oracle_address[2:]), # to
                0, # value,
                len(meta_tx) // 2 - 1, # length of data in bytes,
                bytes.fromhex(meta_tx[2:])
            ])
            packedMetaTxs += encoded
        return packedMetaTxs

    def _create_exectute_safe_calldata(self, to: str, data: str, operation: int) -> str:
        executeUserOpWithErrorStringSelector = "0x541d63c8"
        abi = ["address", "uint256", "bytes", "uint8"]
        params = [
            bytes.fromhex(to[2:]),
            0, # value
            bytes.fromhex(data[2:]),
            operation
        ]
        return executeUserOpWithErrorStringSelector + encode(abi, params).hex()

    async def _get_bundler_nonce(self, entryPoint: str) -> int:
        getNonceSelector = "0x35567e1a"
        if entryPoint.lower() == LocalMempoolManagerV6.entrypoint_lowercase:
            smart_account_address = self.bundler_smart_account_address_v6
        elif entryPoint.lower() == LocalMempoolManagerV7.entrypoint_lowercase:
            smart_account_address = self.bundler_smart_account_address_v7
        else:
            raise ValidationException(
                ValidationExceptionCode.InvalidFields,
                "Unsupported entrypoint",
            )
        calldata = getNonceSelector + encode(
            ["address", "uint192"],
            [bytes.fromhex(smart_account_address[2:]), 0],
        ).hex()
        params = [
            {
                "from": "0x0000000000000000000000000000000000000000",
                "to": entryPoint,
                "data": calldata,
            },
            "latest",
        ]

        result: Any = await send_rpc_request_to_eth_client(
            self.ethereum_node_url, "eth_call", params
        )
        return int(result["result"], 0)

    async def _get_gas_price(self):
        result: Any = await send_rpc_request_to_eth_client(
            self.ethereum_node_url, "eth_gasPrice", []
        )
        maxFeePerGas = result["result"]

        result = await send_rpc_request_to_eth_client(
            self.ethereum_node_url, "eth_maxPriorityFeePerGas", []
        )
        maxPriorityFeePerGas = result["result"]
        return maxFeePerGas, maxPriorityFeePerGas

    async def _get_gas_limits(self, nonce: int, calldata: str, entrypoint: str) -> tuple[str, str, str]:
        jsonDict = {
            "nonce": hex(nonce),
            "callData": calldata,
            "callGasLimit": "0x00",
            "verificationGasLimit": "0x00",
            "preVerificationGas": "0x00",
            "maxFeePerGas": "0x00",
            "maxPriorityFeePerGas": "0x00",
            "signature": "0x" + "ff" * 77
        }
        if entrypoint.lower() == LocalMempoolManagerV6.entrypoint_lowercase:
            jsonDict["sender"] = self.bundler_smart_account_address_v6
            jsonDict["initCode"] = "0x"
            jsonDict["paymasterAndData"] = "0x"
            user_op = UserOperationV6(jsonDict)
            return await self.gas_manager_v6.estimate_user_operation_gas(user_op, entrypoint, dict())
        elif entrypoint.lower() == LocalMempoolManagerV7.entrypoint_lowercase:
            jsonDict["sender"] = self.bundler_smart_account_address_v7
            jsonDict["factory"] = None
            jsonDict["factoryData"] = None
            jsonDict["paymaster"] = None
            jsonDict["paymasterVerificationGasLimit"] = None
            jsonDict["paymasterPostOpGasLimit"] = None
            jsonDict["paymasterData"] = None
            user_op = UserOperationV7(jsonDict)
            return await self.gas_manager_v7.estimate_user_operation_gas(user_op, entrypoint, dict())
        else:
            raise ValidationException(
                ValidationExceptionCode.InvalidFields,
                "Unsupported entrypoint",
            )

    def _sign_user_op_for_safe_wallet(self, user_op: Any, entrypoint: str):
        if entrypoint.lower() == LocalMempoolManagerV6.entrypoint_lowercase:
            hashed_domain = self._get_hashed_domain(SAFE_MODULE_ADDRESS_V6)
        elif entrypoint.lower() == LocalMempoolManagerV7.entrypoint_lowercase:
            hashed_domain = self._get_hashed_domain(SAFE_MODULE_ADDRESS_V7)
        else:
            raise ValidationException(
                ValidationExceptionCode.InvalidFields,
                "Invalid entrypoint address",
            )
        hashed_payload = self._hash_payload(user_op, entrypoint)
        hash_to_sign = keccak(bytes.fromhex('1901') + hashed_domain + hashed_payload)
        (v, r, s) = self._sign_hash(hash_to_sign)
        signature = r.to_bytes(32, 'big') + s.to_bytes(32, 'big') + v.to_bytes(1, 'big')
        return "0x" + encode_packed(["uint48", "uint48", "bytes"], [0, 0, signature]).hex()

    def _get_hashed_domain(self, safeModuleAddress) -> bytes:
        # hash of EIP712Domain(uint256 chainId,address verifyingContract)
        prefix = "47e79534a245952e8b16893a336b85a3d9ea9fa8c573f3d803afb92a79469218"
        chainId = hex(self.chain_id)[2:].zfill(64)
        address = safeModuleAddress[2:].zfill(64)
        return keccak(bytes.fromhex(prefix + chainId + address))

    def _hash_payload(self, user_op: dict[str, Any], entrypoint: str) -> bytes:
        if entrypoint.lower() == LocalMempoolManagerV6.entrypoint_lowercase:
            # hash of the payload types
            prefix = "84aa190356f56b8c87825f54884392a9907c23ee0f8e1ea86336b763faf021bd"
        elif entrypoint.lower() == LocalMempoolManagerV7.entrypoint_lowercase:
            prefix = "c03dfc11d8b10bf9cf703d558958c8c42777f785d998c62060d85a4f0ef6ea7f"
        else:
            raise ValidationException(
                ValidationExceptionCode.InvalidFields,
                "Invalid entrypoint address",
            )
        # with empty factory and paymaster data the resulting initCode and
        # paymasterAndData are still 0x in v7 safe op
        return keccak(
            bytes.fromhex(prefix) +
            bytes.fromhex(user_op["sender"][2:].zfill(64)) +
            bytes.fromhex(user_op["nonce"][2:].zfill(64)) +
            keccak(bytes.fromhex("")) +
            keccak(bytes.fromhex(user_op["callData"][2:])) +
            bytes.fromhex(user_op["callGasLimit"][2:].zfill(64)) +
            bytes.fromhex(user_op["verificationGasLimit"][2:].zfill(64)) +
            bytes.fromhex(user_op["preVerificationGas"][2:].zfill(64)) +
            bytes.fromhex(user_op["maxFeePerGas"][2:].zfill(64)) +
            bytes.fromhex(user_op["maxPriorityFeePerGas"][2:].zfill(64)) +
            keccak(bytes.fromhex("")) +
            bytes.fromhex(hex(0)[2:].zfill(64)) + # validAfter
            bytes.fromhex(hex(0)[2:].zfill(64)) + # validUntil
            bytes.fromhex(entrypoint[2:].zfill(64))
        )

    async def _get_data_costs(self, requirements: List[DataRequirement]) -> int:
        costs = 0
        for requirement in requirements:
            call_data = self._encode_get_price(requirement)
            params = [
                {
                    "from": self.bundler_address,
                    "to": self.oracle_address,
                    "data": call_data,
                },
                "latest",
            ]

            result: Any = await send_rpc_request_to_eth_client(
                self.ethereum_node_url, "eth_call", params
            )
            costs += int(result["result"], 0)
        return costs

    def _encode_get_price(self, requirement: DataRequirement) -> str:
        function_selector = "0x75fd37a6" #prices(address,bytes32)
        params = encode(
            ["address", "bytes32"],
            [self.bundler_address, bytes.fromhex(requirement.dataKey[2:])],
        )

        call_data = function_selector + params.hex()
        return call_data

    async def _override_data_slot(
            self,
            requirement: DataRequirement,
            s_o_dict: dict[str, Any]
    ) -> dict[str, Any]:
        slot_position = encode(["uint256"], [ORACLE_DATA_STORAGE_SLOT])
        provider = encode(["address"], [requirement.provider])
        requester = encode(["address"], [requirement.requester])
        key = encode(["bytes32"], [bytes.fromhex(requirement.dataKey[2:])])
        storage_slot = "0x" + keccak(key + keccak(requester + keccak(provider + slot_position))).hex()
        value = await self.provide_latest_data_value_for_key(requirement.dataKey)
        # some clients don't like uint256 with leading 0s for some reason?
        if self.cut_slot_leading_zeros:
            s_o_dict[self.oracle_address]["stateDiff"][hex(int(storage_slot, 16))] = hex(int(value, 16))
        else:
            s_o_dict[self.oracle_address]["stateDiff"][storage_slot] = value
        return s_o_dict

    async def _build_meta_transactions(self, requirements: List[DataRequirement]) -> List[Any]:
        result = []
        nonce = await self._get_nonce_for_oracle()
        for requirement in requirements:
            if requirement.provider != self.bundler_address.lower():
                raise Exception("Cannot inject data for another provider!")
            valueHex = await self.provide_latest_data_value_for_key(requirement.dataKey)
            unsignedData = [
                self.chain_id,
                bytes.fromhex(requirement.provider[2:]),
                nonce,
                bytes.fromhex(requirement.requester[2:]),
                bytes.fromhex(requirement.dataKey[2:]),
                bytes.fromhex(valueHex[2:])
            ]
            packed = encode_packed(["uint256", "address", "uint256", "address", "bytes32", "bytes32"], unsignedData)
            packed = encode_packed(["bytes", "bytes"], [bytes('\x19Oracle Signed Data Op:\n168', 'utf-8'), packed])
            (v, r, s) = self._sign_hash(keccak(packed))
            calldata = self._get_store_data_calldata(unsignedData, r.to_bytes(32, 'big'), s.to_bytes(32, 'big'), v)
            result.append(calldata)
            nonce += 1
        return result

    async def _get_nonce_for_oracle(self) -> int:
        params = [
            {
                "from": self.bundler_address,
                "to": self.oracle_address,
                "data": "0x7ecebe00" + encode(["address"], [self.bundler_address]).hex(),
            },
            "latest",
        ]
        result: Any = await send_rpc_request_to_eth_client(
            self.ethereum_node_url, "eth_call", params
        )
        return int(result["result"], 0)

    def _get_store_data_calldata(self, data, r, s, v):
        selector = '0x91dd3d25' # storeData selector
        return selector + encode(
            ["address", "address", "uint256", "bytes32", "bytes32", "bytes32", "bytes32", "uint8"],
            [data[1], data[3], data[2]] + data[4:] + [r, s, v]
        ).hex()

    def _sign_hash(self, hash: bytes):
        pk = keys.PrivateKey(bytes.fromhex(self.bundler_private_key[2:]))
        signature = pk.sign_msg_hash(hash)
        (v_raw, r, s) = signature.vrs
        v = 27 + v_raw
        return (v, r, s)

    async def _call_data_provider(self, path: str) -> Any:
        async with aiohttp.ClientSession() as session:
            resp_json = { "error": None }
            try:
                response = await session.get(self.data_provider_url + path)
                resp = await response.read()
                response.release()
                resp_json = json.loads(resp)
            except aiohttp.ClientError as e:
                raise DataProviderException(
                    DataProviderExceptionCode.GENERIC_ERROR,
                    "HTTP request to data provider failed: " + str(e)
                )
            except Exception as e:
                raise DataProviderException(
                    DataProviderExceptionCode.GENERIC_ERROR,
                    "Unexpected error encountered while connecting to data provider: " + str(e)
                )
            if "error" in resp_json.keys():
                raise DataProviderException(
                    DataProviderExceptionCode.GENERIC_ERROR,
                    "Data Provider returned error: " + resp_json["error"]
                )
            return resp_json["data"]
