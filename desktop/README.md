# Windows中文审稿安装版 v11.2

当前发布：墨镜猫浅色界面、主编完整报告、右上角阅卷式分数和自动稿面完播曲线。评分规则仍为v11，上游0.14.1；模型估计未用真实留存校准。所有新界面和本地模型/评分恢复功能进入本次EXE。

[详细使用教程](../docs/使用教程-v11.2.md) · [GitHub发布](https://github.com/vashzwingli/ai-counsel-review/releases/tag/review-v11.2)

构建使用全新路径：先在frontend运行 `npm ci` 与 `npm run build -- --outDir ../build/release-v11-2-web`。回到根目录，在打包进程中设置 `AI_COUNSEL_BUILD_FRONTEND=build/release-v11-2-web` 和 `AI_COUNSEL_BUILD_ICON=desktop/assets/yuanbao-ip/yuanbao-ip-cat.ico`，再运行 `pyinstaller --distpath build/frozen-v11-2-ip --workpath build/pyinstaller-v11-2-ip AICounselServer.spec`。需先安装PyInstaller。

运行 `python desktop/build_guide.py --out-dir build/release-v11-2-guide --pdf-output output/pdf/AI审稿团-v11.2-详细教程.pdf` 生成离线教程；PDF额外依赖ReportLab及Windows微软雅黑字体。再运行 `python desktop/package_windows.py --server-dir build/frozen-v11-2-ip/AICounselServer --frontend-dir build/release-v11-2-web --review-version 11 --release-label v11.2 --stage-tag v11-2-ip --icon desktop/assets/yuanbao-ip/yuanbao-ip-cat.ico --guide-dir build/release-v11-2-guide --installer-name AI审稿团-v11.2-最新版-Windows-x64-安装包.exe`。保留旧安装包，勿复用已有stage目录。

协议验证：`desktop/verify_v11_packaged_runtime.py --server <冻结或安装的服务EXE> --output <报告> --check-html`；安装验证：`desktop/verify_v11_installer.py --installer <EXE> --payload dist/payload-roles-v11-2-ip.zip --frontend-dir build/release-v11-2-web --release-label v11.2 --ip-release --report <报告>`。这些检查使用独立数据目录及本机模拟接口，不调用真实模型。

升级先停止原服务、关闭原启动器。程序默认安装在 `%LOCALAPPDATA%\Programs\AICounselReview`，个人数据保存在独立的 `%LOCALAPPDATA%\AICounselReview`，更新不覆盖自定义配置。默认3340端口，与源码服务不能同时占用。

