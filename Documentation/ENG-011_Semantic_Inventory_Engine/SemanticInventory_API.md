# Semantic Inventory API

## Engine contract

`SemanticInventoryContract` exposes initialize, refresh, get object, get all, search, statistics, export, and close. Requests use contract `taskgraph.semantic-inventory` version `1.0.0`. Responses carry status, lifecycle state, correlation, payload, structured errors, and explanations.

## Read-only HTTP projections

| Method | Route | Meaning |
|---|---|---|
| GET | `/semantic` | Complete inventory snapshot |
| GET | `/semantic/{object_id}` | One semantic object or 404 |
| GET | `/semantic/search?q=&category=&alias=&tag=` | AND-combined filters |
| GET | `/semantic/statistics` | Counts and average semantic score |

There are no semantic POST, PATCH, PUT, or DELETE routes. Editing remains exclusively in Object Library.
