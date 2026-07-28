from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class PlanningRule:rule_id:str;goal:str;object_terms:tuple[str,...];actions:tuple[str,...];success:tuple[str,...]
RULES=(
 PlanningRule("planner.pour-water","pour water",("bottle",),("pick","carry","pour","place"),("water poured", "bottle placed")),
 PlanningRule("planner.stir","stir",("spoon",),("pick","stir","place"),("contents stirred", "spoon placed")),
 PlanningRule("planner.fill-container","fill container",("bottle","cup","container"),("pick","fill","place"),("container filled", "container placed")),
)
def rule_for(goal):
    key=" ".join(str(goal).strip().casefold().split())
    return next((r for r in RULES if r.goal==key),None)

