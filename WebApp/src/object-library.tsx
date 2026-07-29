import {useEffect,useMemo,useState} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {AlertTriangle,Box,Boxes,Check,ChevronDown,Copy,Filter,FolderInput,ImageOff,LayoutGrid,List,Maximize2,Minus,Pencil,Plus,RefreshCw,RotateCcw,Search,Square,Trash2,X} from 'lucide-react'
import './object-library.css'

type Category={category_id:string;name:string;created:string;updated:string}
export type ManifestObject={
  object_id:string;name:string;category:string;type:string;description:string;tags:string[];aliases:string[]
  properties:Record<string,unknown>;metadata:Record<string,unknown>;color:string;material:string;created:string;updated:string
  version:number;review_status:string;availability:'available'|'missing';thumbnail_url:string;representative_image_url:string
  representative_frame_id:string;source_cluster:string;source_cluster_name:string;source_frames:string[];frame_count:number
  bounding_boxes:{x:number;y:number;width:number;height:number}[];detection_confidence:number|null;average_confidence:number|null
  usage_count:number;dependencies:{kind:string;id:string;name:string}[]
}
type Manifest={version:string;objects:ManifestObject[];categories:Category[]}
type Draft={name:string;category:string;description:string;aliases:string;tags:string;material:string;color:string;type:string}
type DeleteRequest={ids:string[];dependencies:{kind:string;id:string;name:string}[]}
type Props={createAction:(objectId:string)=>void;notify:(message:string)=>void}

const preferenceKey='taskgraph.object-library.preferences.v1'
const readPreferences=()=>{try{return JSON.parse(localStorage.getItem(preferenceKey)||'{}')}catch{return{}}}
const request=async<T,>(path:string,method='GET',body?:unknown):Promise<T>=>{
  const response=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,cache:'no-store'})
  const payload=await response.json().catch(()=>({detail:response.statusText}))
  if(!response.ok){const detail=payload.detail;const message=typeof detail==='string'?detail:detail?.message||payload.message||response.statusText;throw Object.assign(new Error(message),{status:response.status,payload:detail||payload})}
  return payload
}
const percent=(value:number|null)=>value==null?'Unknown':`${(value*100).toFixed(1)}%`
const text=(value:unknown)=>value===null||value===undefined||value===''?'Unknown':String(value)

function ObjectImage({object,className=''}:{object:ManifestObject;className?:string}){
  const [failed,setFailed]=useState(false)
  useEffect(()=>setFailed(false),[object.thumbnail_url])
  if(!object.thumbnail_url||failed)return <div className={`object-image-missing ${className}`}><ImageOff/><span>Thumbnail unavailable</span></div>
  return <img className={className} loading="lazy" src={object.thumbnail_url} alt={`${object.name||'Object'} thumbnail`} onError={()=>setFailed(true)}/>
}

