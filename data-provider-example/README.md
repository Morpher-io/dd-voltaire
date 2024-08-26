# Data Provider Specs

These are the specification the data provider server MUST implement.

## Host and port

The server url have to be specified in the bundler command line args as `--data_provider_url`. This server should NOT be exposed to the internet.

## Endpoint

The server must provide a `GET` `/fetch` endpoint with a `key` request arg which returns a json response like so:
```
{
    "data": "0x0123...def" # bytes32 data value
}
```
In case of any error or missing data, the endpoint should still return a 200 response like so:
```
{
    "error": "Invalid dataKey"
}
```

## Data information

The provider entity must also publish the list of data keys with an optional description that users will be able to see from the bunlder `eth_oracleDataKeys` rpc endpoint. This list must be available on the `GET` `/keys` route. The response should be:
```
{
    "data": [
        { "key": "0x0123...a", "description": "" },
        { "key": "0x0123...b", "description": "Bitcoin price" },
        { "key": "0x0123...c", "description": "Japan GDP" },
        { "key": "0x0123...d", "description": "Premier League leading team" }
    ]
}
```
