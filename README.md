# 洛琪希 AI 对话网站 💧

一个支持文字聊天和可选本地语音合成的角色聊天网站。后端使用 FastAPI，语音可接入
[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。

仓库包含代码和抽象占位图，不包含动漫图片、原声音频、角色声音模型、API Key 或访问口令。
文字聊天不需要安装语音引擎；请自行准备有权使用的自定义素材。

## Windows 快速开始

### 1. 安装 Python 并下载代码

安装 Python 3.12，在安装程序中勾选 **Add python.exe to PATH**。
从 GitHub 点击 **Code → Download ZIP**，解压到一个可写文件夹。
已有 Python 的用户可用 `python --version` 或 `py -3 --version` 查看版本。

### 2. 创建本地配置

双击 `start.bat`。若没有配置，启动器会生成 `config.yaml` 并暂停。
用记事本打开它，修改 `llm.base_url` 和 `llm.model`：
接口地址通常以 `/v1` 结尾，模型名填写你的服务商实际提供的模型。

不要覆盖已有的配置。也可以在项目目录的 PowerShell 中手动创建：

```powershell
Copy-Item config.example.yaml config.yaml
```

`config.yaml` 已被 Git 忽略；`api_key` 留空，密钥按下一步设置。

### 3. 设置 API Key

在 PowerShell 中执行（把“你的Key”替换成自己的密钥）：

```powershell
[Environment]::SetEnvironmentVariable('ROXY_LLM_API_KEY', '你的Key', 'User')
```

重新打开启动窗口。启动器会读取此环境变量，但不会显示密钥。
聊天请求会使用你的 API 账户额度。

### 4. 启动

再次双击 `start.bat`，首次会在项目的 `.venv-web` 中创建独立环境并安装
`requirements.txt` 中的依赖，需要联网。之后依赖没有变化时会直接启动。

服务就绪后浏览器自动打开 `http://127.0.0.1:8321`（修改端口后以配置为准）。
保持窗口开启；按 Ctrl+C 或关闭窗口停止网站。`启动洛琪希.bat` 与 `run_website.bat`
也是同一个文字网站的启动入口。未配置接口时可以预览界面，发送消息会提示补全配置。

没有自定义图片时显示仓库自带的占位图。添加图片、背景的方法见 [素材说明](assets/README.md)。

## 可选：语音

1. 运行 `setup_voice.bat` 下载和解压 GPT-SoVITS 整合包（约 8GB，需要额外磁盘空间）。
2. 准备有权使用的参考音频和模型，在本机 `config.yaml` 中填写路径、参考台词、语言及模型路径。
3. 把 `voice.enabled` 改为 `true`。
4. 单独双击 `run_voice.bat`，等待语音服务就绪，保持窗口开启。
5. 启动或重启网站，在网页中开启语音。

网站启动器不会自动启动语音引擎。已有整合包的用户也可用其中的 Python 3.9 或以上版本作为备用启动环境。
这种情况下会复用整合包中已安装的依赖；如果依赖不全，启动器会提示安装完整的 Python 3.12。
模型、音频和语音引擎均不随 Git 仓库分发。

## 常见问题

- **窗口提示找不到 Python**：安装 Python 后勾选 PATH 选项，再重新打开启动脚本。
- **依赖安装失败**：检查网络后重新运行。启动器不会删除已有环境；若环境损坏，
  可关闭网站后将 `.venv-web` 重命名为备份目录，再运行以创建新环境。
- **页面提示配置接口**：检查 API 地址、模型名和 `ROXY_LLM_API_KEY`，保存后重启。
- **端口被占用**：关闭之前启动的网站窗口，或修改 `config.yaml` 中的 `server.port`。
- **想让朋友访问**：GitHub 只托管代码。远程访问需另外部署或配置隧道；
  使用本项目的 [公网分享指南](公网分享指南.md) 前，需要自行安装 cloudflared，并设置访问口令。
- **只想检查安装**：在项目目录运行 `start.bat --check`。
- **不自动打开浏览器**：运行 `start.bat --no-browser`。

## 开发与验证

先完成配置和依赖安装，然后在项目目录运行：

```powershell
.\.venv-web\Scripts\python.exe -m unittest discover -s tests -v
```

测试会在临时目录中使用示例配置和模拟回复，验证无私有素材启动、配置提示、文字聊天、
流式响应及语音关闭行为，不需要真实 API Key。

## 开源与第三方内容

本项目代码和自带占位图使用 MIT License。GPT-SoVITS 是独立项目，使用时遵守其许可证。
角色名称、人物形象、图片、音视频和训练模型不因本项目的 MIT License 获得授权；
请自行确认每项素材的许可，并保留必要的署名和许可证文件。
