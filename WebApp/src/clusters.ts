import {teachable,type AppData} from './lib'
export type ClusterState='Ready'|'Accepted'|'Rejected'|'Ignored'
export type Cluster={id:string;name:string;instances:any[];confidence:number;state:ClusterState}
export function buildClusters(data:AppData):Cluster[]{
  const groups=new Map<string,any[]>()
  for(const detection of (data.detections?.detections||[]).filter(teachable)){
    const key=String(detection.class_name||'object').trim().toLowerCase()
    groups.set(key,[...(groups.get(key)||[]),detection])
  }
  return [...groups].map(([name,instances])=>({id:`cluster-${name.replace(/\W+/g,'-')}`,name:name.replace(/^./,x=>x.toUpperCase()),instances,confidence:instances.reduce((sum,x)=>sum+Number(x.confidence||0),0)/instances.length,state:'Ready'}))
}
export type FrameState='Extracted'|'Queued'|'Processing'|'Detected'|'Reviewed'|'Accepted'|'Rejected'
export function frameState(frame:number,data:AppData):FrameState{
  const rows=(data.detections?.detections||[]).filter((x:any)=>x.frame===frame)
  const status=String(rows[0]?.status||'').toLowerCase()
  if(status.includes('accept'))return 'Accepted';if(status.includes('reject'))return 'Rejected';if(status.includes('review'))return 'Reviewed'
  const processed=Number(data.runtime?.workspace.processed||0),total=Number(data.runtime?.workspace.frames||0)
  if(rows.length||frame<=processed)return 'Detected';if(frame===processed+1&&processed<total)return 'Processing';if(frame<=total)return 'Queued';return 'Extracted'
}
