import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'

const backend='http://127.0.0.1:8000'
const routes=['/runtime','/frame-workspace','/object-library','/objects','/actions','/action-assets','/action-builder','/taskir','/execution','/semantic','/knowledge','/affordances','/clusters','/scene','/health','/reports','/validation','/detections','/detection','/frames','/video']
const proxy=routes.reduce<Record<string,string>>((value,route)=>({...value,[route]:backend}),{})

export default defineConfig({
  plugins:[react()],
  build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom','react-router-dom'],charts:['recharts'],graph:['@xyflow/react'],motion:['framer-motion']}}}},
  server:{proxy:{...proxy,'/ws':{target:'ws://127.0.0.1:8000',ws:true}}},
})
