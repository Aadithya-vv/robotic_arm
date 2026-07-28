import {useMemo,useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {api,type Runtime,useSocket} from './lib'
import {Studio,type StudioObject} from './studio'

export default function App(){
  const objects=useQuery({queryKey:['objects'],queryFn:()=>api<any>('/objects')})
  const runtime=useQuery({queryKey:['runtime'],queryFn:()=>api<Runtime>('/runtime'),refetchInterval:300})
  useSocket('/ws/runtime','runtime');useSocket('/ws/objects','objects')
  const mapped=useMemo<StudioObject[]>(()=>((objects.data?.objects||[]) as any[]).map((x,i)=>({id:x.object_id||String(i),name:x.name||'Untitled object',category:x.category||'Custom',description:x.description||'Learned robotic knowledge object.',color:x.color||['#e9b765','#71a8df','#d57b65','#8daf79'][i%4],uses:Number(x.frames_seen||0)%5+1,image:x.thumbnail?.path?`/objects/${encodeURIComponent(x.object_id)}/thumbnail`:undefined,aliases:x.aliases||[],material:x.material||'',properties:x.properties||{},tags:x.tags||[],metadata:x.metadata||{}})),[objects.data])
  const [seed]=useState<StudioObject[]>([
    {id:'bottle',name:'Glass Bottle',category:'Containers',description:'Clear 750 ml bottle used as a source container.',color:'#d29b55',uses:3},
    {id:'cup',name:'Ceramic Cup',category:'Kitchen',description:'White ceramic destination vessel.',color:'#87a9c5',uses:5},
    {id:'tray',name:'Serving Tray',category:'Kitchen',description:'Rigid support surface for transport tasks.',color:'#a77751',uses:2},
    {id:'gripper',name:'Soft Gripper',category:'Tools',description:'Compliant end-effector attachment.',color:'#78869a',uses:4},
    {id:'box',name:'Storage Bin',category:'Containers',description:'Stackable blue storage container.',color:'#507cae',uses:1},
  ])
  return <Studio initialObjects={mapped.length?mapped:seed} runtime={runtime.data}/>
}
