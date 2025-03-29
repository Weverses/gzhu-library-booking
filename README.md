# 广州大学图书馆座位预约脚本

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-GPL3.0-green)

预约广州大学图书馆座位的Python脚本，孩子来图书馆随便写着玩的，不过等我打算开源的时候发现github原来已经有现成的实现了:D

## 功能特性

✅ 多账号管理系统  
✅ 可视化座位选择  
✅ 定时预约
✅ 预约结果二维码生成  
✅ 预约查询及签到

## 环境要求
- Python 3.8+
- 依赖安装：
```bash
pip install -r requirements.txt
```

## 快速开始

```bash
git clone https://github.com/yourusername/gzhu-library-booking.git
cd gzhu-library-booking
python library_booking.py
```

## 使用指南

1. **账号管理**
   - 支持添加/删除多个校园账号
   
2. **座位预约**
   - 支持普通房间和走廊区域选择
   - 自动查询大段时间内座位状态，列出空闲座位
   - 可视化显示各楼层座位分布
   - 自动切割预约时段为每4h一段，方便大段时间预约

3. **预约管理**
   - 生成预约二维码
   - 预约查询及签到

## 未实现的功能

1. 可视化Webui
2. Github Actions自动预约及签到
3. 你告诉我

## Eula
本项目仅供学习交流使用，不得用于商业用途。作者不对因使用本项目而导致的任何问题负任何责任。

## 开源协议

[GPL-3.0 License](LICENSE)