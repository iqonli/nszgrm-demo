# NSZGRM Demo

独立静态网页，浏览器加载 FP32 和 INT8/16 JSON 模型进行推理。

## Render 部署

本仓库仅保存页面、原始模型压缩包和部署脚本。Render 在构建阶段从 model/ 提取 JSON，
不使用 GitHub Actions 来连接 Render，也不会把解压后的文件提交回 GitHub。

在 Render 中新建 Static Site，连接 iqonli/nszgrm-demo（main），填写：

| 配置 | 内容 |
| --- | --- |
| Root Directory | 留空（仓库根目录） |
| Build Command | bash build.sh |
| Publish Directory | public |

也可以通过 Blueprint 读取根目录的 render.yaml。

构建脚本递归扫描 model/。优先复制独立 JSON；再读取 ZIP、7z、RAR、TAR、TAR.GZ、
TAR.XZ、TAR.BZ2、TAR.ZST 等 GNU tar 支持的格式与嵌套压缩包。
提取出的所有 JSON 扁平化放到 public/ 与 index.html 同级。
遇到同名文件直接跳过，不覆盖、不重命名。脚本要求 models_int8.json 与 models_fp32.json 都存在。

当前模型包：model/2model-2026-11-17.7z。
原有 .github/workflows/package-models.yml 不修改，且不负责部署 Render。

部署后可直接访问 /models_int8.json 和 /models_fp32.json 验证文件。

本地 Linux 构建：先运行 bash build.sh，再运行 python3 -m http.server 8000 --directory public。
