# ADBC (ADB Connect)

`adbc` 是一个高效的异步 Python 工具，用于自动扫描局域网内开启了 TCP/IP 调试（默认 5555 端口）的 Android 设备并自动建立连接。

### 核心特性

* **自动网段识别**：无需手动输入 IP，自动获取本机所在网段。
* **异步并发扫描**：基于 `asyncio`，在不到 1 秒内完成整个 /24 网段（254 个 IP）的扫描。
* **一键连接**：发现开放端口后自动执行 `adb connect`。
* **轻量化**：无重度依赖。

---

## 🛠 安装

推荐使用 [uv](https://github.com/astral-sh/uv) 进行安装。`uv` 会自动为您管理 Python 环境并将脚本添加到系统的 PATH 中。

```bash
uv tool install https://github.com/ljxi/adbc.git

```

> **注意**：请确保您的系统中已安装并配置了 `adb` 命令行工具。

---

## 🚀 使用方法

安装完成后，直接在终端输入 `adbc` 即可：

```bash
adbc

```

### 运行流程

1. **启动服务**：脚本会尝试后台初始化 `adb devices` 确保 ADB 服务正在运行。
2. **网段探测**：自动识别如 `192.168.1.x` 的局域网网段。
3. **高速扫描**：并发探测该网段下所有 IP 的 `5555` 端口。
4. **自动连接**：对所有响应的设备执行连接指令。

**输出示例：**

```text
Scanning for ADB devices on 192.168.31.0/24...
Found device at 192.168.31.45, connecting...
✓ Connected to 192.168.31.45
Found device at 192.168.31.102, connecting...
✓ Connected to 192.168.31.102

```

---

## 🔧 工作原理

1. **UDP 联通测试**：通过向 `8.8.8.8` 发送数据包（不实际发送）获取本机局域网 IP。
2. **信号量控制**：使用 `asyncio.Semaphore` 限制并发数（默认 100），在保证速度的同时避免过度消耗系统资源。
3. **端口检测**：使用 `asyncio.open_connection` 进行非阻塞的 TCP 握手。

---
