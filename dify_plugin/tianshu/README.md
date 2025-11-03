# Tianshu Dify Plugin

**Author:** magic_yuan  
**Version:** 0.0.1  
**Type:** Tool Plugin

## Description

Tianshu (天枢) is an enterprise-grade, all-in-one AI data preprocessing platform that supports converting various data types (PDF, Office documents, images, audio, video) into Markdown and JSON formats.

This Dify plugin integrates Tianshu as a tool provider, allowing you to use document parsing capabilities in your Dify workflows.

GitHub: https://github.com/magicyuan876/mineru-tianshu

## Features

- **File Upload Support**: Direct file selection in Dify
- **Multiple Formats**: Parse PDF, Office documents (Word, Excel, PowerPoint), images, audio, and video files
- **Output Formats**: Convert documents to Markdown or JSON format
- **Asynchronous Processing**: Submit tasks and query results separately for better workflow control
- **API Key Authentication**: Secure authentication with X-API-Key header
- **Table Recognition**: Always enabled for accurate table extraction
- **Formula Recognition**: Optional formula recognition support

## Installation

1. Install the plugin in your Dify instance
2. Configure the plugin with your Tianshu API credentials:
   - **API Base URL**: The base URL of your Tianshu API server (e.g., `http://localhost:8000`)
   - **API Key**: Your API Key for authentication

## Configuration

### Getting Your API Key

To use this plugin, you need to obtain an API Key from your Tianshu server. The API Key is used for authentication via the `X-API-Key` header.

Please refer to your Tianshu server documentation for instructions on how to generate an API Key.

### Plugin Configuration

When configuring the plugin in Dify, you'll need to provide:

1. **API Base URL**: The base URL where your Tianshu API server is running
   - Example: `http://localhost:8000` or `https://api.example.com`
2. **API Key**: Your authentication API Key

## Tools

### 1. parse-document

Submit a document parsing task and get a `task_id` for querying results later.

**Parameters:**
- `file` (required): File to be parsed (supports PDF, Office docs, images, etc.)
- `backend` (optional): Processing backend - `auto` (default), `pipeline`, `deepseek-ocr`, `paddleocr-vl`, `markitdown`, `sensevoice`, `video`
- `lang` (optional): Language - `auto` (default), `ch`, `en`, `korean`, `japan`
- `formula_enable` (optional): Enable formula recognition (default: `true`)
- `priority` (optional): Task priority, higher number = higher priority (default: `0`)

**Returns:**
```json
{
  "task_id": "abc123",
  "message": "任务已提交，请使用 get_task_status 工具查询结果",
  "file_name": "document.pdf",
  "status": "pending"
}
```

### 2. get-task-status

Query the status and result of a document parsing task.

**Parameters:**
- `task_id` (required): The task ID returned from `parse-document`
- `format` (optional): Output format - `markdown` (default), `json`, or `both`
- `upload_images` (optional): Upload images to MinIO and replace links (default: `false`)

**Returns:**

When completed:
```json
{
  "task_id": "abc123",
  "status": "completed",
  "file_name": "document.pdf",
  "content": "Markdown content...",
  "json_content": {...}
}
```

When processing:
```json
{
  "task_id": "abc123",
  "status": "processing",
  "file_name": "document.pdf",
  "message": "任务正在处理中"
}
```

## Usage Examples

### Example 1: Parse Document

```
1. Use parse-document tool:
   - file: Select your document
   - backend: auto

2. Use get-task-status tool:
   - task_id: <from step 1>
   - format: markdown
```

### Example 2: Workflow with Retry Logic

```
1. parse-document → task_id
2. get-task-status → check status
3. If status != "completed":
   - Wait (or use delay node)
   - Loop back to step 2
4. If status == "completed":
   - Use the parsed content
```

## Supported File Formats

- **Documents**: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT
- **Images**: PNG, JPG, JPEG
- **Audio**: WAV, MP3, FLAC, M4A, OGG
- **Video**: MP4, AVI, MKV, MOV, FLV, WMV
- **Web**: HTML
- **Text**: TXT, CSV

## Error Handling

The plugin handles various error scenarios:

- **Authentication Errors** (401/403): Invalid API Key or insufficient permissions
- **Network Errors**: Connection failures, timeouts
- **Task Errors**: Task not found, task failed

## Requirements

- Python 3.12+
- `dify_plugin>=0.4.0,<0.7.0`
- `httpx>=0.24.0`
- `yarl`

## License

Apache License 2.0

## Support

For issues and questions, please refer to the [Tianshu project](https://github.com/magicyuan876/mineru-tianshu).
