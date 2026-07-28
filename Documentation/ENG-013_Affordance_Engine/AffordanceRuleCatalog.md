# Affordance Rule Catalog 1.0.0

| Rule | Exact field/value | Actions |
|---|---|---|
| category.container | category=`container` | fill, pour, carry |
| name.cup | name=`cup` | pick, place, hold |
| name.bottle | name=`bottle` | pick, carry, open, close, pour, place |
| name.knife | name=`knife` | pick, cut, place |
| name.spoon | name=`spoon` | pick, hold, move, stir, transfer, place |
| name.plate | name=`plate` | place food, carry |
| name.bowl | name=`bowl` | hold food, carry, fill, pour out |

Matching is case-insensitive exact equality. All matching rules union, deduplicate, and lexically sort actions. Every output stores `rule_id@version`. Unknown values deliberately produce no actions. Action categories are manipulation, transport, container, access, tool use, and food handling.
