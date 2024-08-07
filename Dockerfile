FROM python:3.11.4-alpine3.18

ENV PIP_DEFAULT_TIMEOUT=100 \
    # Allow statements and log messages to immediately appear
    PYTHONUNBUFFERED=1 \
    # disable a pip version check to reduce run-time & log-spam
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # cache is useless in docker image, so disable to reduce image size
    PIP_NO_CACHE_DIR=1

# Set WORKDIR
WORKDIR /app
COPY . /app

RUN set -ex \
    # Create a non-root user
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 -G appgroup --no-create-home appuser \
    # Install dependencies
    && pip install --no-cache-dir --upgrade pip \
    && pip install . --no-cache-dir

RUN chown -R appuser:appgroup /app 
RUN mkdir -p /app/cache
RUN chmod a+w /app/cache

ENTRYPOINT [ "python", "-m", "voltaire_bundler" ]
CMD [ "--entrypoints 0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789", 
    "--bundler_secret 0xd7f305cda31c0cb26f900afd16b3fcd697c3c1d00855767a8352d41987643e36",
    "--bundler_smart_wallet 0x90f007bfaf925a39e63568d8fc4712c81676ff05" +
    "--chain_id 11155111" +
    "--ethereum_node_url http://3.68.113.82:8545" +
    "--oracle 0x36bDD3f53826e4359E22edb9C6DD2E81Dd4dEf41" +
    "--verbose" ]
