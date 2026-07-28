import {useEffect} from 'react'
import {useQueryClient} from '@tanstack/react-query'
export type Runtime={detector:Record<string,any>;accelerator:Record<string,any>;metrics:Record<string,number>;workers:Record<string,any>;workspace:Record<string,any>;timeline:any[];status:string}
export type AppData={runtime?:Runtime;health?:any;objects?:any;semantic?:any;knowledge?:any;affordances?:any;plans?:any;taskir?:any;explanations?:any;clusters?:any;scene?:any;detections?:any;validation?:any;reports?:any}
export const api=async<T,>(path:string):Promise<T>=>{const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw Error(r.statusText);return r.json()}
export async function mutate<T=any>(path:string,method:string,body?:any):Promise<T>{const r=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,cache:'no-store'});if(!r.ok)throw Error((await r.text())||r.statusText);return r.json()}
export const fmt=(v:any,d=1)=>Number(v||0).toFixed(d)
export function useSocket(path:string,key:string){const qc=useQueryClient();useEffect(()=>{let ws:WebSocket|undefined,timer:number|undefined,closed=false;const connect=()=>{const proto=location.protocol==='https:'?'wss':'ws';ws=new WebSocket(`${proto}://${location.host}${path}`);ws.onmessage=e=>qc.setQueryData([key],JSON.parse(e.data));ws.onclose=()=>{if(!closed)timer=window.setTimeout(connect,1000)};ws.onerror=()=>ws?.close()};connect();return()=>{closed=true;if(timer)clearTimeout(timer);ws?.close()}},[path,key,qc])}
export const frameCount=(d:AppData)=>Number(d.runtime?.workspace.frames||0)
export const teachable=(x:any)=>!['person','hand','arm','face','body'].includes(String(x.class_name).toLowerCase())
