"""Semantic cluster to permanent object conversion."""
from pathlib import Path
import shutil
from uuid import uuid4


class ObjectLibraryService:
    def __init__(self, library):self.library=library
    def create_from_cluster(self, cluster, fields):
        instances=sorted(cluster["instances"],key=lambda item:(-float(item.get("confidence",0.0)),int(item["frame"])));representative=instances[0];box=representative["bounding_box"]
        saved,thumbnail=self._save_instances(instances,representative)
        source_frames=sorted(set(cluster.get("representative_frames",()))|{item["frame"] for item in instances})
        semantic={"path":thumbnail,"frame_id":f"video-frame-{representative['frame']}","confidence":float(representative.get("confidence",0.0)),"x":box["x"],"y":box["y"],"width":box["width"],"height":box["height"],"instance_images":saved,"source_frames":source_frames}
        values={"name":fields.get("name") or cluster["name"],"description":fields.get("description",f"Semantic object generated from {cluster['frame_count']} detected frames."),"category":fields.get("category","Detected Objects"),"notes":fields.get("notes",""),"tags":fields.get("tags",""),"aliases":fields.get("aliases",""),"material":fields.get("material",""),"color":fields.get("color",""),"properties":fields.get("properties",{}),"metadata":fields.get("metadata",{}),"confidence":cluster["confidence"]}
        existing=next((item for item in self.library.list() if str(item.get("name","")).casefold()==str(values["name"]).casefold()),None)
        if existing is not None and hasattr(self.library,"replace_capture"):
            self.library.replace_capture(existing["object_id"],semantic,representative.get("confidence",cluster["confidence"]));return next(item for item in self.library.list() if item["object_id"]==existing["object_id"])
        before={x["object_id"] for x in self.library.list()};self.library.create(values,semantic,())
        return next(x for x in self.library.list() if x["object_id"] not in before)

    def _save_instances(self,instances,representative):
        storage=Path(getattr(self.library,"_storage_path",""))
        if not storage.name:return [],""
        root=storage.resolve().parents[2];target=root/"Assets"/"ObjectLibrary"/"instances"/uuid4().hex
        saved=[];representative_path=None
        for item in instances:
            number=int(item["frame"]);source=root/"Workspace"/"Frames"/"Detected"/f"frame{number:04d}.png"
            if not source.is_file():source=root/"Workspace"/"Frames"/f"frame{number:04d}.png"
            if source.is_file():
                target.mkdir(parents=True,exist_ok=True);destination=target/source.name;shutil.copy2(source,destination);saved.append(str(destination))
                if number==int(representative["frame"]):representative_path=destination
        if representative_path is None:return saved,""
        thumbnail=target/"thumbnail.png"
        try:
            import cv2
            image=cv2.imread(str(representative_path));box=representative.get("bounding_box",{})
            x=max(0,int(box.get("x",0)));y=max(0,int(box.get("y",0)));width=int(box.get("width",0));height=int(box.get("height",0))
            if image is not None and width>0 and height>0:
                crop=image[y:min(image.shape[0],y+height),x:min(image.shape[1],x+width)]
                if crop.size and cv2.imwrite(str(thumbnail),crop):return saved,str(thumbnail)
        except Exception:
            pass
        shutil.copy2(representative_path,thumbnail)
        return saved,str(thumbnail)
