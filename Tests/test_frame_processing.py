import sys,unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
COMPOSITION=ROOT/"Integration"/"CompositionRoot"
if str(COMPOSITION) not in sys.path:sys.path.insert(0,str(COMPOSITION))

from cluster_engine import ClusterEngine
from frame_processing import FrameProcessingService
from object_library_service import ObjectLibraryService
from gpu_runtime import accelerator_diagnostics


class FakeWorkspace:
    def __init__(self):
        self.frames=[Path("frame0001.png"),Path("frame0002.png")];self.results={};self.errors=[];self.web_detection={};self.web_clusters={}
    def detect_all(self,started,progress,finished,done):
        for index,path in enumerate(self.frames,1):
            started(index,path.name);progress(index,len(self.frames),0,path.name);finished(index-1,10.0+index)
        done(True,None)


class FrameProcessingTests(unittest.TestCase):
    def test_accelerator_diagnostics_are_cached_for_safe_inference_polling(self):
        accelerator_diagnostics.cache_clear();first=accelerator_diagnostics();second=accelerator_diagnostics()
        self.assertIs(first,second);self.assertEqual(accelerator_diagnostics.cache_info().hits,1)

    def test_batch_processes_every_frame_synchronously(self):
        workspace=FakeWorkspace();runtime=SimpleNamespace(video_workspace=workspace,perception=SimpleNamespace(detector_status=lambda:{"current":"YOLO11N"}));events=[]
        state=FrameProcessingService(runtime,events.append,lambda:None).run()
        self.assertEqual(state["state"],"complete");self.assertEqual(state["metrics"]["processed"],2)
        self.assertEqual([state["frames"][str(i)]["status"] for i in (1,2)],["no_detection","no_detection"])
        self.assertTrue(any("FRAME 1 STARTED" in event for event in events));self.assertTrue(any("BATCH COMPLETE" in event for event in events))

    def test_clusters_are_grouped_by_semantic_label(self):
        rows=[{"frame":1,"class_name":"Bottle","confidence":.9,"bounding_box":{"width":10,"height":20}},{"frame":2,"class_name":"bottle","confidence":.7,"bounding_box":{"width":14,"height":24}},{"frame":2,"class_name":"Cup","confidence":.8,"bounding_box":{"width":8,"height":9}}]
        clusters=ClusterEngine().build(rows)
        bottle=next(x for x in clusters if x["name"]=="Bottle")
        self.assertEqual(bottle["frame_count"],2);self.assertAlmostEqual(bottle["confidence"],.8);self.assertEqual(bottle["bounding_box_statistics"]["average_width"],12)

    def test_accepted_cluster_creates_semantic_object_without_moving_frames(self):
        class Library:
            def __init__(self):self.items=[]
            def list(self):return self.items
            def create(self,fields,crop,descriptors):self.items.append({"object_id":"object-1",**fields,"thumbnail":crop})
        cluster={"name":"Bottle","frame_count":2,"confidence":.8,"representative_frames":[1,2],"instances":[{"frame":1,"bounding_box":{"x":1,"y":2,"width":10,"height":20}}]};library=Library()
        created=ObjectLibraryService(library).create_from_cluster(cluster,{})
        self.assertEqual(created["name"],"Bottle");self.assertEqual(created["thumbnail"]["path"],"");self.assertEqual(created["thumbnail"]["source_frames"],[1,2])


if __name__=="__main__":unittest.main()
