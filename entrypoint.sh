#!/bin/sh

cmd="python -m voltaire_bundler \
  --rpc_url 0.0.0.0 \
  --bundler_secret $BUNDLER_SECRET \
  --bundler_smart_wallet $BUNDLER_SMART_WALLET \
  --chain_id $CHAIN_ID \
  --ethereum_node_url $ETHEREUM_NODE_URL \
  --oracle $ORACLE_ADDRESS \
  --data_provider_url $DATA_PROVIDER_URL \
  --disable_p2p true
  --verbose"

exec $cmd
