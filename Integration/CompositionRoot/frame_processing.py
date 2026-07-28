"""Simple project-owned frame detection orchestration."""
from pathlib import Path
from time import monotonic


class FrameProcessingService:
    def __init__(self, runtime, logger, publish):
        self.runtime, self.workspace, self.log, self.publish = runtime, runtime.video_workspace, logger, publish

    def run(self):
        total = len(self.workspace.frames)
        if not total:
            raise ValueError("No extracted frames")
        started = monotonic()
        state = {"state":"running","phase":"warming_up","current":0,"current_label":"Loading YOLO model","total":total,"eta":0.0,"frame":0,"frames":{str(i):{"status":"waiting","labels":[],"overlay_ready":False} for i in range(1,total+1)},"metrics":{"processed":0,"failed":0,"detected_objects":0,"average_inference_ms":0.0,"inference_ms":0.0,"fps":0.0},"inference_samples":[]}
        self.workspace.web_detection = state
        self.workspace.web_clusters = {"renamed":{},"ignored":[],"deleted":[],"accepted":[],"generated":[]}
        self.log(f"BATCH START model={self.runtime.perception.detector_status().get('current')} frames={total}")

        def started_frame(number, name):
            state.update(phase="detecting",current=number,frame=number,frame_name=name,current_label="Scanning")
            state["frames"][str(number)]={"status":"processing","labels":[],"overlay_ready":False}
            self.log(f"FRAME {number} STARTED")
            self.publish()

        def progress(current, count, eta, name):
            state.update(current=current,total=count,eta=eta,frame=current,frame_name=name)

        def finished(index, elapsed_ms):
            number=index+1;failed=next((x for x in self.workspace.errors if x.get("frame")==number),None);result=self.workspace.results.get(index)
            labels=[{"class_name":x.properties.get("ai_class") or "Object","confidence":x.confidence,"object_id":x.candidate_id,"x":x.region.x,"y":x.region.y,"width":x.region.width,"height":x.region.height} for x in result[1].objects] if result else []
            status="error" if failed else "detected" if labels else "no_detection"
            state["frames"][str(number)]={"status":status,"labels":labels,"overlay_ready":bool(result and Path(result[3]).is_file()),"overlay":f"/frames/{Path(result[3]).name}" if result else None,"inference_ms":elapsed_ms}
            samples=state["inference_samples"];samples.append(float(elapsed_ms));processed=sum(x["status"] in {"detected","no_detection","error"} for x in state["frames"].values());failures=sum(x["status"]=="error" for x in state["frames"].values());objects=sum(len(x.get("labels",[])) for x in state["frames"].values());elapsed=max(.001,monotonic()-started)
            state["metrics"].update(processed=processed,failed=failures,detected_objects=objects,average_inference_ms=sum(samples)/len(samples),inference_ms=elapsed_ms,fps=processed/elapsed)
            state.update(current=number,frame=number,current_label=labels[0]["class_name"] if labels else "No object")
            summary=", ".join(f"{x['class_name']}:{x['confidence']:.3f}" for x in labels) or "none"
            self.log(f"FRAME {number} FINISHED inference_ms={elapsed_ms:.1f} status={status} labels={summary}")
            self.publish()

        def done(completed,error):
            state.update(state="complete" if completed else "error",phase="complete" if completed else "stopped",current=total if completed else state["current"],frame=total if completed else state["frame"],eta=0.0,error=error)
            state["metrics"]["total_runtime_seconds"]=max(.001,monotonic()-started)
            self.log(f"BATCH {'COMPLETE' if completed else 'FAILED'} processed={state['metrics']['processed']} error={error}")
            self.publish()

        self.workspace.detect_all(started_frame,progress,finished,done)
        return state
