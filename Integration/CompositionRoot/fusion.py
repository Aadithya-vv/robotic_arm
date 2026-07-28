"""Multi-scale proposal fusion, duplicate removal, and NMS."""


def iou(first, second):
    left, top = max(first[0], second[0]), max(first[1], second[1]); right = min(first[0]+first[2], second[0]+second[2]); bottom = min(first[1]+first[3], second[1]+second[3])
    intersection = max(0, right-left) * max(0, bottom-top); union = first[2]*first[3] + second[2]*second[3] - intersection
    return 0.0 if union <= 0 else intersection / union


def non_maximum_suppression(proposals, threshold=0.45):
    """Suppress immutable VisualObject instances using attribute access exclusively."""
    ordered = sorted(proposals, key=lambda item: (-item.confidence, item.region.x, item.region.y))
    kept = []
    for proposal in ordered:
        box = (proposal.region.x, proposal.region.y, proposal.region.width, proposal.region.height)
        if all(iou(box, (existing.region.x, existing.region.y, existing.region.width, existing.region.height)) < threshold for existing in kept): kept.append(proposal)
    return tuple(kept)
