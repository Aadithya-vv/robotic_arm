import {useMemo} from 'react'
import {useQuery} from '@tanstack/react-query'
import {api,type Runtime,useSocket} from './lib'
import {Studio,type StudioObject} from './studio'

export default function App(){
  const objects=useQuery({queryKey:['objects'],queryFn:()=>api<any>('/objects')})
  const runtime=useQuery({queryKey:['runtime'],queryFn:()=>api<Runtime>('/runtime'),refetchInterval:300})
  useSocket('/ws/runtime','runtime');useSocket('/ws/objects','objects')
  const mapped=useMemo<StudioObject[]>(()=>((objects.data?.objects||[]) as any[]).filter(x=>typeof x.object_id==='string'&&x.object_id).map(x=>({id:x.object_id,name:String(x.name||''),category:String(x.category||''),description:String(x.description||''),color:String(x.color||''),uses:0,image:x.thumbnail?.path?`/objects/${encodeURIComponent(x.object_id)}/thumbnail`:undefined,aliases:Array.isArray(x.aliases)?x.aliases:[],material:String(x.material||''),properties:x.properties&&typeof x.properties==='object'?x.properties:{},tags:Array.isArray(x.tags)?x.tags:[],metadata:x.metadata&&typeof x.metadata==='object'?x.metadata:{}})),[objects.data])
  return <Studio initialObjects={mapped} runtime={runtime.data}/>
}
