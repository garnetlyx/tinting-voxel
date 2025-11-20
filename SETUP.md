# ImageToSTLConverter - 启动指南

## 项目概览

这是一个图像转STL色块转换器，支持将图像转换为分层的3D打印STL文件。

**技术栈**：
- 前端：React 19 + TypeScript + Vite + Tailwind CSS
- 后端：Python 3 + FastAPI + numpy-stl + PIL + scikit-learn

## 前后端架构

### 前端职责
- 用户交互界面
- 参数调整（maxColors, colorThreshold, layerHeight, pixelSize）
- 图像上传
- 实时预览
- 显示色块结果
- 下载STL ZIP和CSV文件

### 后端职责
- 图像处理和色彩提取
- 色彩聚类（scikit-learn）
- 映射到CMYK原色（map_to_nearest_color）
- 使用Beer-Lambert光学模型计算混色
- 生成分层STL文件
- 返回处理后的预览图

## 快速启动

### 方式1：手动启动（推荐）

#### 1. 启动后端

```bash
# 进入项目根目录
cd ImageToSTLConverter

# 进入后端目录
cd backend

# 激活虚拟环境
source .venv/bin/activate

# 启动后端服务器
uvicorn main:app --reload --port 8000
```

后端将在 http://localhost:8000 启动

#### 2. 启动前端（新终端）

```bash
# 进入项目根目录
cd ImageToSTLConverter

# 启动前端开发服务器
npm run dev
```

前端将在 http://localhost:5173 启动

### 方式2：npm脚本

```bash
# 只启动前端
npm run dev

# 只启动后端
npm run dev:backend
```

**注意**：你需要在两个终端窗口中分别运行前后端服务。

## API端点

### 1. POST /api/process-image
处理上传的图像，提取色块

**请求**：
- `image`: File（图像文件）
- `maxColors`: int（最大色块数量，默认10）
- `colorThreshold`: float（色彩合并阈值，默认50）
- `pixelSize`: float（像素尺寸mm，默认0.08）

**响应**：
```json
{
  "colorBlocks": [
    {
      "r": 128, "g": 64, "b": 200,
      "count": 1234,
      "pixels": [{"x": 10, "y": 20}, ...],
      "hex": "#8040c8"
    }
  ],
  "processedImage": "data:image/png;base64,...",
  "imageDimensions": {"width": 208, "height": 208}
}
```

### 2. POST /api/download-csv
下载颜色数据CSV

**请求**：
```json
{
  "colorBlocks": [...]
}
```

**响应**：CSV文件

### 3. POST /api/download-stl
生成并下载按原色合并的STL文件

**请求**：
```json
{
  "colorBlocks": [...],
  "layerHeight": 0.08,
  "pixelSize": 0.08,
  "layerCount": 4,
  "imageDimensions": {"width": 208, "height": 208}
}
```

**响应**：ZIP文件（包含 CMYW_208x208x3.36_C.stl 等）

## 文件结构

```
ImageToSTLConverter/
├── backend/
│   ├── main.py                  # FastAPI应用入口
│   ├── blend_color.py           # 核心色彩算法
│   ├── api/
│   │   ├── models.py           # Pydantic数据模型
│   │   └── __init__.py
│   ├── services/
│   │   ├── image_processor.py  # 图像处理服务
│   │   ├── stl_generator.py    # STL生成服务
│   │   ├── csv_generator.py    # CSV导出服务
│   │   └── __init__.py
│   └── requirements.txt
├── src/
│   ├── main.tsx                # React入口
│   ├── image_to_stl_converter.tsx  # 主组件
│   ├── api/
│   │   ├── client.ts           # API客户端
│   │   └── types.ts            # TypeScript类型
│   └── index.css
├── vite.config.ts              # Vite配置（包含API代理）
├── package.json
└── index.html
```

## 依赖检查

### 后端依赖

```bash
cd backend
source .venv/bin/activate
pip list | grep -E "fastapi|uvicorn|pillow|scikit"
```

应该看到：
- fastapi==0.121.2
- uvicorn==0.38.0
- pillow==12.0.0
- scikit-image==0.25.2
- scikit-learn==1.7.2

### 前端依赖

```bash
npm list --depth=0
```

应该看到：
- react@19.2.0
- vite@5.4.21
- typescript@5.9.3
- lucide-react@0.553.0

## 常见问题

### 1. 后端启动失败

**错误**：`ModuleNotFoundError: No module named 'fastapi'`

**解决**：
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 前端无法连接后端

**错误**：API请求失败

**检查**：
1. 后端是否在运行：`curl http://localhost:8000/`
2. Vite代理配置是否正确（见vite.config.ts）

### 3. CORS错误

确保后端main.py中的CORS配置包含前端地址：
```python
allow_origins=["http://localhost:5173", "http://localhost:3000"]
```

## 开发说明

### 前端开发
- Vite自动代理 `/api/*` 请求到 `http://localhost:8000`
- 修改代码后自动热更新
- TypeScript严格模式已启用

### 后端开发
- uvicorn `--reload` 模式自动重启
- 日志输出到控制台
- API文档：http://localhost:8000/docs

## 生产部署（TODO）

- [ ] Docker容器化
- [ ] 云服务器部署
- [ ] 环境变量配置
- [ ] 生产环境优化
- [ ] 用户手动选择色块颜色映射
- [ ] 异步任务处理（大图像优化）
- [ ] 缓存机制（性能优化）

## 许可证

ISC
