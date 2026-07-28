import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    build: { rollupOptions: { output: { manualChunks: { react: ['react', 'react-dom', 'react-router-dom'], charts: ['recharts'], graph: ['@xyflow/react'], motion: ['framer-motion'] } } } },
    server: { proxy: { '/runtime': 'http://127.0.0.1:8000', '/objects': 'http://127.0.0.1:8000', '/actions': 'http://127.0.0.1:8000', '/action-assets': 'http://127.0.0.1:8000', '/action-builder': 'http://127.0.0.1:8000', '/taskir': 'http://127.0.0.1:8000', '/semantic': 'http://127.0.0.1:8000', '/knowledge': 'http://127.0.0.1:8000', '/affordances': 'http://127.0.0.1:8000', '/clusters': 'http://127.0.0.1:8000', '/scene': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000', '/reports': 'http://127.0.0.1:8000', '/validation': 'http://127.0.0.1:8000', '/detections': 'http://127.0.0.1:8000', '/detection': 'http://127.0.0.1:8000', '/frames': 'http://127.0.0.1:8000', '/video': 'http://127.0.0.1:8000', '/ws': { target: 'ws://127.0.0.1:8000', ws: true } } }
});
