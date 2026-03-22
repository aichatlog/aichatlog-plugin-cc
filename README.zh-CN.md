# AIChatLog — Claude Code 插件

[English](README.md) | 简体中文

自动同步 Claude Code 对话到你的知识库。挂载到 Claude Code 的 Stop 事件，解析 JSONL 对话日志，按会话去重，并通过可配置的输出适配器同步。

## 安装

### pip（推荐）

> **注意：** macOS 上请使用 `pip3`。系统自带的 `pip` 可能指向已不受支持的 Python 2。

```bash
pip3 install git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code
```

如果看到脚本不在 PATH 中的警告：

```text
WARNING: The script aichatlog is installed in '/Users/you/Library/Python/3.x/bin' which is not on PATH.
```

将其添加到 shell 配置文件中：

```bash
# zsh（macOS 默认）
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 或者直接使用完整路径
python3 -m aichatlog.core install
```

然后注册 Claude Code hook：

```bash
aichatlog install
```

重启 Claude Code 即可生效。

### Claude Code 插件市场

```text
/plugin marketplace add https://github.com/aichatlog/aichatlog.git
```

然后从市场安装 **aichatlog**。

## 配置

```bash
aichatlog setup --adapter=fns --url=http://localhost:37240 --token=YOUR_TOKEN --vault=MyVault
```

适配器选项：

- `fns` — 通过 Fast Note Sync 同步到 Obsidian
- `local` — 写入本地 .md 文件
- `git` — 自动提交到 Git 仓库
- `server` — 推送到 aichatlog-server

## 命令

| 命令 | 说明 |
| --- | --- |
| `aichatlog setup` | 配置适配器和设置 |
| `aichatlog status` | 显示配置和同步统计 |
| `aichatlog run` | 手动同步最新对话 |
| `aichatlog export` | 批量同步所有对话 |
| `aichatlog test` | 测试适配器连接 |
| `aichatlog web` | 启动 Web 管理面板 |
| `aichatlog log` | 查看最近的同步日志 |
| `aichatlog ingest` | 手动导入所有 JSONL 文件 |

在 Claude Code 中使用 `/aichatlog:web` 打开管理面板。

## 同步协议

插件支持 v2 条件同步协议，大幅减少网络开销：

- **check 模式** — 仅发送元数据 (~500B)，服务器比对哈希后返回"未变化"或"需要全量"
- **delta 模式** — 仅发送新增消息，服务器追加到已有对话
- **full 模式** — 完整发送所有消息（首次同步或回退时）

## 元数据采集

插件自动从 Claude Code JSONL 中提取：

- AI 模型名称（如 `claude-opus-4-6`）
- 精确 UTC 时间戳（毫秒级）
- 每条消息的 Token 用量（input/output）
- Git 分支、入口（vscode/cli）、CC 版本
- 缓存 Token 统计

## 更新和卸载

```bash
# 更新
pip3 install --upgrade git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code

# 卸载
aichatlog uninstall   # 移除 hook
pip3 uninstall aichatlog-plugin
```
