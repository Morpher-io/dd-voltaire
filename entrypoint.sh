#!/bin/sh

cmd="python -m voltaire_bundler \
  --rpc_url 0.0.0.0 \
  --bundler_secret $BUNDLER_SECRET \
  --bundler_smart_wallet_v6 $BUNDLER_SMART_WALLET_V6 \
  --bundler_smart_wallet_v7 $BUNDLER_SMART_WALLET_V7 \
  --chain_id $CHAIN_ID \
  --ethereum_node_url $ETHEREUM_NODE_URL \
  --oracle $ORACLE_ADDRESS \
  --data_provider_url $DATA_PROVIDER_URL \
  --disable_p2p true
  --verbose"

if [ "$CUT_SLOT_LEADING_ZEROS" = true ]; then
  cmd="$cmd --cut_slot_leading_zeros true"
fi

exec $cmd
