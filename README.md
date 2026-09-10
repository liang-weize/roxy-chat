# 洛琪希 AI 对话网站 💧

一个支持文字与可选本地语音合成的角色聊天网站。后端使用 FastAPI，语音功能可接入
[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。

> 本仓库只提供程序代码，不包含动漫图片、Wallpaper Engine 视频、原声音频、角色声音模型、
> API Key 或访问口令。请只使用你拥有或已获授权的素材和模型。

## 快速开始

### 第 1 步：创建本地配置

在项目目录打开 PowerShell，复制示例配置：

```powershell
Copy-Item config.example.yaml config.yaml
```

编辑 `config.yaml`，填写自己的 API 地址和模型名。`config.yaml` 已被 `.gitignore` 排除，
不要删除这条忽略规则，也不要在其中填写 API Key。

### 第 2 步：设置 API Key（必做，仅一次）

将 API Key 保存到当前 Windows 用户的环境变量 `ROXY_LLM_API_KEY`，不要直接写入 `config.yaml`。PowerShell 示例：

```powershell
[Environment]::SetEnvironmentVariable('ROXY_LLM_API_KEY', '你的Key', 'User')
```

重新打开启动窗口后即可生效。

### 第 3 步：启动网站

双击 **`start.bat`**（首次运行会自动安装依赖，需联网）。
浏览器自动打开 `http://127.0.0.1:8321`，即可开始对话。

> 默认只有文字。需要语音时继续下一步。

### 第 4 步：安装语音引擎（可选，约 8GB 下载）

双击 **`setup_voice.bat`**，等待下载解压完成，然后：

1. 双击 `voice-engine\GPT-SoVITS\go-api.bat` 启动语音服务
2. 窗口出现 `Uvicorn running on http://127.0.0.1:9880` 字样即成功。**保持这个窗口开着**
3. 将你有权使用的参考音频和模型放到本机目录中，并在 `config.yaml` 里填写对应路径
4. 把 `voice.enabled` 改为 `true`，重启网站
5. 回到网站刷新页面，状态显示“语音就绪”即可

## 日常使用

| 想做什么 | 操作 |
|---|---|
| 开始聊天 | 双击 `start.bat` |
| 让她开口说话 | 先双击 `voice-engine\GPT-SoVITS\go-api.bat`（窗口保持开着），再双击 `start.bat` |
| 关闭 | 直接关掉命令行窗口 |
| 静音她的语音 | 点右上角"语音"按钮 |
| 更换立绘 | 将有权使用的图片放入本机素材目录后，点击左侧立绘图片 |
| 切换动态背景 | 点右上角“🎬 背景”按钮循环切换；只添加有权使用的视频 |
| 重听某句语音 | 点消息下方的"重播语音" |

## 开源与第三方内容

本项目代码使用 MIT License。GPT-SoVITS 是独立的第三方项目，使用时请同时遵守其许可证。
角色名称、人物形象、图片、音视频和训练模型不因本项目的 MIT License 获得授权；请自行确认
每项素材的许可，并保留必要的署名和许可证文件。
