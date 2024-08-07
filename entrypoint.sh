#!/bin/sh

cmd="python -m voltaire_bundler \
  --entrypoints $ENTRYPOINTS \
  --bundler_secret $BUNDLER_SECRET \
  --bundler_smart_wallet $BUNDLER_SMART_WALLET \
  --chain_id $CHAIN_ID \
  --ethereum_node_url $ETHEREUM_NODE_URL \
  --oracle $ORACLE_ADDRESS \
  --data_provider_url $DATA_PROVIDER_URL \
  --verbose"

exec $cmd
