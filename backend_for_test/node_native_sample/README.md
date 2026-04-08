# Node native representative sample

This sample uses Node built-in http only (no web framework dependency).
It is only for AST route and function extraction tests.
It is not wired into docker-compose or frontend import presets.

Coverage:
- imperative dispatch with method/path conditions (`if (req.method && req.url)`)
- methods: GET POST PUT PATCH DELETE HEAD OPTIONS
