# Tianshu 插件使用说明

## 插件已完成！

基于官方 MinerU 插件修改完成，使用正确的 Dify 插件规范：

### ✅ 修复的关键问题

1. **凭据配置格式**
   - 使用 `credentials_for_provider` 而不是 `credentials_schema`
   - 正确的配置结构会自动显示 "API Key 授权配置" 按钮

2. **凭据访问方式**
   - 在 Tool 中通过 `self.runtime.credentials` 直接访问
   - 不再通过 `self.runtime.tool_provider` 访问

3. **验证方法**
   - Provider 调用 Tool 的 `from_credentials` 方法创建实例
   - Tool 实现 `validate_credentials` 方法进行验证

## 文件结构

```
tianshu/
├── manifest.yaml               # 插件清单
├── requirements.txt            # Python 依赖
├── README.md                   # 英文文档
├── provider/
│   ├── tianshu.yaml           # Provider 配置（包含凭据配置）
│   └── tianshu.py             # Provider 实现
└── tools/
    ├── parse_document.yaml    # 解析文档工具配置
    ├── parse_document.py      # 解析文档工具实现
    ├── get_task_status.yaml   # 查询状态工具配置
    └── get_task_status.py     # 查询状态工具实现
```

## 配置说明

### 1. 凭据配置 (provider/tianshu.yaml)

```yaml
credentials_for_provider:
  api_base_url:
    label:
      en_US: API Base URL
      zh_Hans: API 服务器地址
    placeholder:
      en_US: Please input your Tianshu server's Base URL
      zh_Hans: 请输入你的 Tianshu 服务的 Base URL
    required: true
    type: text-input

  api_key:
    label:
      en_US: API Key
      zh_Hans: API 密钥
    placeholder:
      en_US: Please input your Tianshu server's API Key
      zh_Hans: 请输入你的 Tianshu 服务的 API 密钥
    required: true
    type: secret-input
```

### 2. 工具说明

#### parse-document (解析文档)

提交文档解析任务，返回 task_id。

**参数：**
- `file` (必填): 要解析的文件
- `backend` (可选): 处理后端，默认 auto
- `lang` (可选): 文档语言，默认 auto
- `formula_enable` (可选): 启用公式识别，默认 true
- `priority` (可选): 任务优先级，默认 0

**返回：**
```json
{
  "task_id": "abc123",
  "message": "任务已提交，请使用 get_task_status 工具查询结果",
  "file_name": "document.pdf",
  "status": "pending"
}
```

#### get-task-status (查询任务状态)

查询文档解析任务的状态和结果。

**参数：**
- `task_id` (必填): 从 parse-document 返回的任务 ID
- `format` (可选): 输出格式 (markdown/json/both)，默认 markdown
- `upload_images` (可选): 上传图片到 MinIO，默认 false

**返回：**
- 任务完成时返回解析内容
- 任务处理中返回当前状态
- 任务失败返回错误信息

## 使用步骤

### 1. 安装依赖

```bash
cd tianshu
pip install -r requirements.txt
```

### 2. 启动插件

```bash
python -m main
```

### 3. 在 Dify 中配置

1. 进入 Dify 插件管理页面
2. 找到 "Tianshu" 插件
3. 点击配置/授权按钮
4. 输入：
   - API Base URL: `http://localhost:8000` (或您的实际地址)
   - API Key: 您的 API 密钥

### 4. 使用工具

在 Dify 工作流中：

1. 添加 "parse-document" 节点
   - 选择要解析的文件
   - 设置参数（可选）
   - 执行后获得 task_id

2. 添加 "get-task-status" 节点
   - 输入上一步的 task_id
   - 选择输出格式
   - 查询解析结果

3. 循环查询（可选）
   - 如果状态是 processing，等待后重新查询
   - 如果状态是 completed，使用解析内容
   - 如果状态是 failed，查看错误信息

## 工作流示例

### 简单工作流

```
[文件输入] → [parse-document] → [等待5秒] → [get-task-status] → [使用结果]
```

### 带重试的工作流

```
[文件输入] → [parse-document]
               ↓
        [get-task-status]
               ↓
        [判断状态]
          ├─ completed → [使用结果]
          ├─ processing → [等待] → [返回查询]
          └─ failed → [错误处理]
```

## API 端点说明

插件调用的 Tianshu API 端点：

1. **健康检查**: `GET /api/v1/health`
2. **提交任务**: `POST /api/v1/tasks/submit`
3. **查询任务**: `GET /api/v1/tasks/{task_id}`
4. **验证凭据**: `GET /api/v1/queue/tasks`

## 常见问题

### Q: 看不到 API Key 配置按钮？

A:
1. 确保使用的是 `credentials_for_provider` 格式
2. 重启插件服务
3. 刷新 Dify 页面（Ctrl+F5）

### Q: 提示 "ToolRuntime object has no attribute tool_provider"？

A: 这个错误已修复。现在使用 `self.runtime.credentials` 直接访问凭据。

### Q: 如何获取 task_id？

A: task_id 在 parse-document 工具的返回结果中，作为 JSON 对象的 task_id 字段。

### Q: 任务一直处于 processing 状态？

A: 正常现象。复杂文档可能需要几分钟处理。建议在工作流中添加循环查询逻辑。

## 调试

启用日志查看详细信息：

```python
import logging
logging.basicConfig(level=logging.INFO)
```

查看：
- 凭据验证过程
- API 请求详情
- 任务提交和查询

## 更新日志

**v0.0.1** (2025-01-27)
- 基于官方 MinerU 插件修改
- 实现 Tianshu API 集成
- 支持文档解析和状态查询
- API Key 认证
- 异步任务处理

## 支持

- GitHub: https://github.com/magicyuan876/mineru-tianshu
- Issues: 请在 GitHub 提交问题
