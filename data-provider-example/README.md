# Data Provider Specs

These are the specification the data provider server MUST implement.

## Host and port

The server can run on any local address and port, which have to be specified in the bundler command line args as *--data_host* and *--data_port*.

## Endpoint

The server must provide a GET /fetch endpoint with a *key* request arg which returns a json response like so:
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

The provider entity should also publish the list of data keys available on their bundler.
