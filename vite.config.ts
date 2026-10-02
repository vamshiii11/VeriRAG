import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  server:{host:"::",port:5173,proxy:{"/api":{target:"http://127.0.0.1:8000",changeOrigin:true,ws:true}}},
  build:{outDir:"dist/spa"},
  plugins:[react()],
  resolve:{alias:{"@":path.resolve(__dirname,"./client"),"@shared":path.resolve(__dirname,"./shared")}},
});
