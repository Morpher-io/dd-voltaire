// SPDX-License-Identifier: LGPL-3.0-only
pragma solidity >=0.7.0 <0.9.0;

contract GetCodeHashes {

    error CodeHashesResult(bytes32 hash);
    constructor(address[] memory addresses) {
        revert CodeHashesResult(getCodeHashes(addresses));
    }

    function getCodeHashes(address[] memory addresses) public view returns (bytes32) {
        bytes32[] memory hashes = new bytes32[](addresses.length);
        for (uint i = 0; i < addresses.length; i++) {
            hashes[i] = addresses[i].codehash;
        }
        bytes memory data = abi.encode(hashes);
        return (keccak256(data));
    }
}