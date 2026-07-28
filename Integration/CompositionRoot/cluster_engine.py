"""Deterministic semantic clustering of stored detection results."""
from collections import defaultdict


class ClusterEngine:
    def build(self, detections):
        groups=defaultdict(list)
        for item in detections:
            label=str(item.get("class_name") or "Object").strip()
            if label.casefold() in {"person","hand","arm","face","body"}:continue
            groups[label.casefold()].append(item)
        result=[]
        for key,instances in sorted(groups.items()):
            boxes=[x["bounding_box"] for x in instances];confidence=sum(x["confidence"] for x in instances)/len(instances)
            result.append({"id":f"cluster-{key.replace(' ','-')}","name":instances[0]["class_name"].title(),"instances":instances,"frame_count":len({x["frame"] for x in instances}),"confidence":confidence,"representative_frames":list(dict.fromkeys(x["frame"] for x in sorted(instances,key=lambda x:x["confidence"],reverse=True)))[:4],"bounding_box_statistics":{"average_width":sum(x["width"] for x in boxes)/len(boxes),"average_height":sum(x["height"] for x in boxes)/len(boxes)},"status":"pending"})
        return result
