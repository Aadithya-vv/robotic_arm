var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
var backend = 'http://127.0.0.1:8000';
var routes = ['/runtime', '/frame-workspace', '/object-library', '/objects', '/actions', '/action-assets', '/action-builder', '/taskir', '/execution', '/semantic', '/knowledge', '/affordances', '/clusters', '/scene', '/health', '/reports', '/validation', '/detections', '/detection', '/frames', '/video'];
var proxy = routes.reduce(function (value, route) {
    var _a;
    return (__assign(__assign({}, value), (_a = {}, _a[route] = backend, _a)));
}, {});
export default defineConfig({
    plugins: [react()],
    build: { rollupOptions: { output: { manualChunks: { react: ['react', 'react-dom', 'react-router-dom'], charts: ['recharts'], graph: ['@xyflow/react'], motion: ['framer-motion'] } } } },
    server: { proxy: __assign(__assign({}, proxy), { '/ws': { target: 'ws://127.0.0.1:8000', ws: true } }) },
});
