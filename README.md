# ByteScope 字节窥探 🔍

<!-- Language Switch -->
**Languages:** [🇨🇳 中文](#) | [🇺🇸 English](#english-version)

> 📢 **语言支持声明**: 软件客户端目前仅支持中文，英文版本正在开发中，后续版本将支持多语言。网页管理端可使用浏览器自带翻译功能实现英文显示。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.7+-green.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-2.2+-red.svg)](https://flask.palletsprojects.com)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey.svg)](https://github.com/xzajyb/bytescope)

> 🔒 **注意**: 本开源项目仅包含服务器端代码。客户端和验证功能基于安全考虑不对外开源。（后续可能会）

一个功能强大的远程监控管理平台，专为企业和个人用户提供安全可靠的设备监控解决方案。

## ✨ 功能特性

### 🖥️ 核心监控功能
- **屏幕截图** - 实时捕获设备屏幕，支持自定义间隔
- **屏幕录制** - 远程控制录屏，支持实时和定时录制
- **键盘记录** - 详细记录键盘输入，支持历史和实时模式
- **系统信息** - 收集CPU、内存、磁盘等系统性能数据
- **文件浏览** - 安全的远程文件系统访问

### 🌐 Web管理界面
- **响应式设计** - 支持桌面、平板、手机等多种设备
- **实时监控** - 实时查看客户端状态和数据
- **多客户端管理** - 统一管理多个监控终端
- **数据可视化** - 直观的图表和统计信息
- **操作日志** - 完整的操作记录和审计追踪

### 🔧 系统管理
- **配置管理** - 远程配置客户端参数
- **自动清理** - 可配置的数据清理策略
- **后台捕获** - 计划任务和自动化监控
- **状态监控** - 客户端在线状态实时追踪

### 🔐 安全特性
- **权限验证** - 基于密钥的访问控制
- **数据加密** - 传输和存储数据加密保护
- **审计日志** - 完整的操作记录
- **访问控制** - 细粒度的权限管理

## 🏗️ 技术架构

### 后端技术栈
- **Python 3.7+** - 核心开发语言
- **Flask 2.2+** - Web框架
- **文件系统** - 数据存储（无需额外数据库）
- **WebSocket** - 实时通信
- **RESTful API** - 标准化接口设计

### 前端技术栈
- **Bootstrap 5** - 响应式UI框架
- **JavaScript ES6+** - 前端交互逻辑
- **WebSocket** - 实时数据更新
- **Chart.js** - 数据可视化图表

## 🚀 快速开始

### 系统要求
```
Python 3.7+
操作系统: Windows, Linux, macOS
RAM: 最少 512MB
磁盘: 最少 1GB 可用空间
网络: 支持TCP/IP通信
```

### 安装部署

#### 1. 克隆仓库
```bash
git clone https://github.com/xzajyb/bytescope.git
```

#### 2. 安装依赖
```bash
cd server
pip install -r requirements.txt
```

#### 3. 启动服务器
```bash
python run.py
```

#### 4. 访问管理界面
打开浏览器访问: `http://127.0.0.1:5000`

## 🎯 小白快速上手教程

> 💡 **适用范围**: 本教程适用于局域网内部署，如需跨网络访问请参考[内网穿透设置](#内网穿透设置)

### 📋 第一步：部署服务器

1. **启动服务器**
   ```bash
   cd server
   python run.py
   ```

2. **复制服务器IP地址**
   - 服务器启动后，控制台会显示监听地址
   - 复制显示的IP地址（如：`http://192.168.1.100:5000`）

   ![服务器启动示例](https://github.com/xzajyb/ByteScope/blob/main/P1.png)

### 📋 第二步：配置客户端

1. **在监控对象设备上打开客户端程序**

2. **首次向导配置**
   - 客户端首次启动会出现配置向导
   - 在"服务器地址"输入框中粘贴第一步复制的IP地址(服务器地址配置后续可以在客户端设置界面重新设置，方法：在客户端目录创建"设置.txt"文件重新客户端可重新打开设置界面)
   - 点击"确认"或"连接"按钮

3. **连接成功**
   - 客户端成功连接到服务器
   - 状态显示为"已连接"

### 📋 第三步：开始监控

1. **打开管理界面**
   - 在您的设备浏览器中访问复制的IP地址
   - 进入ByteScope管理界面

2. **查看客户端**
   - 在主页面可以看到已连接的客户端
   - 点击客户端名称进入详细管理页面

3. **开始使用各项功能**
   - 📸 实时截图
   - 🎥 录屏功能  
   - ⌨️ 键盘记录
   - 📁 文件浏览

### 🌐 内网穿透设置

如果需要**跨网络**访问（不在同一局域网），您需要：

#### 方案一：使用内网穿透（推荐）
- 推荐使用 [花生壳内网穿透服务](https://hsk.oray.com/)
- 专业稳定，支持多种协议
- 无需公网IP，即可实现远程访问

#### 方案二：公网IP部署
- 如果您有公网IP，可直接部署到公网
- 需要配置防火墙和安全策略
- 确保网络安全防护

> ⚠️ **重要提醒**: 跨网络部署时，请特别注意网络安全和数据保护！

## 🔐 验证机制说明

> **重要**: 为确保软件的合法合规使用，系统内置了验证机制

### 📋 验证功能限制

在验证过程中，以下功能将被**暂时禁用**：
- 🚫 录屏功能
- 🚫 截屏功能  
- 🚫 键盘捕获
- 🚫 系统性能监控
- 🚫 实时日志功能

### ⏰ 验证时间安排

**自动验证周期**:
- 📅 系统会在**1周内**自动安排验证
- 🔄 验证次数：**2-4次**（一天最多2次）
- ⏱️ 单次验证有效期：**6小时**
- 🎯 总验证次数：**4次**

### 📝 验证操作步骤

1. **获取验证文件**
   ```
   前往客户端目录：
   📁 
   └── verification_key_XXXX.txt  ← 复制最新的验证文件
   ```

2. **进行网页验证**
   - 访问监控管理网页
   - 打开验证界面弹窗
   - 粘贴验证文件内容
   - 点击验证按钮

3. **验证文件说明**
   - `verification_data.enc` - 验证数据文件
   - `.scheduled_verifications.enc` - 计划验证文件
   - `verification_key_XXXX.txt` - 验证密钥文件

### ⚠️ 验证过期/次数耗尽处理

**当出现以下情况时**：
- ❌ 验证超时（超过6小时）
- ❌ 验证次数耗尽（超过4次）
- ❌ 验证功能失效

**解决方案**：
1. 💎 **使用永久激活码**（推荐）
   - 永久激活码不受次数和时间限制
   - 一次激活，终身有效
   
2. 🔄 **远程卸载重装**
   - 远程卸载客户端程序
   - 重新下载安装客户端
   
3. 🗑️ **删除验证文件**
   - 手动删除以下验证相关文件：
     - `verification_data.enc`
     - `.scheduled_verifications.enc`
     - `verification_key_XXXX.txt`

### 💎 永久验证方案(推荐)

如果希望避免重复验证或解决验证问题，可选择**永久验证**：

#### 💡 永久验证优势：
- ✅ **无时间限制**: 不受6小时有效期约束
- ✅ **无次数限制**: 不受4次验证次数限制  
- ✅ **一次激活**: 终身有效，无需重复操作
- ✅ **功能完整**: 所有监控功能正常使用

#### 💳 支持的支付方式：
- 💰 **支付宝** - 国内用户推荐
- 💚 **微信支付** - 便捷移动支付
- 🌐 **PayPal** - 国际用户支持

#### 🎉 限时优惠活动：
> **⏰ 4折优惠**: 仅需 **20 RMB** （原价50 RMB）  
> **截止时间**: 2025年10月3日 05:34  
> **活动剩余**: 机会有限，建议尽快参与！

#### 获取永久激活码步骤：
1. **复制机器码**: 从验证弹窗复制显示的机器码
2. **选择支付方式**: 前往 [永久验证页面](https://afdian.tv/item/3a378fa03ec411f0b59b52540025c377)
   - 支持支付宝/微信/PayPal多种支付方式
   - 活动期间享受4折优惠价格
3. **提交信息**: 在支付页面输入您的验证ID和机器码
4. **完成支付**: 选择合适的支付方式完成付款
5. **获取激活码**: 支付成功后获得**FV开头的20位激活码**
6. **激活使用**: 在验证输入框输入激活码完成永久验证

#### 永久激活码格式：
```
FV + 18位字符码
示例：FV1234567890ABCDEF12
```

> **注意**: 永久激活码必须以**FV**开头，否则会被识别为普通验证码，会消耗验证次数

### 🛡️ 验证机制意义

此验证机制旨在：
- ✅ 确保软件合法合规使用
- ✅ 防止恶意滥用和传播
- ✅ 保护用户隐私和数据安全
- ✅ 维护软件生态健康发展

## 📖 使用指南

### 服务器配置

#### 基础配置
服务器默认运行在端口 `5000`，可以通过修改 `run.py` 中的配置进行调整：

```python
# 服务器配置
host = "0.0.0.0"  # 监听地址
port = 5000       # 监听端口
debug = False     # 生产环境建议关闭调试模式
```

#### 高级配置

**上传限制**
```python
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB
```

**自动清理**
```python
app.config["AUTO_CLEANUP_ENABLED"] = True   # 启用自动清理
app.config["AUTO_CLEANUP_DAYS"] = 30        # 保留30天数据
app.config["AUTO_CLEANUP_INTERVAL"] = 24    # 每24小时清理一次
```

### API接口

#### 客户端注册
```http
POST /upload
Content-Type: multipart/form-data

参数:
- client_id: 客户端唯一标识
- hostname: 主机名
- username: 用户名
- file: 上传文件
```

#### 获取客户端列表
```http
GET /api/clients

响应:
{
  "clients": [
    {
      "id": "client_id",
      "hostname": "DESKTOP-ABC123",
      "username": "user1",
      "last_seen": "2024-01-09T10:30:00",
      "status": "online"
    }
  ]
}
```

#### 发送远程命令
```http
POST /api/send_command/{client_id}
Content-Type: application/json

{
  "type": "screenshot",  // 命令类型
  "parameters": {}       // 命令参数
}
```

### Web界面使用

#### 1. 客户端管理
- 查看所有连接的客户端
- 监控客户端在线状态
- 管理客户端配置

#### 2. 数据查看
- **截图**: 查看历史截图，支持缩略图和全屏预览
- **录屏**: 播放录制的视频文件
- **键盘记录**: 查看键盘输入历史
- **系统信息**: 监控系统性能指标

#### 3. 远程控制
- 发送截图命令
- 启动/停止录屏
- 下载指定文件
- 浏览文件系统

## 📁 项目结构

```
bytescope/
├── server/                 # 服务器端代码（开源）
│   ├── server.py          # 主服务器文件
│   ├── run.py             # 启动脚本
│   ├── requirements.txt   # Python依赖
│   ├── templates/         # HTML模板
│   │   ├── index.html     # 主页面
│   │   ├── client.html    # 客户端详情页
│   │   └── ...
│   ├── static/            # 静态资源
│   │   ├── js/           # JavaScript文件
│   │   └── images/       # 图片资源
│   └── uploads/          # 数据存储目录
├── client/                # 客户端代码（不开源）
├── config/               # 配置文件
├── docs/                 # 文档
└── README.md            # 项目说明
```

## 🔧 配置说明

### 服务器配置修改
如需修改服务器配置，请直接编辑以下文件：

**修改监听地址和端口** (`server/run.py`):
```python
# 服务器配置
host = "0.0.0.0"  # 修改监听地址
port = 5000       # 修改端口
debug = False     # 生产环境设置为False
```

**修改上传限制** (`server/server.py`):
```python
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 修改上传大小限制
```

**修改自动清理设置** (`server/server.py`):
```python
app.config["AUTO_CLEANUP_ENABLED"] = True   # 启用自动清理
app.config["AUTO_CLEANUP_DAYS"] = 30        # 保留天数
app.config["AUTO_CLEANUP_INTERVAL"] = 24    # 清理间隔(小时)
```

## 🛡️ 安全注意事项

### 生产环境部署
1. **更改默认端口**: 避免使用默认的5000端口
2. **启用HTTPS**: 配置SSL证书保护数据传输
3. **防火墙配置**: 限制访问IP范围
4. **定期备份**: 设置数据备份策略
5. **监控日志**: 关注异常访问和错误日志

### 权限管理
- 建议在受控环境中部署
- 定期更新密钥和访问凭证
- 监控客户端连接状态
- 记录所有操作日志

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：



### 开发规范
- 遵循 PEP 8 Python编码规范
- 添加适当的注释和文档
- 编写单元测试
- 更新相关文档

## 📋 更新日志

### v1.0.1 (2025-6-9)
- 🔧 **新增远程开机自启动管理功能**
  - 客户端支持远程开启/关闭开机自启动
  - 网页端添加自启动控制按钮（检查、开启、关闭）
  - 实时显示开机自启动状态（启动文件夹、注册表、整体状态）
  - 支持详细状态反馈和错误处理
- ✨ **优化客户端初始配置体验**
  - 简化首次运行向导界面
  - 移除复杂的法律确认文本输入要求
  - 改为简单的复选框确认方式
  - 提升用户配置便利性
- ⚙️ **新增客户端设置访问方式**
  - 在客户端目录创建"设置.txt"文件可重新打开设置界面
  - 方便用户后续修改服务器地址等配置
  - 无需重新安装即可调整客户端参数


### v1.0.0 (2025-6-9)
- 🎉 首次发布
- 📸 基础截图功能
- 🎥 录屏功能
- ⌨️ 键盘记录功能
- 🖥️ 系统信息监控
- ✨ 新增实时监控功能
- 🔧 优化数据存储机制
- 🌐 改进Web界面设计
- 🔐 增强安全验证
- ✨ 新增永久验证功能

## ❓ 常见问题

### Q: 如何获取客户端程序？
A: 客户端程序基于安全考虑不对外开源，如需获取请联系项目维护者。

### Q: 支持哪些操作系统？
A: 服务器端支持Windows, Linux, macOS。客户端主要支持Windows系统。

### Q: 如何配置HTTPS？
A: 可以使用Nginx作为反向代理配置SSL证书，或直接在Flask中配置SSL上下文。

### Q: 数据存储在哪里？
A: 默认存储在 `server/uploads/` 目录，支持自定义存储路径。

### Q: 如何备份数据？
A: 定期备份 `uploads/` 目录和配置文件即可。

## 📞 技术支持

- **GitHub Issues**: [提交问题](https://github.com/xzajyb/bytescope/issues)

- **邮件**: yy222dghjbk@163.com

## 📄 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。

## ⚖️ 法律声明与合规要求

> **⚠️ 严重法律风险警告**: 本软件涉及设备监控功能，使用前必须了解相关法律风险！

### 📋 相关法律条文

**《中华人民共和国民法典》第一千零三十二条、一千零三十三条**
- 自然人享有隐私权，任何组织或个人不得侵害他人隐私权
- 禁止拍摄、窥视、窃听、公开他人的私密活动
- 禁止处理他人的私密信息

**《中华人民共和国治安管理处罚法》第四十二条**
- 偷窥、偷拍、窃听、散布他人隐私的，处五日以下拘留或五百元以下罚款
- 情节较重的，处五日以上十日以下拘留，可并处五百元以下罚款

**《中华人民共和国刑法》第二百五十三条之一**
- 违反国家规定，向他人出售或提供公民个人信息，情节严重的，处三年以下有期徒刑或拘役
- 窃取或以其他方法非法获取公民个人信息的，依照规定处罚

### ✅ 合法使用场景

本软件**仅限**以下合法场景使用：
- 🏠 **家长监护**: 监控未成年子女的设备使用情况
- 🏢 **企业管理**: 监控企业自有设备，需经员工明确同意
- 🔧 **设备维护**: IT管理员维护企业网络设备
- 📚 **学术研究**: 网络安全、系统监控相关的学术研究

### ❌ 严禁使用场景

**绝对禁止**将本软件用于：
- 🚫 未经授权监控他人设备
- 🚫 窃取他人个人信息、隐私数据
- 🚫 商业间谍、竞争情报收集
- 🚫 任何违法犯罪活动

### 📝 使用前必须确认

使用本软件前，您必须确保：
1. ✅ 拥有被监控设备的**合法所有权**或**明确授权**
2. ✅ 已告知相关人员并获得**书面同意**（如适用）
3. ✅ 使用目的**符合当地法律法规**
4. ✅ 不会侵犯任何第三方的**隐私权**和**个人信息权**

### 🛡️ 免责声明

- 本项目**仅供技术学习和研究使用**
- 开发者**不对任何滥用行为承担责任**
- 使用者须**自行承担**因使用本软件产生的**所有法律风险**
- 使用本软件即表示您**完全理解并承担**上述法律风险
- 如不同意上述条款，请**立即停止使用**并删除本软件

> **💡 建议**: 在企业或机构环境中使用前，强烈建议咨询专业律师以确保合规。

---

<div align="center">
  <p>如果这个项目对您有帮助，请给我们一个 ⭐ Star！</p>
  <p>Made with ❤️ by ByteScope Team</p>
</div>

---

# English Version

**Languages:** [🇨🇳 中文](#bytescope-字节窥探-) | [🇺🇸 English](#)

> 📢 **Language Support Notice**: The client software currently supports Chinese only. English version is under development for future releases. The web management interface can use browser's built-in translation feature for English display.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.7+-green.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-2.2+-red.svg)](https://flask.palletsprojects.com)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey.svg)](https://github.com/xzajyb/bytescope)

> 🔒 **Notice**: This open source project only includes server-side code. Client and verification functions are not open source for security reasons. (May be released later)

A powerful remote monitoring management platform designed to provide secure and reliable device monitoring solutions for enterprises and individual users.

## ✨ Key Features

### 🖥️ Core Monitoring Functions
- **Screen Capture** - Real-time screen capture with customizable intervals
- **Screen Recording** - Remote control screen recording with real-time and scheduled recording
- **Keyboard Logging** - Detailed keyboard input recording with historical and real-time modes
- **System Information** - Collect CPU, memory, disk and other system performance data
- **File Browsing** - Secure remote file system access

### 🌐 Web Management Interface
- **Responsive Design** - Support for desktop, tablet, mobile and other devices
- **Real-time Monitoring** - Real-time view of client status and data
- **Multi-client Management** - Unified management of multiple monitoring terminals
- **Data Visualization** - Intuitive charts and statistical information
- **Operation Logs** - Complete operation records and audit trails

### 🔧 System Management
- **Configuration Management** - Remote configuration of client parameters
- **Auto Cleanup** - Configurable data cleanup policies
- **Background Capture** - Scheduled tasks and automated monitoring
- **Status Monitoring** - Real-time tracking of client online status

### 🔐 Security Features
- **Permission Verification** - Key-based access control
- **Data Encryption** - Encrypted protection of transmitted and stored data
- **Audit Logs** - Complete operation records
- **Access Control** - Fine-grained permission management

## 🏗️ Technical Architecture

### Backend Technology Stack
- **Python 3.7+** - Core development language
- **Flask 2.2+** - Web framework
- **File System** - Data storage (no additional database required)
- **WebSocket** - Real-time communication
- **RESTful API** - Standardized interface design

### Frontend Technology Stack
- **Bootstrap 5** - Responsive UI framework
- **JavaScript ES6+** - Frontend interaction logic
- **WebSocket** - Real-time data updates
- **Chart.js** - Data visualization charts

## 🚀 Quick Start

### System Requirements
```
Python 3.7+
Operating System: Windows, Linux, macOS
RAM: Minimum 512MB
Disk: Minimum 1GB available space
Network: TCP/IP communication support
```

### Installation and Deployment

#### 1. Clone Repository
```bash
git clone https://github.com/xzajyb/bytescope.git
```

#### 2. Install Dependencies
```bash
   cd server
pip install -r requirements.txt
```

#### 3. Start Server
```bash
   python run.py
```

#### 4. Access Management Interface
Open browser and visit: `http://127.0.0.1:5000`

## 🎯 Quick Start Tutorial for Beginners

> 💡 **Scope**: This tutorial applies to LAN deployment. For cross-network access, please refer to [Network Penetration Setup](#network-penetration-setup)

### 📋 Step 1: Deploy Server

1. **Start Server**
   ```bash
   cd server
   python run.py
   ```

2. **Copy Server IP Address**
   - After server starts, the console will display the listening address
   - Copy the displayed IP address (e.g., `http://192.168.1.100:5000`)

   ![Server Startup Example](https://github.com/xzajyb/ByteScope/blob/main/P1.png)

### 📋 Step 2: Configure Client

1. **Open Client Program on Target Device**

2. **First-time Setup Wizard**
   - Client will show configuration wizard on first startup
   - Paste the IP address from Step 1 into the "Server Address" input box(The server address configuration can be reset in the client settings interface later, method: create a "设置.txt" file in the client directory and re-open the setting interface on the client side)
   - Click "Confirm" or "Connect" button

3. **Connection Success**
   - Client successfully connects to server
   - Status shows "Connected"

### 📋 Step 3: Start Monitoring

1. **Open Management Interface**
   - Visit the copied IP address in your device's browser
   - Enter ByteScope management interface

2. **View Clients**
   - See connected clients on the main page
   - Click client name to enter detailed management page

3. **Start Using Features**
   - 📸 Real-time Screenshots
   - 🎥 Screen Recording
   - ⌨️ Keyboard Logging
   - 📁 File Browsing

### 🌐 Network Penetration Setup

If you need **cross-network** access (not on the same LAN), you need:

#### Option 1: Use Network Penetration (Recommended)
- Recommended: [Peanut Shell Network Penetration Service](https://hsk.oray.com/)
- Professional and stable, supports multiple protocols
- No public IP required, enables remote access

#### Option 2: Public IP Deployment
- If you have a public IP, you can deploy directly to the public network
- Need to configure firewall and security policies
- Ensure network security protection

> ⚠️ **Important Reminder**: When deploying across networks, pay special attention to network security and data protection!

## 🔐 Verification Mechanism

> **Important**: To ensure legal and compliant use of the software, the system has a built-in verification mechanism

### 📋 Verification Function Restrictions

During verification, the following functions will be **temporarily disabled**:
- 🚫 Screen recording
- 🚫 Screen capture
- 🚫 Keyboard capture
- 🚫 System performance monitoring
- 🚫 Real-time logging

### ⏰ Verification Schedule

**Automatic Verification Cycle**:
- 📅 System will automatically schedule verification **within 1 week**
- 🔄 Verification times: **2-4 times** (maximum 2 times per day)
- ⏱️ Single verification validity: **6 hours**
- 🎯 Total verification count: **4 times**

### 📝 Verification Steps

1. **Get Verification File**
   ```
   Go to client directory:
   📁 
   └── verification_key_XXXX.txt  ← Copy the latest verification file
   ```

2. **Perform Web Verification**
   - Access monitoring management webpage
   - Open verification interface popup
   - Paste verification file content
   - Click verification button

3. **Verification File Description**
   - `verification_data.enc` - Verification data file
   - `.scheduled_verifications.enc` - Scheduled verification file
   - `verification_key_XXXX.txt` - Verification key file

### ⚠️ Verification Expiry/Count Exhaustion Handling

**When the following situations occur**:
- ❌ Verification timeout (over 6 hours)
- ❌ Verification count exhausted (over 4 times)
- ❌ Verification function failure

**Solutions**:
1. 💎 **Use Permanent Activation Code** (Recommended)
   - Permanent activation codes are not limited by count and time
   - One-time activation, lifetime validity
   
2. 🔄 **Remote Uninstall and Reinstall**
   - Remotely uninstall client program
   - Re-download and install client
   
3. 🗑️ **Delete Verification Files**
   - Manually delete the following verification-related files:
     - `verification_data.enc`
     - `.scheduled_verifications.enc`
     - `verification_key_XXXX.txt`

### 💎 Permanent Verification Solution (Recommended)

If you want to avoid repeated verification or solve verification problems, you can choose **permanent verification**:

#### 💡 Permanent Verification Advantages:
- ✅ **No Time Limit**: Not constrained by 6-hour validity period
- ✅ **No Count Limit**: Not limited by 4 verification counts
- ✅ **One-time Activation**: Lifetime validity, no repeated operations needed
- ✅ **Full Functionality**: All monitoring functions work normally

#### 💳 Supported Payment Methods:
- 💰 **Alipay** - Recommended for domestic users
- 💚 **WeChat Pay** - Convenient mobile payment
- 🌐 **PayPal** - International user support

#### 🎉 Limited-time Promotion:
> **⏰ 60% OFF**: Only **20 RMB** (Original price 50 RMB)  
> **Deadline**: October 3, 2025 05:34  
> **Limited availability**: Don't miss out!

#### Steps to Get Permanent Activation Code:
1. **Copy Machine Code**: Copy the machine code displayed in the verification popup
2. **Choose Payment Method**: Go to [Permanent Verification Page](https://afdian.tv/item/3a378fa03ec411f0b59b52540025c377)
   - Supports Alipay/WeChat/PayPal multiple payment methods
   - Enjoy 60% discount during promotion period
3. **Submit Information**: Enter your verification ID and machine code on the payment page
4. **Complete Payment**: Choose suitable payment method to complete payment
5. **Get Activation Code**: After successful payment, get **20-digit activation code starting with FV**
6. **Activate**: Enter the activation code in the verification input box to complete permanent verification

#### Permanent Activation Code Format:
```
FV + 18-character code
Example: FV1234567890ABCDEF12
```

> **Note**: Permanent activation codes must start with **FV**, otherwise they will be recognized as regular verification codes and consume verification counts

### 🛡️ Significance of Verification Mechanism

This verification mechanism aims to:
- ✅ Ensure legal and compliant software use
- ✅ Prevent malicious abuse and distribution
- ✅ Protect user privacy and data security
- ✅ Maintain healthy software ecosystem development

## 📖 User Guide

### Server Configuration

#### Basic Configuration
The server runs on port `5000` by default, which can be adjusted by modifying the configuration in `run.py`:

```python
# Server configuration
host = "0.0.0.0"  # Listen address
port = 5000       # Listen port
debug = False     # Recommended to turn off debug mode in production
```

#### Advanced Configuration

**Upload Limits**
```python
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB
```

**Auto Cleanup**
```python
app.config["AUTO_CLEANUP_ENABLED"] = True   # Enable auto cleanup
app.config["AUTO_CLEANUP_DAYS"] = 30        # Keep data for 30 days
app.config["AUTO_CLEANUP_INTERVAL"] = 24    # Clean every 24 hours
```

## 📋 Update Log

### v1.0.1 (2025-6-9)
- 🔧 **New Remote Auto-startup Management Feature**
  - Client supports remote enable/disable auto-startup
  - Web interface adds auto-startup control buttons (check, enable, disable)
  - Real-time display of auto-startup status (startup folder, registry, overall status)
  - Support for detailed status feedback and error handling
- ✨ **Optimized Client Initial Configuration Experience**
  - Simplified first-run wizard interface
  - Removed complex legal confirmation text input requirements
  - Changed to simple checkbox confirmation method
  - Improved user configuration convenience
- ⚙️ **New Client Settings Access Method**
  - Create "设置.txt" file in client directory to reopen settings interface
  - Convenient for users to modify server address and other configurations later
  - No need to reinstall to adjust client parameters

### v1.0.0 (2025-6-9)
- 🎉 Initial release
- 📸 Basic screenshot functionality
- 🎥 Screen recording functionality
- ⌨️ Keyboard logging functionality
- 🖥️ System information monitoring
- ✨ Added real-time monitoring functionality
- 🔧 Optimized data storage mechanism
- 🌐 Improved web interface design
- 🔐 Enhanced security verification
- ✨ Added permanent verification functionality

## 📄 License

This project is open sourced under the MIT License. See [LICENSE](LICENSE) file for details.

## ⚖️ Legal Disclaimer and Compliance Requirements

> **⚠️ Serious Legal Risk Warning**: This software involves device monitoring functions. You must understand the relevant legal risks before use!

### 📋 Relevant Legal Provisions

**Civil Code of the People's Republic of China Articles 1032 & 1033**
- Natural persons enjoy privacy rights, and no organization or individual may infringe upon others' privacy rights
- Prohibits photographing, voyeurism, eavesdropping, and publicizing others' private activities
- Prohibits processing others' private information

**Public Security Administration Punishment Law Article 42**
- Voyeurism, secretly photographing, eavesdropping, or spreading others' privacy shall be punished with detention of not more than 5 days or a fine of not more than 500 yuan
- In serious cases, detention of 5 to 10 days, with a possible fine of not more than 500 yuan

**Criminal Law Article 253-1**
- Violating national regulations to sell or provide citizens' personal information, if the circumstances are serious, shall be sentenced to fixed-term imprisonment of not more than 3 years or criminal detention
- Stealing or illegally obtaining citizens' personal information by other means shall be punished according to regulations

### ✅ Legal Use Scenarios

This software is **limited** to the following legal scenarios:
- 🏠 **Parental Supervision**: Monitoring minors' device usage
- 🏢 **Enterprise Management**: Monitoring enterprise-owned devices with explicit employee consent
- 🔧 **Device Maintenance**: IT administrators maintaining enterprise network devices
- 📚 **Academic Research**: Network security and system monitoring related academic research

### ❌ Strictly Prohibited Scenarios

**Absolutely prohibited** to use this software for:
- 🚫 Unauthorized monitoring of others' devices
- 🚫 Stealing others' personal information and privacy data
- 🚫 Commercial espionage and competitive intelligence gathering
- 🚫 Any illegal criminal activities

### 📝 Pre-use Confirmation Required

Before using this software, you must ensure:
1. ✅ Have **legal ownership** or **explicit authorization** of the monitored device
2. ✅ Have informed relevant personnel and obtained **written consent** (if applicable)
3. ✅ Usage purpose **complies with local laws and regulations**
4. ✅ Will not infringe upon any third party's **privacy rights** and **personal information rights**

### 🛡️ Disclaimer

- This project is **for technical learning and research use only**
- Developers are **not responsible for any misuse**
- Users must **bear all legal risks** arising from using this software
- Using this software indicates that you **fully understand and accept** the above legal risks
- If you disagree with the above terms, please **immediately stop using** and delete this software

> **💡 Recommendation**: It is strongly recommended to consult professional lawyers to ensure compliance before use in enterprise or institutional environments.

---

<div align="center">
  <p>If this project helps you, please give us a ⭐ Star!</p>
  <p>Made with ❤️ by ByteScope Team</p>
</div>
