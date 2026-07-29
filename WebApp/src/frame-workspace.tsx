import {useEffect,useRef,useState} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {AlertTriangle,Boxes,Check,ChevronDown,ChevronLeft,ChevronRight,ChevronsLeft,ChevronsRight,ChevronUp,ImageOff,Images,LayoutGrid,Maximize2,Merge,Minus,Pencil,Plus,Scissors,Send,Trash2,X,Sparkles} from 'lucide-react'
import type {Runtime} from './lib'
import {api} from './lib'
import './frame-workspace.css'
import './frame-clusters.css'

type Detection={class_name?:string;label?:string;confidence?:number;x:number;y:number;width:number;height:number}
type ManifestFrame={
  frame_id:string
  filename:string
  ordinal:number
  source_frame_number:number
  timestamp:number
  width:number
  height:number
  availability:'available'|'missing'
  available:boolean
  detection_status:string
  detections:Detection[]
  image_url:string
}
type FrameWorkspacePayload={
  session_id:string
  frames:ManifestFrame[]
  review:{current_frame_id:string|null;selected_frame_ids:string[]}
  detection:Record<string,any>
}
type ClusterRepresentative={frame_id:string;ordinal:number;filename:string;image_url:string;available:boolean}
type ClusterManifest={
  id:string
  name:string
  frame_count:number
  object_count:number
  confidence:number
  status:string
  review_state:string
  created_at:string
  selected:boolean
  expanded:boolean
  representative_frame:ClusterRepresentative|null
  representatives:ClusterRepresentative[]
  member_frames:string[]
}
type ClusterPayload={
  clusters:ClusterManifest[]
  selected_cluster_ids:string[]
  clustering:{state:string;progress:number;error?:string|null}
}

const FrameImage=({frame,className='',onLoad}:{frame:ManifestFrame;className?:string;onLoad?:()=>void})=>{
  const [failed,setFailed]=useState(!frame.available)
  useEffect(()=>setFailed(!frame.available),[frame.frame_id,frame.available])
  if(failed)return <div className={`frame-image-fallback ${className}`} role="img" aria-label={`${frame.filename} is unavailable`}><ImageOff/><span>Frame unavailable</span></div>
  return <img className={className} src={frame.image_url} alt={`Extracted frame ${frame.ordinal}`} loading="lazy" onLoad={onLoad} onError={()=>setFailed(true)}/>
}
const RepresentativeImage=({representative,label}:{representative:ClusterRepresentative;label:string})=>{
  const [failed,setFailed]=useState(!representative.available)
  if(failed)return <div className="cluster-image-fallback"><ImageOff/><span>Unavailable</span></div>
  return <img src={representative.image_url} alt={`${label}, representative frame ${representative.ordinal}`} loading="lazy" onError={()=>setFailed(true)}/>
}

