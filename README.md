# 小度 × Home Assistant 双向集成

将百度小度（DuerOS）智能家居生态与 Home Assistant 打通，实现双向设备控制。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                       Home Assistant                     │
│                                                          │
│  ┌──────────────┐              ┌───────────────────┐    │
│  │   xiaodu      │              │ dueros_smarthome   │    │
│  │  (小度→HA)    │              │   (HA→小度)        │    │
│  │              │              │                   │    │
│  │ BDUSS Cookie │              │ OAuth2 + DuerOS   │    │
│  │ Web API 轮询  │              │ ConnectedHome     │    │
│  └──────┬───────┘              └────────┬──────────┘    │
│         │                               │               │
│         │  蓝牙Mesh开关                  │  三方设备      │
│         │  空调/灯/窗帘...               │  Zigbee/WiFi   │
└─────────┼───────────────────────────────┼───────────────┘
          │                               │
          ▼                               ▼
   ┌──────────────┐              ┌──────────────────┐
   │  小度中控屏    │              │  DuerOS 语音控制   │
   │  蓝牙Mesh设备  │              │  "小度小度，开灯"   │
   └──────────────┘              └──────────────────┘
```

## 组件一：xiaodu（小度设备 → HA）

把小度生态里的设备拉到 Home Assistant 中控制。

### 支持设备

| 小度设备类型 | HA 实体 | 功能 |
|------------|---------|------|
| SWITCH（开关） | Switch | 开/关 |
| SOCKET（插座） | Switch | 开/关 |
| LIGHT（灯） | Light | 开/关、亮度、色温、模式 |
| CURTAIN（窗帘） | Cover | 开/关/停 |
| AIR_CONDITION（空调） | Climate | 开/关、模式、温度 |
| CLOTHES_RACK（晾衣架） | Switch × N | 多面板控制 |
| HEATER（取暖器） | Switch | 开/关 |
| WASHING_MACHINE（洗衣机） | Switch | 开/关 |
| WINDOW_OPENER（推拉窗） | Switch | 开/关 |
| DOOR_LOCK（门锁） | Lock | 锁/开 |

### 安装

#### 方式一：手动安装

```bash
# 复制到 HA 配置目录
cp -r custom_components/xiaodu <你的HA配置目录>/custom_components/
```

#### 方式二：HACS

1. HACS → 集成 → 右上角三点 → 自定义存储库
2. 输入仓库地址，类型选 Integration
3. 下载安装

### 配置

1. **重启 Home Assistant**
2. **设置 → 设备与服务 → 添加集成 → 搜索"小度智能家居"**

#### 获取 BDUSS Cookie

> BDUSS 是百度账号的长期令牌，约 6 个月过期一次。

1. 浏览器打开 [小度智能家居网页版](https://xiaodu.baidu.com/saiya/smarthome/index.html)
2. **F12** 打开开发者工具
3. **切换到手机模式**（重要！PC 模式可能拿不到正确的 Cookie）
4. 刷新页面，登录百度账号
5. 切换到 **Application**（应用程序）标签
6. 左侧 Cookies → `xiaodu.baidu.com`
7. 找到 **BDUSS**，复制它的值

![Cookie获取示意](https://xiaodu.baidu.com/saiya/smarthome/index.html)

#### 配置流程

```
输入 BDUSS → 选择家庭 → 勾选设备 → 完成
```

### 更新 Cookie

BDUSS 过期后（约6个月），在集成配置页面可以直接更新，无需删除重建：

**设置 → 设备与服务 → 小度智能家居 → 选项 → 更新 BDUSS**

### 语音命令示例

配置完成后，你可以通过小度语音控制 HA 里的设备：

- "小度小度，打开客厅灯"
- "小度小度，把灯调到50%"
- "小度小度，空调调到26度"
- "小度小度，打开窗帘"

> ⚠️ 注意：请勿在厂商 APP 中直接操作设备，小度不会从厂商 APP 同步最新状态到 HA。

---

## 组件二：dueros_smarthome（HA 设备 → 小度）

把 Home Assistant 里的三方设备暴露给小度语音控制。

### 前提条件

- Home Assistant 能被**公网 HTTPS** 访问
- 有百度 DuerOS 开发者账号

### 支持设备

| HA 设备类型 | DuerOS 类型 | 语音命令示例 |
|------------|------------|------------|
| light | LIGHT | "小度小度，打开灯" |
| switch / input_boolean | SWITCH | "小度小度，打开开关" |
| fan | FAN | "小度小度，风扇调到最大" |
| cover | CURTAIN | "小度小度，打开窗帘" |
| climate | AIR_CONDITION | "小度小度，空调调到26度" |
| humidifier | HUMIDIFIER | "小度小度，加湿器调到50%" |
| scene / automation | SCENE_TRIGGER | "小度小度，执行回家模式" |
| sensor | SENSOR | "小度小度，客厅温度多少" |

### 安装

```bash
cp -r custom_components/dueros_smarthome <你的HA配置目录>/custom_components/
```

### 配置

#### 1. HA 端

重启 HA → 添加集成 → 搜索 "DuerOS Smart Home" → 输入 Client ID 和 Client Secret（自定义）。

#### 2. 确保 HA 公网可访问

##### 方案一：Nginx 反向代理 + Let's Encrypt

```nginx
server {
    listen 443 ssl http2;
    server_name ha.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/ha.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ha.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8123;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

##### 方案二：Cloudflare Tunnel

```bash
cloudflared tunnel create ha-tunnel
cloudflared tunnel route dns ha-tunnel ha.yourdomain.com
```

配置文件 `~/.cloudflared/config.yml`：

```yaml
tunnel: <tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: ha.yourdomain.com
    service: http://localhost:8123
  - service: http_status:404
```

#### 3. DuerOS 开放平台

1. 打开 [DuerOS 智能家居控制台](https://dueros.baidu.com/openiot/html/iot/iot.html#/cloud/console)
2. 创建**云云接入**技能
3. 配置 OAuth2：

| 配置项 | 值 |
|--------|-----|
| Client ID | 你在 HA 中配置的值 |
| Client Secret | 你在 HA 中配置的值 |
| Authorization URL | `https://ha.yourdomain.com/auth/dueros/authorize` |
| Token URL | `https://ha.yourdomain.com/auth/dueros/token` |

4. 配置设备云接口：

| 配置项 | 值 |
|--------|-----|
| 接口地址 | `https://ha.yourdomain.com/api/dueros/smarthome` |

5. 测试 → 用小度 APP 扫码授权 → "小度小度，发现设备"

---

## 常见问题

### xiaodu 组件

**Q: BDUSS 多久过期？**
A: 约 6 个月。过期后 HA 日志会报错，在集成选项里更新即可。

**Q: 设备状态不同步？**
A: 默认 30 秒轮询一次。如果在厂商 APP 里操作了设备，小度不会同步状态，HA 也就拿不到最新状态。请通过 HA 或小度语音操作。

**Q: 新增了设备怎么办？**
A: 在集成选项里重新配置，或者删除重建。

### dueros_smarthome 组件

**Q: 授权失败？**
A: 确认 HA 能被公网 HTTPS 访问，Authorization URL 和 Token URL 可以从外网打开。

**Q: 设备发现为空？**
A: 确认 HA 中有非 `unavailable` 状态的可控设备。

**Q: 语音控制没反应？**
A: 在 DuerOS 控制台重新测试接口，检查 token 是否过期。

---

## 日志调试

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.xiaodu: debug
    custom_components.dueros_smarthome: debug
```

---

## 技术栈

- **xiaodu 组件**: BDUSS Cookie 认证 → xiaodu.baidu.com Web API → Coordinator 模式轮询
- **dueros_smarthome 组件**: OAuth2 授权 → DuerOS ConnectedHome 协议 → HA 服务调用

## License

MIT
