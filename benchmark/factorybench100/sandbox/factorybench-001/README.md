# FactoryBench live sandbox bundle

This bundle powers the public benchmark-page MCP demo. Each browser session
receives a private SQLite database and trace. `bridge.py` executes only the
checked-in FactoryWorld tools in `runtime.py`; it does not accept source code,
shell commands, package installation, or arbitrary paths.