export function ObjectLibrary({createAction,notify}:Props){
  const queryClient=useQueryClient(),preferences=useMemo(readPreferences,[])
  const manifest=useQuery({queryKey:['object-manifest'],queryFn:()=>request<Manifest>('/object-library/manifest'),staleTime:5_000,refetchOnMount:'always'})
  const [selected,setSelected]=useState<Set<string>>(()=>new Set(preferences.selectedIds||[]))
  const [primaryId,setPrimaryId]=useState<string>(preferences.primaryId||'')
  const [query,setQuery]=useState(preferences.query||''),[category,setCategory]=useState(preferences.category||'')
  const [status,setStatus]=useState(preferences.status||'all'),[sort,setSort]=useState(preferences.sort||'alphabetical')
  const [view,setView]=useState<'grid'|'list'>(preferences.view==='list'?'list':'grid'),[limit,setLimit]=useState(80)
  const [draft,setDraft]=useState<Draft>(),[saving,setSaving]=useState(false),[busy,setBusy]=useState('')
  const [deleteRequest,setDeleteRequest]=useState<DeleteRequest>(),[replacement,setReplacement]=useState('')
  const [preview,setPreview]=useState(false),[zoom,setZoom]=useState(1),[actionError,setActionError]=useState('')
  const objects=useMemo(()=>manifest.data?.objects||[],[manifest.data?.objects])
  const categories=useMemo(()=>manifest.data?.categories||[],[manifest.data?.categories])
  const primary=objects.find(item=>item.object_id===primaryId)||objects.find(item=>selected.has(item.object_id))

  useEffect(()=>{
    if(!manifest.data)return
    const valid=new Set(objects.map(item=>item.object_id))
    setSelected(current=>new Set([...current].filter(id=>valid.has(id))))
    if(primaryId&&!valid.has(primaryId))setPrimaryId('')
  },[manifest.data,objects,primaryId])
  useEffect(()=>{
    let socket:WebSocket|undefined,reconnect:number|undefined,stopped=false
    const connect=()=>{
      const protocol=location.protocol==='https:'?'wss':'ws'
      socket=new WebSocket(`${protocol}://${location.host}/ws/objects`)
      socket.onmessage=()=>void queryClient.invalidateQueries({queryKey:['object-manifest']})
      socket.onclose=()=>{if(!stopped)reconnect=window.setTimeout(connect,1_500)}
    }
    connect()
    return()=>{stopped=true;if(reconnect)window.clearTimeout(reconnect);socket?.close()}
  },[queryClient])
  useEffect(()=>{
    localStorage.setItem(preferenceKey,JSON.stringify({selectedIds:[...selected],primaryId,query,category,status,sort,view}))
  },[selected,primaryId,query,category,status,sort,view])
  useEffect(()=>{
    if(!primary){setDraft(undefined);return}
    setDraft({name:primary.name,category:primary.category,description:primary.description,aliases:primary.aliases.join(', '),tags:primary.tags.join(', '),material:primary.material,color:primary.color,type:primary.type})
    setZoom(1)
  },[primary])

  const filtered=useMemo(()=>{
    const needle=query.trim().toLocaleLowerCase()
    const values=objects.filter(item=>{
      const matchesCategory=!category||item.category===category
      const matchesStatus=status==='all'||item.availability===status||item.review_status===status
      const haystack=[item.name,item.category,item.type,item.description,item.material,...item.tags,...item.aliases,item.source_cluster_name,item.object_id].join(' ').toLocaleLowerCase()
      return matchesCategory&&matchesStatus&&(!needle||haystack.includes(needle))
    })
    values.sort((a,b)=>sort==='recently-added'?b.created.localeCompare(a.created):sort==='recently-modified'?b.updated.localeCompare(a.updated):a.name.localeCompare(b.name,undefined,{sensitivity:'base'}))
    return values
  },[objects,query,category,status,sort])
  const visible=filtered.slice(0,limit)
  const updateManifest=(payload:{manifest:Manifest})=>{queryClient.setQueryData(['object-manifest'],payload.manifest);void queryClient.invalidateQueries({queryKey:['objects']})}
  const selectObject=(id:string,multi:boolean)=>{
    setPrimaryId(id)
    setSelected(current=>{
      if(!multi)return new Set([id])
      const next=new Set(current);if(next.has(id))next.delete(id);else next.add(id);return next
    })
  }
  const save=async()=>{
    if(!primary||!draft||saving)return
    if(!draft.name.trim()){setActionError('Object name is required.');return}
    setSaving(true);setActionError('')
    try{
      const payload=await request<{manifest:Manifest}>('/objects/edit','PATCH',{object_id:primary.object_id,...draft,aliases:draft.aliases,tags:draft.tags})
      updateManifest(payload);notify(`${draft.name.trim()} saved`)
    }catch(reason){setActionError(reason instanceof Error?reason.message:'Object could not be saved.')}
    finally{setSaving(false)}
  }
  const duplicate=async()=>{
    if(selected.size!==1)return
    const id=[...selected][0];setBusy('duplicate');setActionError('')
    try{const payload=await request<{object:ManifestObject;manifest:Manifest}>(`/object-library/objects/${encodeURIComponent(id)}/duplicate`,'POST');updateManifest(payload);setSelected(new Set([payload.object.object_id]));setPrimaryId(payload.object.object_id);notify(`${payload.object.name} created`)}
    catch(reason){setActionError(reason instanceof Error?reason.message:'Object could not be duplicated.')}
    finally{setBusy('')}
  }
  const askDelete=()=>{
    const targets=objects.filter(item=>selected.has(item.object_id))
    setDeleteRequest({ids:targets.map(item=>item.object_id),dependencies:targets.flatMap(item=>item.dependencies)})
    setReplacement('')
  }
  const remove=async(force=false)=>{
    if(!deleteRequest)return
    setBusy('delete');setActionError('')
    try{
      let payload:{manifest:Manifest}
      if(deleteRequest.ids.length===1){
        const suffix=replacement?`?replacement_id=${encodeURIComponent(replacement)}`:force?'?force=true':''
        payload=await request(`/objects/${encodeURIComponent(deleteRequest.ids[0])}${suffix}`,'DELETE')
      }else payload=await request('/object-library/objects/bulk-delete','POST',{object_ids:deleteRequest.ids,force})
      updateManifest(payload);setSelected(new Set());setPrimaryId('');setDeleteRequest(undefined);notify(`${deleteRequest.ids.length} object${deleteRequest.ids.length===1?'':'s'} deleted`)
    }catch(reason:any){
      if(reason?.status===409){
        const blocked=reason.payload?.blocked||[reason.payload]
        setDeleteRequest(current=>current&&({...current,dependencies:blocked.flatMap((item:any)=>item.references||[])}))
      }else setActionError(reason instanceof Error?reason.message:'Objects could not be deleted.')
    }finally{setBusy('')}
  }
  const createCategory=async()=>{
    const name=window.prompt('New category name')?.trim();if(!name)return
    try{const payload=await request<{manifest:Manifest}>('/object-library/categories','POST',{name});updateManifest(payload);setCategory(name);notify(`${name} category created`)}
    catch(reason){setActionError(reason instanceof Error?reason.message:'Category could not be created.')}
  }
  const renameCategory=async()=>{
    const item=categories.find(value=>value.name===category);if(!item)return
    const name=window.prompt('Rename category',item.name)?.trim();if(!name||name===item.name)return
    try{const payload=await request<{manifest:Manifest}>(`/object-library/categories/${encodeURIComponent(item.category_id)}`,'PATCH',{name});updateManifest(payload);setCategory(name);notify(`Category renamed to ${name}`)}
    catch(reason){setActionError(reason instanceof Error?reason.message:'Category could not be renamed.')}
  }
  const deleteCategory=async()=>{
    const item=categories.find(value=>value.name===category);if(!item)return
    const members=objects.filter(value=>value.category===item.name)
    let replacementCategory=''
    if(members.length){
      replacementCategory=window.prompt(`Move ${members.length} object(s) to which existing category?`,categories.find(value=>value.name!==item.name)?.name||'')?.trim()||''
      if(!replacementCategory)return
    }
    if(!window.confirm(`Delete category ${item.name}?`))return
    try{const payload=await request<{manifest:Manifest}>(`/object-library/categories/${encodeURIComponent(item.category_id)}?replacement=${encodeURIComponent(replacementCategory)}`,'DELETE');updateManifest(payload);setCategory('');notify(`${item.name} category deleted`)}
    catch(reason){setActionError(reason instanceof Error?reason.message:'Category could not be deleted.')}
  }

  if(manifest.isLoading)return <div className="object-library-state"><span/><h2>Loading Object Library</h2><p>Reading the authoritative object manifest…</p></div>
  if(manifest.isError)return <div className="object-library-state error"><AlertTriangle/><h2>Object Library unavailable</h2><p>{manifest.error instanceof Error?manifest.error.message:'The backend could not be reached.'}</p><button onClick={()=>void manifest.refetch()}><RefreshCw/> Retry</button></div>

  return <div className="object-library-page">
    <div className="object-library-title"><div><small>ASSET WORKSPACE</small><h1>Object Library</h1><p>Permanent semantic assets backed by the authoritative Object Manifest.</p></div><div><button onClick={createCategory}><Plus/> Category</button><button disabled={!selected.size} onClick={askDelete}><Trash2/> Delete</button></div></div>
    {actionError&&<div className="object-library-error"><AlertTriangle/>{actionError}<button onClick={()=>setActionError('')}><X/></button></div>}
    <div className="object-library-toolbar">
      <label><Search/><input aria-label="Search objects" value={query} onChange={event=>{setQuery(event.target.value);setLimit(80)}} placeholder="Search objects, aliases, tags, IDs…"/></label>
      <label><Filter/><select aria-label="Availability filter" value={status} onChange={event=>setStatus(event.target.value)}><option value="all">All statuses</option><option value="available">Available</option><option value="missing">Missing assets</option><option value="accepted">Accepted</option></select></label>
      <select aria-label="Object sorting" value={sort} onChange={event=>setSort(event.target.value)}><option value="alphabetical">Alphabetical</option><option value="recently-added">Recently added</option><option value="recently-modified">Recently modified</option></select>
      <button className={view==='grid'?'active':''} onClick={()=>setView('grid')} title="Grid view"><LayoutGrid/></button><button className={view==='list'?'active':''} onClick={()=>setView('list')} title="List view"><List/></button>
      <span>{filtered.length} of {objects.length}</span>
    </div>
    <div className="object-library-layout">
      <aside className="object-categories"><header><b>Categories</b><button onClick={createCategory} title="Create category"><Plus/></button></header><button className={!category?'active':''} onClick={()=>setCategory('')}><span><LayoutGrid/>All Objects</span><em>{objects.length}</em></button>{categories.map(item=><button key={item.category_id} className={category===item.name?'active':''} onClick={()=>setCategory(item.name)}><span><Box/>{item.name}</span><em>{objects.filter(object=>object.category===item.name).length}</em></button>)}{category&&<footer><button onClick={renameCategory}><Pencil/> Rename</button><button onClick={deleteCategory}><Trash2/> Delete</button></footer>}</aside>
      <main className="object-collection">
        <header><div><button onClick={()=>setSelected(new Set(filtered.map(item=>item.object_id)))}><Check/> Select All</button><button disabled={!selected.size} onClick={()=>setSelected(new Set())}><Square/> Deselect</button><button disabled={selected.size!==1||busy==='duplicate'} onClick={()=>void duplicate()}><Copy/> Duplicate</button></div><span>{selected.size} selected</span></header>
        {!objects.length?<div className="object-empty"><Boxes/><h2>No Objects Available</h2><p>Accepted Frame Workspace clusters will appear here as permanent semantic assets.</p></div>:!filtered.length?<div className="object-empty"><Search/><h2>No matching objects</h2><p>Adjust search, category, or status filters.</p></div>:<div className={`object-cards ${view}`}>{visible.map(object=><article key={object.object_id} className={`${selected.has(object.object_id)?'selected':''} ${object.availability}`}>
          <button className="object-card-select" aria-label={`${selected.has(object.object_id)?'Deselect':'Select'} ${object.name}`} aria-pressed={selected.has(object.object_id)} onClick={event=>selectObject(object.object_id,event.ctrlKey||event.metaKey)}><i>{selected.has(object.object_id)&&<Check/>}</i></button>
          <button className="object-card-body" onClick={event=>selectObject(object.object_id,event.ctrlKey||event.metaKey)}><div><ObjectImage object={object}/><span className={object.availability}>{object.availability}</span></div><section><b>{object.name||'Unknown'}</b><small>{object.category||'Unknown'}</small><em>{object.usage_count} dependencies</em></section></button>
        </article>)}</div>}
        {visible.length<filtered.length&&<button className="object-load-more" onClick={()=>setLimit(value=>value+80)}>Load more objects</button>}
      </main>
      <aside className="object-inspector">
        <header><b>Inspector</b>{primary&&<button onClick={()=>setPreview(true)} title="Full preview"><Maximize2/></button>}</header>
        {!primary||!draft?<div className="object-inspector-empty"><Boxes/><p>Select an object to inspect it.</p></div>:<>
          <div className="object-preview"><div><button onClick={()=>setZoom(value=>Math.min(3,value+.25))}><Plus/></button><button onClick={()=>setZoom(value=>Math.max(.5,value-.25))}><Minus/></button><button onClick={()=>setZoom(1)}><RotateCcw/></button></div><span style={{transform:`scale(${zoom})`}}><ObjectImage object={primary}/></span></div>
          <div className="object-inspector-scroll"><h2>{primary.name||'Unknown'}</h2><p>{primary.object_id}</p>
            <details open><summary>General <ChevronDown/></summary><label>Name<input value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label>Category<select value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value})}><option value="">Unknown</option>{categories.map(item=><option key={item.category_id}>{item.name}</option>)}</select></label><label>Type<input value={draft.type} onChange={event=>setDraft({...draft,type:event.target.value})}/></label><label>Description<textarea value={draft.description} onChange={event=>setDraft({...draft,description:event.target.value})}/></label></details>
            <details open><summary>Properties <ChevronDown/></summary><label>Aliases<input value={draft.aliases} onChange={event=>setDraft({...draft,aliases:event.target.value})}/></label><label>Tags<input value={draft.tags} onChange={event=>setDraft({...draft,tags:event.target.value})}/></label><label>Material<input value={draft.material} onChange={event=>setDraft({...draft,material:event.target.value})}/></label><label>Color<span className="object-color">{/^#[0-9a-f]{6}$/i.test(draft.color)&&<input aria-label="Color picker" type="color" value={draft.color} onChange={event=>setDraft({...draft,color:event.target.value})}/>}<input value={draft.color} placeholder="Unknown" onChange={event=>setDraft({...draft,color:event.target.value})}/></span></label></details>
            <details><summary>Source & Detection <ChevronDown/></summary><dl><dt>Source cluster</dt><dd>{text(primary.source_cluster_name||primary.source_cluster)}</dd><dt>Source frames</dt><dd>{primary.frame_count}</dd><dt>Representative frame</dt><dd>{text(primary.representative_frame_id)}</dd><dt>Detection confidence</dt><dd>{percent(primary.detection_confidence)}</dd><dt>Average confidence</dt><dd>{percent(primary.average_confidence)}</dd><dt>Bounding boxes</dt><dd>{primary.bounding_boxes.length}</dd><dt>Review status</dt><dd>{text(primary.review_status)}</dd></dl></details>
            <details><summary>Manifest <ChevronDown/></summary><dl><dt>Availability</dt><dd>{primary.availability}</dd><dt>Version</dt><dd>{primary.version}</dd><dt>Created</dt><dd>{text(primary.created)}</dd><dt>Updated</dt><dd>{text(primary.updated)}</dd><dt>Dependencies</dt><dd>{primary.usage_count}</dd></dl></details>
            <footer><button onClick={()=>{setDraft({name:primary.name,category:primary.category,description:primary.description,aliases:primary.aliases.join(', '),tags:primary.tags.join(', '),material:primary.material,color:primary.color,type:primary.type});setActionError('')}}>Cancel</button><button className="primary" disabled={saving||!draft.name.trim()} onClick={()=>void save()}>{saving?'Saving…':'Save Changes'}</button><button onClick={()=>createAction(primary.object_id)}><Plus/> Create Action</button></footer>
          </div>
        </>}
      </aside>
    </div>
    <div className="object-library-status"><span>Objects <b>{objects.length}</b></span><span>Categories <b>{categories.length}</b></span><span>Visible <b>{filtered.length}</b></span><span>Selected <b>{selected.size}</b></span><span>Manifest <b>{manifest.data?.version}</b></span></div>
    {preview&&primary&&<div className="object-modal" onMouseDown={()=>setPreview(false)}><div className="object-full-preview" onMouseDown={event=>event.stopPropagation()}><header><b>{primary.name||'Unknown'}</b><button onClick={()=>setPreview(false)}><X/></button></header><ObjectImage object={primary}/></div></div>}
    {deleteRequest&&<div className="object-modal" onMouseDown={()=>setDeleteRequest(undefined)}><div className="object-delete-dialog" onMouseDown={event=>event.stopPropagation()}><AlertTriangle/><h2>Delete {deleteRequest.ids.length} object{deleteRequest.ids.length===1?'':'s'}?</h2>{deleteRequest.dependencies.length?<><p>These objects are referenced by downstream assets. Replace references or explicitly force deletion.</p><ul>{deleteRequest.dependencies.map((item,index)=><li key={`${item.kind}-${item.id}-${index}`}>{item.kind}: {item.name}</li>)}</ul>{deleteRequest.ids.length===1&&<label>Replace references with<select value={replacement} onChange={event=>setReplacement(event.target.value)}><option value="">Choose an object</option>{objects.filter(item=>!deleteRequest.ids.includes(item.object_id)).map(item=><option key={item.object_id} value={item.object_id}>{item.name}</option>)}</select></label>}</>:<p>This removes the permanent object record and its independent image dataset.</p>}<footer><button onClick={()=>setDeleteRequest(undefined)}>Cancel</button>{replacement&&<button onClick={()=>void remove(false)}><FolderInput/> Replace & Delete</button>}<button className="danger" disabled={busy==='delete'} onClick={()=>void remove(Boolean(deleteRequest.dependencies.length))}>{deleteRequest.dependencies.length?'Force Delete':'Delete'}</button></footer></div></div>}
  </div>
}
