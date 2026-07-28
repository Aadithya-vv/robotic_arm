# Knowledge Engine API

## Engine contract

Contract `taskgraph.knowledge` version `1.0.0` provides initialize, rebuild, close, get all/one, get by Object ID, general/property/fact/category/relationship search, statistics, export, and integrity validation.

## HTTP projections

| Method | Route | Result |
|---|---|---|
| GET | `/knowledge` | Complete graph |
| GET | `/knowledge/{id}` | One record |
| GET | `/knowledge/search?q=&property=&fact=&category=&relationship=` | Combined filters |
| GET | `/knowledge/statistics` | Graph statistics |
| GET | `/knowledge/categories` | Category index |
| GET | `/knowledge/properties` | Property index |
| GET | `/knowledge/relationships` | Declared relationships |

No mutation route exists. Knowledge is generated and rebuilt, never edited through UI/WebAPI.
