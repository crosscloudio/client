# Developer Toolchain

## Purifier

Helper script to purge a users keys, shares and device approval requests.

    PYTHONPATH=../Core python purifier.py

or a custom admin console url:

    PYTHONPATH=../Core CC_ADMIN_CONSOLE_URL=https://cc-testing.herokuapp.com python purifier.py

Optionally you can use `--username` and `--password` to directly specify credentials.
