---
id: bugfix-config-command-allowlist
type: bugfix
title: 配置环境变量失效与绝对路径白名单降级
status: fixed
severity: high
scope: [backend, security]
modules: [config, safety, launcher]
tags: [config, allowlist, path]
symptoms:
  - COMPUTER_USE_CONFIG 不生效
  - 绝对路径白名单允许其他目录的同名程序
related_files:
  - computer_use/config.py
  - computer_use/safety.py
  - tests/test_config.py
  - tests/test_safety.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_config.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_safety.py tests/test_launcher.py -v
created_at: 2026-06-15
updated_at: 2026-06-15
---

# 配置环境变量失效与绝对路径白名单降级

## 现在的行为

修复前环境变量指定的配置文件未被读取；带路径的白名单项还会隐式加入 basename，导致其他目录同名程序通过校验。

## 预期的行为

显式参数、环境变量、默认配置依次生效；路径白名单只匹配完整路径，裸文件名才按名称匹配。

## 复现方式

设置 `COMPUTER_USE_CONFIG` 指向带特殊配置的 YAML，或将 `C:/Safe/app.exe` 加入白名单后检查 `D:/Other/app.exe`。

## 原因是什么

`load_config` 未读取环境变量；白名单归一化同时保存了完整路径和 basename。

## 怎么修复的

补充配置路径优先级，并按白名单项是否含路径分隔符区分完整路径匹配与 basename 匹配。

## 验证结果

配置、安全和启动器回归测试已通过。

## 风险和后续

配置仍按进程缓存；运行时修改环境变量后需要重启服务或显式清缓存。
