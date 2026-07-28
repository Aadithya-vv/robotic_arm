"""Explicit versioned deterministic Affordance rules."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import RULE_VERSION
@dataclass(frozen=True,slots=True)
class AffordanceRule:
    rule_id:str;match_field:str;match_value:str;actions:tuple[str,...];version:str=RULE_VERSION
RULES=(
 AffordanceRule("category.container","category","container",("fill","pour","carry")),
 AffordanceRule("name.cup","name","cup",("pick","place","hold")),
 AffordanceRule("name.bottle","name","bottle",("pick","carry","open","close","pour","place")),
 AffordanceRule("name.knife","name","knife",("pick","cut","place")),
 AffordanceRule("name.spoon","name","spoon",("pick","hold","move","stir","transfer","place")),
 AffordanceRule("name.plate","name","plate",("place food","carry")),
 AffordanceRule("name.bowl","name","bowl",("hold food","carry","fill","pour out")),
)
ACTION_CATEGORIES={"pick":"manipulation","hold":"manipulation","move":"manipulation","place":"manipulation","release":"manipulation","carry":"transport","transfer":"transport","fill":"container","pour":"container","pour out":"container","open":"access","close":"access","stir":"tool use","cut":"tool use","place food":"food handling","hold food":"food handling"}
def matching_rules(name:str,category:str):return tuple(r for r in RULES if (r.match_field=="name" and name.casefold()==r.match_value) or (r.match_field=="category" and category.casefold()==r.match_value))
