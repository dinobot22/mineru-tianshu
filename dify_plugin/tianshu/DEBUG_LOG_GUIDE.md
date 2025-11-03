# Tianshu 插件调试日志指南

## 日志系统说明

插件现在包含完整的调试日志，帮助你排查问题。所有日志都会输出到控制台（标准输出）。

## 日志级别

- **INFO**: 正常流程信息（蓝色分隔线）
- **DEBUG**: 详细调试信息（响应内容等）
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **EXCEPTION**: 异常堆栈信息

## 日志格式

```
时间戳 - [组件名] - 日志级别 - 消息内容
```

示例：
```
2025-10-31 14:30:15 - [Tianshu Plugin] - INFO - 开始验证 Tianshu API 凭据
```

## 组件标识

- `[Tianshu Plugin]` - Provider 凭据验证
- `[Parse Tool]` - 文档解析工具
- `[GetStatus Tool]` - 任务状态查询工具

## 典型日志输出

### 1. 凭据验证成功

```
================================================================================
开始验证 Tianshu API 凭据
================================================================================
📡 API Base URL: http://localhost:8000
🔑 API Key 长度: 32 字符
📤 发送验证请求:
   URL: http://localhost:8000/api/v1/queue/tasks
   Method: GET
   Headers: X-API-Key=***
   Params: {'limit': 1}
📥 收到响应:
   状态码: 200
   响应头: {...}
✅ 验证成功!
   API Key 有效且用户已激活
   返回任务数: 0
   全局查看权限: True
================================================================================
```

### 2. 凭据验证失败 (403)

```
================================================================================
开始验证 Tianshu API 凭据
================================================================================
📡 API Base URL: http://localhost:8000
🔑 API Key 长度: 32 字符
📤 发送验证请求:
   URL: http://localhost:8000/api/v1/queue/tasks
   Method: GET
   Headers: X-API-Key=***
   Params: {'limit': 1}
📥 收到响应:
   状态码: 403
   响应头: {...}
   响应内容: {"detail":"Inactive user"}
❌ 权限不足 (403)
   可能原因:
   1. 用户未激活 (is_active=False)
   2. 缺少必要权限
   服务器响应: {"detail":"Inactive user"}
❌ 凭据验证失败: API Key validation failed (403 Forbidden). Server response: {"detail":"Inactive user"}
================================================================================
```

### 3. 文档解析任务提交

```
================================================================================
开始执行文档解析任务
================================================================================
📡 API Base URL: http://localhost:8000
📄 文件信息:
   文件名: test.pdf
   文件大小: 1024000 bytes
📋 解析参数:
   backend: auto
   lang: auto
   formula_enable: True
   priority: 0
📤 提交任务到: http://localhost:8000/api/v1/tasks/submit
   Headers: X-API-Key=***
📥 收到响应: 200
✅ 任务提交成功!
   Task ID: abc123
   状态: pending
   文件名: test.pdf
================================================================================
```

### 4. 任务状态查询

```
================================================================================
开始查询任务状态
================================================================================
📡 API Base URL: http://localhost:8000
🔍 查询参数:
   Task ID: abc123
   Format: markdown
   Upload Images: False
📤 发送查询请求: http://localhost:8000/api/v1/tasks/abc123
   Params: {'format': 'markdown', 'upload_images': 'false'}
📥 收到响应: 200
📊 任务状态:
   Task ID: abc123
   文件名: test.pdf
   状态: completed
✅ 任务已完成!
   Markdown 内容长度: 5000 字符
================================================================================
```

## 常见错误日志分析

### 错误 1: 连接失败

```
❌ 连接失败: [Errno 111] Connection refused
   请检查:
   1. Tianshu 服务是否正在运行
   2. URL 是否正确: http://localhost:8000
   3. 网络连接是否正常
```

**解决方案**：
1. 启动 Tianshu 服务
2. 检查 URL 配置（端口号等）
3. 测试网络连接

### 错误 2: 认证失败 (401)

```
❌ 认证失败 (401)
   原因: API Key 无效或格式错误
   详细信息: {"detail":"Could not validate credentials"}
```

**解决方案**：
1. 检查 API Key 是否正确
2. 重新生成 API Key
3. 确认 API Key 未过期

### 错误 3: 权限不足 (403)

```
❌ 权限不足 (403)
   可能原因:
   1. 用户未激活 (is_active=False)
   2. 缺少必要权限
   服务器响应: {"detail":"Inactive user"}
```

**解决方案**：
1. 检查用户激活状态
2. 在数据库中激活用户：
   ```sql
   UPDATE users SET is_active = 1 WHERE username = 'your_username';
   ```
3. 或使用管理员界面激活用户

### 错误 4: 请求超时

```
❌ 请求超时: Request timeout after 10.0 seconds
```

**解决方案**：
1. 检查网络连接
2. 检查服务器负载
3. 增加超时时间（代码中配置）

## 如何查看完整日志

### 方法 1: 在 Dify 控制台查看

Dify 插件的日志会输出到插件运行的控制台。

### 方法 2: 重定向到文件

如果需要保存日志到文件：

```bash
# 运行 Dify 插件并重定向日志
dify plugin run tianshu 2>&1 | tee plugin_debug.log
```

### 方法 3: 调整日志级别

如果需要更详细的日志，可以修改日志级别：

在插件代码中找到：
```python
logger.setLevel(logging.DEBUG)  # 当前级别
```

可选级别：
- `logging.DEBUG` - 最详细
- `logging.INFO` - 正常信息
- `logging.WARNING` - 仅警告
- `logging.ERROR` - 仅错误

## 调试技巧

### 1. 验证 API 连通性

```bash
# 测试服务器连接
curl http://localhost:8000/

# 测试 API Key
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/queue/tasks?limit=1
```

### 2. 检查响应内容

日志会记录完整的 HTTP 响应头和内容（前 500 字符），可以从中判断：
- 服务器是否返回了预期的数据
- 错误消息的具体内容
- API 返回的数据结构

### 3. 追踪请求流程

每个操作都有清晰的流程标记：
- 📡 API 配置
- 📄 文件信息
- 📤 发送请求
- 📥 收到响应
- ✅ 成功
- ❌ 失败

## 获取帮助

如果日志信息不足以解决问题：

1. 收集完整的日志输出
2. 记录操作步骤
3. 在 GitHub 提交 Issue：https://github.com/magicyuan876/mineru-tianshu/issues
4. 附上日志和错误信息

---

**注意**：日志中会隐藏 API Key 的完整内容（显示为 `***`），保护你的凭据安全。
