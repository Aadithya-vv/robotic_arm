"""Short-window candidate smoothing and recovery before Scene tracking."""
from taskgraph_vision import BoundingRegion, VisualObject
from fusion import iou


class TemporalStabilizer:
    def __init__(self, alpha=0.65, recovery_frames=2):
        self.alpha = alpha; self.recovery_frames = recovery_frames; self._tracks = {}; self._next = 1

    def update(self, candidates):
        unmatched = set(self._tracks); output = []; next_tracks = {}
        for candidate in sorted(candidates, key=lambda item: (-item.confidence, item.candidate_id)):
            box = (candidate.region.x, candidate.region.y, candidate.region.width, candidate.region.height)
            matches = sorted(((iou(box, self._tracks[key][0]), key) for key in unmatched), reverse=True)
            key = matches[0][1] if matches and matches[0][0] >= 0.25 else None
            if key is None:
                key = f"temporal-{self._next}"; self._next += 1; stable = candidate
            else:
                unmatched.remove(key); previous = self._tracks[key][0]; old = previous.region; new = candidate.region; a = self.alpha
                region = BoundingRegion(round(a*new.x+(1-a)*old.x), round(a*new.y+(1-a)*old.y), max(1,round(a*new.width+(1-a)*old.width)), max(1,round(a*new.height+(1-a)*old.height)))
                stable = VisualObject(key, region, a*candidate.confidence+(1-a)*previous.confidence, candidate.features, {**dict(candidate.properties), "temporally_stable": True})
            next_tracks[key] = (stable, 0); output.append(stable)
        for key in sorted(unmatched):
            previous, missed = self._tracks[key]; missed += 1
            if missed <= self.recovery_frames:
                recovered = VisualObject(key, previous.region, previous.confidence*0.85, previous.features, {**dict(previous.properties), "temporally_recovered": True})
                next_tracks[key] = (recovered, missed); output.append(recovered)
        self._tracks = next_tracks
        return tuple(sorted(output, key=lambda item: item.candidate_id))

    def reset(self): self._tracks.clear(); self._next = 1
