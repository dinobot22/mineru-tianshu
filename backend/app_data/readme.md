# 文件夹说明

### 默认后端运行时存储文件夹. 当前文件夹存储后端运行产生的全部数据, 如果需要更改存储位置,请修改 backend/.env 中的 "BACKEND_APP_DATA_ROOT_PATH" 变量

### 如果未修改存储位置,运行后产生下述文件结构
```
app_data/
├── mineru_tianshu_output/  # 任务输出文件存储文件夹
├── uploads/  # 上传文件的存储文件夹
├── mineru_tianshu.db  # 任务数据库文件
├── readme.md  # 说明文档
```
