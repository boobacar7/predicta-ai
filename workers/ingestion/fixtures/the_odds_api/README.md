# The Odds API — recorded fixtures

These JSON files copy the **shape** documented by The Odds API v4
(`GET /v4/sports/{sport}/odds` and `GET /v4/historical/sports/{sport}/odds`).
They are not live responses and must not be presented as current bookmaker prices.

CI and unit tests load them through `OddsScriptedTransport`. They never call
`api.the-odds-api.com`.
