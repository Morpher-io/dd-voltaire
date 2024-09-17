<div align="center">
  <h1 align="center">DD-Voltaire</h1>
</div>

<!-- PROJECT LOGO -->

<div align="center">
  <img src="https://github.com/candidelabs/voltaire/assets/7014833/603d130d-62ce-458e-b2f6-31597b5279ab">
  <p>
    <b>
      Modular and lighting-fast Python Bundler for Ethereum EIP-4337 Account Abstraction, modded to support oracle data injection
    </b>
   </p>
</div>

# Data endpoints
This mod extends the bundler to provide 4 new endpoints:
- `eth_sendDataDependentUserOperation`: to send data-dependent user operation, with the *data requirements* as an additional param
- `eth_estimateDataDependentUserOperationGas`: to estimate gas for data-dependent user operation, with the *data requirements* as an additional param
- `eth_oracleDataKeys`: to list the available data provided by the oracle
- `eth_oracleDataPreview`: to get a preview of the current data for a particular key, unsigned

# Usage

### Install Poetry
```
curl -sSL https://install.python-poetry.org | python3 -
```
### Install dependencies
```
poetry install
```

### Make sure you are using the right python version

```
poetry env use python3.11
```

### Get a good RPC for your chain of choice or run a node yourself
The node must allow `debug_traceCall` with custom tracers and `eth_call` with state overrides.


### Run the bundler
```
poetry run python3 -m voltaire_bundler --entrypoints $ENTRYPOINT --bundler_secret $YOUR_EOA_PK --bundler_smart_wallet_v6 $YOUR_SCA_V6_ADDRESS --bundler_smart_wallet_v7 $YOUR_SCA_V7_ADDRESS --chain_id $CHAIN_ID --ethereum_node_url $YOUR_RPC --oracle $ORACLE_ADDRESS --verbose
```
Oracle entrypoint is already deployed on Sepolia at address `0x36bDD3f53826e4359E22edb9C6DD2E81Dd4dEf41`.

### Run the data provider server

The bundler will fetch data from your own data server. See the [example](https://github.com/Morpher-io/dd-voltaire/tree/master/data-provider-example) folder for the server specs.

<!-- LICENSE -->
## License
LGPL

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

The project is forked from the [Voltaire bundler](https://github.com/candidelabs/voltaire) from the Voltaire team