export function FrameWorkspace({runtime,next,notify}:{runtime?:Runtime;next:()=>void;notify:(message:string)=>void}){
  const queryClient=useQueryClient()
  const workspace=useQuery({queryKey:['frame-workspace'],queryFn:()=>api<FrameWorkspacePayload>('/frame-workspace'),staleTime:5_000,refetchOnMount:'always'})
  const clusterQuery=useQuery({queryKey:['frame-workspace-clusters'],queryFn:()=>api<ClusterPayload>('/frame-workspace/clusters'),staleTime:5_000,refetchOnMount:'always'})
  const frames=workspace.data?.frames||[]
  const backendDetection=runtime?.workspace?.detection||workspace.data?.detection||{}
  const detectionFrames=backendDetection.frames||{}
  const running=backendDetection.state==='running'
  const [activeId,setActiveId]=useState<string|null>(null)
  const [selected,setSelected]=useState<Set<string>>(new Set())
  const [anchorId,setAnchorId]=useState<string|null>(null)
  const [gridSize,setGridSize]=useState<'small'|'medium'|'large'>('medium')
  const [boxes,setBoxes]=useState(true)
  const [zoom,setZoom]=useState(1)
  const [pan,setPan]=useState({x:0,y:0})
  const [dragging,setDragging]=useState(false)
  const [jump,setJump]=useState('')
  const [limit,setLimit]=useState(120)
  const [actionError,setActionError]=useState('')
  const [clusterOpen,setClusterOpen]=useState(false)
  const [clusterBusy,setClusterBusy]=useState('')
  const rootRef=useRef<HTMLDivElement>(null)
  const gridRef=useRef<HTMLDivElement>(null)
  const dragRef=useRef({x:0,y:0,panX:0,panY:0})
  const hydratedReview=useRef('')

  useEffect(()=>{
    if(!workspace.data)return
    const signature=`${workspace.data.session_id}:${workspace.data.review.current_frame_id||''}:${workspace.data.review.selected_frame_ids.join(',')}`
    if(hydratedReview.current===signature)return
    hydratedReview.current=signature
    const availableIds=new Set(workspace.data.frames.map(frame=>frame.frame_id))
    const restored=workspace.data.review.selected_frame_ids.filter(id=>availableIds.has(id))
    const fallback=workspace.data.frames[0]?.frame_id||null
    const current=availableIds.has(workspace.data.review.current_frame_id||'')?workspace.data.review.current_frame_id:fallback
    setActiveId(current)
    setSelected(new Set(restored.length?restored:current?[current]:[]))
    setAnchorId(current)
  },[workspace.data])

  useEffect(()=>{
    if(!hydratedReview.current)return
    const timer=window.setTimeout(()=>{
      fetch('/frame-workspace/review',{
        method:'PATCH',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({current_frame_id:activeId,selected_frame_ids:[...selected]}),
      }).catch(()=>undefined)
    },150)
    return()=>window.clearTimeout(timer)
  },[activeId,selected])

  useEffect(()=>{
    if(!workspace.data)return
    void workspace.refetch()
  // Refetch the authoritative projection as backend detection advances.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[backendDetection.state,backendDetection.current])

  const activeIndex=Math.max(0,frames.findIndex(frame=>frame.frame_id===activeId))
  const active=frames[activeIndex]
  const liveEntry=active?detectionFrames[String(active.ordinal)]||{}:{}
  const detections=(liveEntry.labels||active?.detections||[]) as Detection[]
  const visibleFrames=frames.slice(0,limit)
  const size={small:140,medium:180,large:220}[gridSize]
  const processed=Number(backendDetection.metrics?.processed||0)
  const percent=frames.length?Math.min(100,Math.round(processed/frames.length*100)):0
  const clusters=clusterQuery.data?.clusters||[]
  const selectedClusterIds=clusterQuery.data?.selected_cluster_ids||[]
  const clustering=clusterBusy==='generate'||clusterQuery.data?.clustering?.state==='running'
  const canCluster=clusters.length>0||['complete','partial'].includes(String(backendDetection.state))

  useEffect(()=>{if(clusters.length)setClusterOpen(true)},[clusters.length])

  useEffect(()=>{
    if(activeIndex>=limit)setLimit(Math.min(frames.length,activeIndex+40))
    requestAnimationFrame(()=>gridRef.current?.querySelectorAll<HTMLElement>('[data-frame-id]')[activeIndex]?.scrollIntoView({block:'nearest',behavior:'smooth'}))
  },[activeId,activeIndex,frames.length,limit])

  useEffect(()=>{setZoom(1);setPan({x:0,y:0})},[activeId])

  const saveReview=async()=>{
    const response=await fetch('/frame-workspace/review',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_frame_id:activeId,selected_frame_ids:[...selected]})})
    if(!response.ok)throw new Error(await response.text())
  }

  const selectFrame=(frame:ManifestFrame,event:{shiftKey:boolean;ctrlKey:boolean;metaKey:boolean})=>{
    setActiveId(frame.frame_id)
    if(event.shiftKey&&anchorId){
      const start=frames.findIndex(item=>item.frame_id===anchorId)
      const end=frames.findIndex(item=>item.frame_id===frame.frame_id)
      if(start>=0&&end>=0)setSelected(new Set(frames.slice(Math.min(start,end),Math.max(start,end)+1).map(item=>item.frame_id)))
    }else if(event.ctrlKey||event.metaKey){
      setSelected(previous=>{const next=new Set(previous);if(next.has(frame.frame_id))next.delete(frame.frame_id);else next.add(frame.frame_id);return next})
      setAnchorId(frame.frame_id)
    }else{
      setSelected(new Set([frame.frame_id]))
      setAnchorId(frame.frame_id)
    }
  }

  const go=(index:number,extend=false)=>{
    if(!frames.length)return
    const bounded=Math.max(0,Math.min(frames.length-1,index)),frame=frames[bounded]
    setActiveId(frame.frame_id)
    if(extend&&anchorId){
      const anchor=Math.max(0,frames.findIndex(item=>item.frame_id===anchorId))
      setSelected(new Set(frames.slice(Math.min(anchor,bounded),Math.max(anchor,bounded)+1).map(item=>item.frame_id)))
    }else{
      setSelected(new Set([frame.frame_id]))
      setAnchorId(frame.frame_id)
    }
  }

  const handleKey=(event:React.KeyboardEvent)=>{
    if((event.target as HTMLElement).matches('input,textarea'))return
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='a'){event.preventDefault();setSelected(new Set(frames.map(frame=>frame.frame_id)));return}
    const target=event.key==='ArrowLeft'?activeIndex-1:event.key==='ArrowRight'?activeIndex+1:event.key==='Home'?0:event.key==='End'?frames.length-1:null
    if(target!==null){event.preventDefault();go(target,event.shiftKey)}
  }

  const runDetection=async()=>{
    setActionError('')
    setClusterOpen(false)
    try{
      const response=await fetch('/detection/run',{method:'POST',cache:'no-store'})
      const result=await response.json()
      if(!response.ok||!result.accepted)throw new Error(result.reason||'Detection could not start.')
      await queryClient.invalidateQueries({queryKey:['frame-workspace']})
      await queryClient.invalidateQueries({queryKey:['frame-workspace-clusters']})
      notify('Frame detection complete')
    }catch(reason){const message=reason instanceof Error?reason.message:'Detection failed';setActionError(message);notify(message)}
  }

  const cancelDetection=async()=>{
    try{
      const response=await fetch('/detection/cancel',{method:'POST'})
      const result=await response.json()
      if(!response.ok)throw new Error(result.detail||'Detection could not be cancelled.')
      await queryClient.invalidateQueries({queryKey:['frame-workspace-clusters']})
      notify(result.cancelled?'Cancelling frame detection…':'No detection is currently running')
    }catch(reason){const message=reason instanceof Error?reason.message:'Detection cancellation failed';setActionError(message);notify(message)}
  }

  const setClusterData=(payload:ClusterPayload)=>queryClient.setQueryData(['frame-workspace-clusters'],payload)
  const clusterRequest=async(path:string,method='POST',body?:unknown,busy=path)=>{
    setClusterBusy(busy);setActionError('')
    try{
      const response=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined})
      const payload=await response.json()
      if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:payload.detail?.message||'Cluster operation failed.')
      setClusterData(payload)
      setClusterOpen(true)
      return payload as ClusterPayload
    }catch(reason){
      const message=reason instanceof Error?reason.message:'Cluster operation failed.'
      setActionError(message);notify(message);throw reason
    }finally{setClusterBusy('')}
  }

  const generateClusters=async()=>{
    if(clusters.length){setClusterOpen(true);return}
    try{
      const payload=await clusterRequest('/frame-workspace/clusters/generate','POST',undefined,'generate')
      notify(`${payload.clusters.length} clusters generated`)
    }catch{/* Error is surfaced by clusterRequest. */}
  }

  const updateClusterReview=async(selectedIds=selectedClusterIds,expandedIds=clusters.filter(cluster=>cluster.expanded).map(cluster=>cluster.id))=>{
    try{await clusterRequest('/frame-workspace/clusters/review','PATCH',{selected_cluster_ids:selectedIds,expanded_cluster_ids:expandedIds},'review')}
    catch{/* Error is surfaced by clusterRequest. */}
  }

  const renameCluster=async(cluster:ClusterManifest)=>{
    const name=window.prompt('Cluster name',cluster.name)?.trim()
    if(!name||name===cluster.name)return
    try{await clusterRequest(`/frame-workspace/clusters/${encodeURIComponent(cluster.id)}`,'PATCH',{name},`rename-${cluster.id}`);notify(`Cluster renamed to ${name}`)}
    catch{/* Error is surfaced by clusterRequest. */}
  }

  const mergeClusters=async()=>{
    if(selectedClusterIds.length<2){setActionError('Select at least two clusters to merge.');return}
    try{await clusterRequest('/frame-workspace/clusters/merge','POST',{cluster_ids:selectedClusterIds},'merge');notify('Selected clusters merged')}
    catch{/* Error is surfaced by clusterRequest. */}
  }

  const splitCluster=async(cluster:ClusterManifest)=>{
    try{await clusterRequest(`/frame-workspace/clusters/${encodeURIComponent(cluster.id)}/split`,'POST',undefined,`split-${cluster.id}`);notify(`${cluster.name} split into two clusters`)}
    catch{/* Error is surfaced by clusterRequest. */}
  }

  const deleteCluster=async(cluster:ClusterManifest)=>{
    if(!window.confirm(`Delete cluster ${cluster.name}?`))return
    try{await clusterRequest(`/frame-workspace/clusters/${encodeURIComponent(cluster.id)}`,'DELETE',undefined,`delete-${cluster.id}`);notify(`${cluster.name} deleted`)}
    catch{/* Error is surfaced by clusterRequest. */}
  }

  const handoffClusters=async()=>{
    setClusterBusy('handoff');setActionError('')
    try{
      const response=await fetch('/frame-workspace/clusters/handoff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cluster_ids:selectedClusterIds})})
      const payload=await response.json()
      if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:payload.detail?.message||'Cluster handoff failed.')
      setClusterData(payload.clusters)
      await queryClient.invalidateQueries({queryKey:['objects']})
      notify(`${payload.created.length} object${payload.created.length===1?'':'s'} sent to Object Library`)
      next()
    }catch(reason){const message=reason instanceof Error?reason.message:'Cluster handoff failed.';setActionError(message);notify(message)}
    finally{setClusterBusy('')}
  }

  const jumpToFrame=()=>{
    const value=Number(jump)
    if(!Number.isInteger(value)||value<1||value>frames.length){setActionError(`Enter a frame number between 1 and ${frames.length}.`);return}
    setActionError('');go(value-1)
  }

  const fit=()=>{setZoom(1);setPan({x:0,y:0})}
  const zoomBy=(amount:number)=>setZoom(value=>Math.min(8,Math.max(.5,Number((value+amount).toFixed(2)))))

  if(workspace.isLoading)return <div className="frame-workspace-state"><span className="frame-loader"/><h2>Loading Frame Workspace…</h2></div>
  if(workspace.isError)return <div className="frame-workspace-state error"><AlertTriangle/><h2>Frame Workspace unavailable</h2><p>{workspace.error instanceof Error?workspace.error.message:'Could not load the frame manifest.'}</p><button onClick={()=>void workspace.refetch()}>Retry</button></div>

  return <div className="frame-review" ref={rootRef} tabIndex={0} onKeyDown={handleKey} aria-label="Frame Workspace">
    <header className="frame-review-toolbar">
      <div><span className="eyebrow">02 / DATASET CURATION</span><h1>Frame Workspace</h1><small>{frames.length?`${frames.length} authoritative frames`:'No extracted frames'}</small></div>
      <div className="frame-toolbar-actions">
        <button disabled={!frames.length} onClick={()=>setGridSize(value=>value==='small'?'medium':value==='medium'?'large':'small')}><LayoutGrid/> {gridSize} · {size}px</button>
        <button disabled={!frames.length||activeIndex===0} onClick={()=>go(0)} title="First frame"><ChevronsLeft/> First</button>
        <button disabled={!frames.length||activeIndex===0} onClick={()=>go(activeIndex-1)}><ChevronLeft/> Previous</button>
        <button disabled={!frames.length||activeIndex===frames.length-1} onClick={()=>go(activeIndex+1)}>Next <ChevronRight/></button>
        <button disabled={!frames.length||activeIndex===frames.length-1} onClick={()=>go(frames.length-1)} title="Last frame">Last <ChevronsRight/></button>
        <span className="frame-jump"><input aria-label="Jump to frame number" disabled={!frames.length} type="number" min="1" max={frames.length||1} value={jump} onChange={event=>setJump(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')jumpToFrame()}} placeholder="#"/><button disabled={!frames.length} onClick={jumpToFrame}>Go</button></span>
        <button className="cluster-button" disabled={!canCluster||clustering||running} onClick={()=>void generateClusters()}><Boxes/> {clustering?'Clustering…':'Generate Clusters'}</button>
        {running?<button onClick={()=>void cancelDetection()}><Minus/> Cancel Detection</button>:<button className="primary" disabled={!frames.length} onClick={()=>void runDetection()}><Sparkles/> Run YOLO Model</button>}
      </div>
    </header>

    {!frames.length?<main className="frame-empty"><Images/><h2>No Frames Available</h2><p>Import and extract a video first.</p></main>:<>
      {running&&<div className="frame-detection-progress" role="status"><Sparkles/><div><small>PROCESSING DATASET</small><b>{processed} of {frames.length} frames</b><span><i style={{width:`${percent}%`}}/></span></div><strong>{percent}%</strong></div>}
      {clustering&&<div className="cluster-progress" role="status"><span className="frame-loader"/><div><small>GENERATING CLUSTERS</small><b>Grouping detected objects using backend feature embeddings…</b></div></div>}
      {actionError&&<div className="frame-error" role="alert"><AlertTriangle/>{actionError}<button onClick={()=>setActionError('')}>Dismiss</button></div>}
      <main className="frame-review-body">
        <section className="frame-grid-panel">
          <header><span><b>{frames.length}</b> Frames</span><span>{selected.size} selected</span><button onClick={()=>setSelected(new Set(frames.map(frame=>frame.frame_id)))}>Select All</button><button disabled={!selected.size} onClick={()=>setSelected(new Set())}>Deselect All</button></header>
          <div className="manifest-grid" ref={gridRef} style={{gridTemplateColumns:`repeat(auto-fill,minmax(${size}px,1fr))`}}>
            {visibleFrames.map(frame=>{
              const entry=detectionFrames[String(frame.ordinal)]||{},status=entry.status||frame.detection_status||'waiting'
              return <button type="button" data-frame-id={frame.frame_id} key={frame.frame_id} aria-selected={selected.has(frame.frame_id)} className={`${activeId===frame.frame_id?'active':''} ${selected.has(frame.frame_id)?'selected':''} status-${status} ${!frame.available?'unavailable':''}`} onClick={event=>selectFrame(frame,event)}>
                <div><FrameImage frame={frame}/><em>{frame.available?String(status).replace('_',' '):'missing'}</em>{selected.has(frame.frame_id)&&<span className="selection-check"><Check/></span>}</div>
                <span><b>Frame {String(frame.ordinal).padStart(4,'0')}</b><small>{frame.timestamp.toFixed(3)}s · source #{frame.source_frame_number}</small></span>
              </button>
            })}
            {limit<frames.length&&<button className="load-more" onClick={()=>setLimit(value=>Math.min(frames.length,value+120))}>Load {Math.min(120,frames.length-limit)} more frames</button>}
          </div>
        </section>

        <aside className="frame-inspector-panel">
          <header><div><b>Frame {String(active.ordinal).padStart(4,'0')}</b><small>{active.filename}</small></div><div><button aria-label="Zoom out" onClick={()=>zoomBy(-.25)}><Minus/></button><button aria-label="Zoom in" onClick={()=>zoomBy(.25)}><Plus/></button><button onClick={fit}><Maximize2/> Fit</button><button className={boxes?'active':''} onClick={()=>setBoxes(value=>!value)}><Check/> Boxes</button></div></header>
          <div className={`frame-stage-viewport ${dragging?'dragging':''}`}
            onWheel={event=>zoomBy(event.deltaY<0?.15:-.15)}
            onPointerDown={event=>{if(zoom<=1)return;setDragging(true);dragRef.current={x:event.clientX,y:event.clientY,panX:pan.x,panY:pan.y};event.currentTarget.setPointerCapture(event.pointerId)}}
            onPointerMove={event=>{if(!dragging)return;setPan({x:dragRef.current.panX+event.clientX-dragRef.current.x,y:dragRef.current.panY+event.clientY-dragRef.current.y})}}
            onPointerUp={event=>{setDragging(false);event.currentTarget.releasePointerCapture(event.pointerId)}}>
            <div className="frame-image-stage" style={{aspectRatio:`${active.width||16}/${active.height||9}`,transform:`translate(${pan.x}px,${pan.y}px) scale(${zoom})`}}>
              <FrameImage frame={active}/>
              {boxes&&active.available&&detections.map((detection,index)=><div className="manifest-bbox" key={`${detection.class_name||detection.label||'object'}-${index}`} style={{left:`${detection.x/active.width*100}%`,top:`${detection.y/active.height*100}%`,width:`${detection.width/active.width*100}%`,height:`${detection.height/active.height*100}%`}}><span>{detection.class_name||detection.label||'Object'} <b>{(Number(detection.confidence||0)*100).toFixed(1)}%</b></span></div>)}
            </div>
          </div>
          <div className="frame-inspector-meta">
            <span><small>FRAME ID</small><b title={active.frame_id}>{active.frame_id}</b></span><span><small>SOURCE FRAME</small><b>{active.source_frame_number}</b></span><span><small>TIMESTAMP</small><b>{active.timestamp.toFixed(3)} s</b></span><span><small>RESOLUTION</small><b>{active.width} × {active.height}</b></span><span><small>STATUS</small><b>{active.available?liveEntry.status||active.detection_status:'Missing'}</b></span><span><small>ZOOM</small><b>{Math.round(zoom*100)}%</b></span>
          </div>
          <div className="frame-detections"><header><span>Detection</span><span>Confidence</span><span>Bounds</span></header>{detections.map((item,index)=><div key={index}><span>{item.class_name||item.label||'Object'}</span><span>{(Number(item.confidence||0)*100).toFixed(1)}%</span><span>{item.x}, {item.y} · {item.width}×{item.height}</span></div>)}{!detections.length&&<p>{running?'Waiting for this frame…':'No detections for this frame.'}</p>}</div>
        </aside>
      </main>
      {clusterOpen&&<section className="cluster-review" aria-label="Cluster Review">
        <header><div><Boxes/><span><b>Cluster Review</b><small>{clusters.length} clusters · {selectedClusterIds.length} selected</small></span></div><div><button disabled={selectedClusterIds.length<2||Boolean(clusterBusy)} onClick={()=>void mergeClusters()}><Merge/> Merge Selected</button><button aria-label="Close cluster review" onClick={()=>setClusterOpen(false)}><X/></button></div></header>
        {clusterQuery.isError?<div className="cluster-empty error"><AlertTriangle/><b>Cluster manifest unavailable</b><button onClick={()=>void clusterQuery.refetch()}>Retry</button></div>:!clusters.length?<div className="cluster-empty"><Boxes/><b>No clusters generated</b><span>Run YOLO, then select Generate Clusters.</span></div>:<div className="cluster-cards">{clusters.map(cluster=><article className={`${cluster.selected?'selected':''} ${cluster.expanded?'expanded':''}`} key={cluster.id}>
          <button className="cluster-select" aria-label={`${cluster.selected?'Deselect':'Select'} ${cluster.name}`} aria-pressed={cluster.selected} onClick={()=>void updateClusterReview(cluster.selected?selectedClusterIds.filter(id=>id!==cluster.id):[...selectedClusterIds,cluster.id])}><i>{cluster.selected&&<Check/>}</i></button>
          <button className="cluster-summary" onClick={()=>void updateClusterReview(selectedClusterIds,cluster.expanded?clusters.filter(item=>item.expanded&&item.id!==cluster.id).map(item=>item.id):[...clusters.filter(item=>item.expanded).map(item=>item.id),cluster.id])}>
            <div className="cluster-thumbnail">{cluster.representative_frame?<RepresentativeImage representative={cluster.representative_frame} label={cluster.name}/>:<div className="cluster-image-fallback"><ImageOff/><span>No representative</span></div>}</div>
            <span><b>{cluster.name}</b><small>{cluster.object_count} objects · {cluster.frame_count} frames</small><em>{cluster.review_state}</em></span>
            <strong>{(cluster.confidence*100).toFixed(1)}%</strong>
            {cluster.expanded?<ChevronUp/>:<ChevronDown/>}
          </button>
          <div className="cluster-card-actions"><button onClick={()=>void renameCluster(cluster)} title="Rename cluster"><Pencil/> Rename</button><button disabled={cluster.object_count<2} onClick={()=>void splitCluster(cluster)} title="Split cluster"><Scissors/> Split</button><button onClick={()=>void deleteCluster(cluster)} title="Delete cluster"><Trash2/> Delete</button></div>
          {cluster.expanded&&<div className="cluster-expanded"><div className="cluster-representatives">{cluster.representatives.map(representative=><button key={representative.frame_id} onClick={()=>{const index=frames.findIndex(frame=>frame.frame_id===representative.frame_id);if(index>=0)go(index)}}><RepresentativeImage representative={representative} label={cluster.name}/><span>Frame {representative.ordinal}</span></button>)}</div><dl><span><dt>Cluster ID</dt><dd title={cluster.id}>{cluster.id}</dd></span><span><dt>Created</dt><dd>{cluster.created_at}</dd></span><span><dt>Members</dt><dd>{cluster.member_frames.length}</dd></span><span><dt>Status</dt><dd>{cluster.status}</dd></span></dl></div>}
        </article>)}</div>}
      </section>}
      <footer className="frame-review-status"><span>Current <b>{active.ordinal} / {frames.length}</b></span><span>Frames Selected <b>{selected.size}</b></span><span>Clusters Selected <b>{selectedClusterIds.length}</b></span><span>Detection <b>{backendDetection.state||'idle'}</b></span>{clusters.length?<button className="primary" disabled={!selectedClusterIds.length||clusterBusy==='handoff'} onClick={()=>void handoffClusters()}><Send/> {clusterBusy==='handoff'?'Sending…':'Send Selected Cluster(s) To Object Library'}</button>:<button className="primary" disabled={!selected.size} onClick={async()=>{try{await saveReview();next()}catch(reason){setActionError(reason instanceof Error?reason.message:'Could not save frame selection.')}}}>Continue to Object Library <ChevronRight/></button>}</footer>
    </>}
  </div>
}
