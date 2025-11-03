# Tianshu 插件启动指南

## 错误："no available node, plugin not found"

这个错误表示 Dify 找不到正在运行的插件实例。

## 解决步骤

### 1. 确认插件正在运行

**重要：必须先启动插件，然后才能在 Dify 中配置！**

#### 启动插件

```bash
cd e:\dify\tianshu
python -m main
```

你应该看到类似以下的输出：
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:xxxx
```

**保持这个窗口运行！** 不要关闭。

### 2. 检查 .env 配置

确保 `.env` 文件配置正确：

```env
INSTALL_METHOD=remote
REMOTE_INSTALL_HOST=localhost
REMOTE_INSTALL_PORT=5003
REMOTE_INSTALL_KEY=586190d4-fc52-4482-89bf-1de9c9f5c186
```

### 3. 在 Dify 中刷新插件

1. **启动插件后**，打开 Dify
2. 进入 **插件管理** 页面
3. 刷新页面（F5 或 Ctrl+F5）
4. 查找 "Tianshu" 或 "天枢" 插件
5. 现在点击配置/授权按钮

### 4. 配置 API 凭据

在弹出的配置窗口中输入：
- **API Base URL**: `http://localhost:8000` (或您的 Tianshu 服务器地址)
- **API Key**: 您的 Tianshu API 密钥

## 常见问题

### Q1: 插件启动失败

**检查依赖是否已安装：**
```bash
pip install -r requirements.txt
```

**查看错误日志：**
```bash
python -m main
# 查看控制台输出的错误信息
```

### Q2: 端口被占用

如果看到 "Address already in use" 错误：

1. 查找占用端口的进程：
```bash
# Windows
netstat -ano | findstr :5003

# 结束进程
taskkill /PID <进程ID> /F
```

2. 或修改 `.env` 中的端口：
```env
REMOTE_INSTALL_PORT=5004
```

### Q3: Dify 连接不上插件

**检查连接配置：**

1. 确认 REMOTE_INSTALL_HOST 和 PORT 正确
2. 确认防火墙没有阻止连接
3. 确认 Dify 和插件在同一网络

**本地调试配置：**
```env
INSTALL_METHOD=remote
REMOTE_INSTALL_HOST=localhost  # 或 127.0.0.1
REMOTE_INSTALL_PORT=5003
REMOTE_INSTALL_KEY=<您的调试密钥>
```

### Q4: 如何获取 REMOTE_INSTALL_KEY？

在 Dify 设置中：
1. 进入 **设置 → 插件**
2. 找到 **调试密钥** 或 **Plugin Debug Key**
3. 复制密钥到 `.env` 文件

## 完整启动流程

### 步骤 1: 准备环境

```bash
cd e:\dify\tianshu
pip install -r requirements.txt
```

### 步骤 2: 配置 .env

编辑 `.env` 文件，确保配置正确：
```env
INSTALL_METHOD=remote
REMOTE_INSTALL_HOST=localhost
REMOTE_INSTALL_PORT=5003
REMOTE_INSTALL_KEY=<从 Dify 获取的密钥>
```

### 步骤 3: 启动插件

```bash
python -m main
```

**保持运行状态！**

### 步骤 4: 在 Dify 中操作

1. 打开 Dify 浏览器页面
2. 刷新页面（F5）
3. 进入 **插件** 或 **工具** 管理
4. 找到 "Tianshu" 插件（可能显示为 "调试中"）
5. 点击 **配置** 或 **授权** 按钮
6. 输入：
   - API Base URL: `http://localhost:8000`
   - API Key: 您的密钥

### 步骤 5: 测试插件

1. 在工作流中添加 "parse-document" 节点
2. 上传测试文件
3. 执行查看结果

## 调试技巧

### 启用详细日志

编辑 `main.py`：
```python
import logging
logging.basicConfig(level=logging.DEBUG)

from dify_plugin import Plugin, DifyPluginEnv

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))

if __name__ == '__main__':
    plugin.run()
```

### 查看插件日志

运行插件时，控制台会显示：
- 凭据验证请求
- API 调用
- 错误信息

### 测试凭据验证

如果配置时报错，检查：
1. Tianshu 服务器是否正在运行
2. API Base URL 是否正确
3. API Key 是否有效
4. 网络连接是否正常

```bash
# 测试 Tianshu 服务器连接
curl http://localhost:8000/api/v1/health

# 测试 API Key
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/v1/queue/tasks?limit=1
```

## 检查清单

启动插件前请确认：

- [ ] Python 3.12+ 已安装
- [ ] 依赖已安装 (`pip install -r requirements.txt`)
- [ ] `.env` 文件配置正确
- [ ] REMOTE_INSTALL_KEY 已从 Dify 获取
- [ ] Tianshu API 服务器正在运行
- [ ] 知道正确的 API Base URL 和 API Key

启动插件后：

- [ ] 插件控制台显示 "Application startup complete"
- [ ] 没有错误信息
- [ ] 在 Dify 中能看到插件（可能标记为调试中）
- [ ] 可以点击配置按钮

## 成功标志

配置成功后：
- ✅ 插件状态变为 "已授权" 或 "已配置"
- ✅ 可以在工作流中使用 parse-document 工具
- ✅ 可以在工作流中使用 get-task-status 工具
- ✅ 工具执行没有认证错误

## 需要帮助？

如果仍有问题：
1. 查看插件控制台的完整错误日志
2. 查看 Dify 浏览器控制台的错误
3. 确认所有服务（Dify、Tianshu API、插件）都在运行
4. 检查网络和防火墙设置
