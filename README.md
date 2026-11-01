# Plota

轻量的 Windows 科研绘图桌面工具。导入数据，选择图形与风格，导出图片和可独立运行的 Python 脚本。

**[下载 Windows 单文件版](https://github.com/alyahromagnoli-create/Plota/releases/latest)** · **[完整使用说明书](docs/USER_GUIDE.md)** · **[报告问题](https://github.com/alyahromagnoli-create/Plota/issues)**

![Plota](docs/images/editor.png)

## 直接使用

1. 在 Releases 下载 `Plota.exe`，放到可写的独立文件夹，双击运行。无需安装 Python、LaTeX 或 SciencePlots。
2. 将数据文件拖入首页白色框，或点击“选择文件”。
3. 选择 X 和一个或多个 Y，选择折线/散点，点击“添加图层”。
4. 在“图形”中设置坐标和多子图，在“页面”中选择画布比例、字体与风格，然后应用。
5. 点击“导出”，同时获得 PNG、PDF、SVG、plot.py、配置和数值快照。

面向 Windows 64 位；程序会在 EXE 旁创建 `Plota_files` 保存导入副本和缓存。软件未签名，下载后可对照 Release 中的 SHA256SUMS.txt 校验。已验证本机中文空格路径单文件移动运行，未承诺所有 Windows 版本或其他操作系统兼容。

## 功能

- Excel `.xlsx/.xlsm`、CSV/TXT/TSV、LAMMPS thermo `.out/.log`；支持多个文件导入。旧 `.xls` 需转换，`.data` 不支持。
- 折线、散点、线性/二次多项式拟合、二维数值矩阵热力图与等高线。
- 多子图、跨行跨列、共享轴、对数轴、坐标范围、图例和子图编号。
- 16:9、1:1、4:3 与自定义画布；毫米尺寸、DPI和字号可调。
- 内嵌 SciencePlots 的 Science、IEEE、Nature、Bright 配置，保留经典风格。无外部 TeX 依赖。
- 项目 JSON 加数据快照保存；独立脚本仅依赖 NumPy 和 Matplotlib。
- Tavotto 无参数 main 入口、静态输出文件名；PDF/SVG保留可编辑图元与文字。

![SciencePlots presets](docs/images/scienceplots-styles.png)

## 文件怎么分享

| 目的 | 分享内容 |
| --- | --- |
| 使用软件 | 单个 `Plota.exe` |
| 展示结果 | PNG、PDF 或 SVG |
| 继续编辑项目 | 项目 JSON 和对应数据文件夹 |
| 运行 Python 或交给 Tavotto | 完整导出包，不要只发 plot.py |

在 Tavotto 中拖入导出的 `plot.py`，并按提示选择其完整文件夹。兼容测试使用 Tavotto 0.19.2 官方源码引擎；输入兼容不等于符合目标期刊的字号、栏宽或分辨率要求。

## 文档和示例

- [完整中文说明书](docs/USER_GUIDE.md)：从下载、导入、图层与布局，到项目备份、独立运行和问题排查。
- [曲线练习](examples/curves.csv)、[矩阵练习](examples/matrix.csv)、[LAMMPS thermo 练习](examples/demo_thermo.out)：全部为合成数据。
- Word 和 PDF 说明书在 Releases 下载。
- [第三方说明](THIRD_PARTY_NOTICES.md)。

公开包不含个人 Excel、原始研究结果或运行缓存。分享自己的项目时，数据快照和来源路径可能包含个人信息，请自行检查。

## 源码运行

建议 Windows x64 + Python 3.12（含 Tcl/Tk）：

```powershell
git clone https://github.com/alyahromagnoli-create/Plota.git
cd Plota
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

测试和单文件构建：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

输出为 `release/Plota.exe`。修改 engine.py 后，构建脚本会同步 engine_source.txt，保证冻结版本可导出同一渲染引擎。仓库不包含虚拟环境、构建缓存、用户数据和 EXE；EXE 位于 Releases。

## 版本

v6.0.0 是 Plota v6 首个 GitHub 公开发行版，保留原有功能，将内置示例替换为合成数据，并补充说明与构建入口。拟合为普通最小二乘，不含置信区间；矩阵图按等间距索引绘制，不做散乱点插值。

本仓库公开提供源码供查看；未为 Plota 自有代码另行指定开源许可。第三方代码、样式与字体遵循其各自许可，SciencePlots MIT 许可随配置及每个导出包保留。
