"""Package the frozen server, Chinese launcher and verified ZIP installer."""

import hashlib
import argparse
import re
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import platform
import zipfile

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--api-fix", action="store_true")
parser.add_argument("--stage-tag", default="")
parser.add_argument("--server-dir", type=Path, default=root / "dist/AICounselServer")
parser.add_argument("--review-version", type=int)
parser.add_argument("--release-label", default="", help="Distribution label; independent of the scoring rule version.")
parser.add_argument("--installer-name", default="", help="Fresh EXE basename to preserve earlier releases.")
parser.add_argument("--frontend-dir", type=Path, default=root / "frontend/dist")
parser.add_argument("--icon", type=Path, default=root / "desktop/assets/review-cat.ico")
parser.add_argument("--guide-dir", type=Path, help="Offline tutorial directory included in the installer.")
parser.add_argument("--desktop-sdk", type=Path, help="Extracted official Microsoft.Web.WebView2 NuGet SDK; builds the independent Windows window.")
parser.add_argument("--desktop-runtime", type=Path, help="Official Microsoft-signed Evergreen bootstrapper for machines missing WebView2.")
args = parser.parse_args()
bundle = json.loads((root/"desktop/role_bundle.json").read_text(encoding="utf-8"))
release_label = args.release_label or 'v'+str(bundle.get('version',1))
if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,39}', release_label):
    raise SystemExit('Invalid release label.')
suffix = "api-fix" if args.api_fix else "roles"
if args.stage_tag:
    if not re.fullmatch(r"[a-z0-9-]+", args.stage_tag):
        raise SystemExit("Stage tag must contain only lowercase letters, numbers and hyphens.")
    suffix += "-" + args.stage_tag
stage = root / "dist" / ("WindowsApp-" + suffix)
installer = root / (f"dist/AI审稿团-v{args.review_version}-Windows-x64-安装包.exe" if args.review_version else "dist/AI审稿团-接口修复版-Windows-x64-安装包.exe" if args.api_fix else "dist/AI审稿团-五类观众与主编-Windows-x64-安装包.exe")
if args.installer_name:
    if Path(args.installer_name).name != args.installer_name or not args.installer_name.lower().endswith('.exe'):
        raise SystemExit('Installer name must be an EXE basename.')
    installer = root/'dist'/args.installer_name
if installer.exists() and args.review_version:
    raise SystemExit("Release installer already exists; preserve it and choose a fresh release.")
if stage.exists():
    raise SystemExit("WindowsApp already exists. Use a fresh staging path rather than overwriting it.")
stage.mkdir(parents=True)
shutil.copytree(args.server_dir, stage / "server")
shutil.copytree(args.frontend_dir, stage / "server/_internal/frontend/dist", dirs_exist_ok=True)
shutil.copy2(root/'desktop/role_bundle.json', stage/'server/_internal/desktop/role_bundle.json')
if args.desktop_runtime:
    (stage/'runtime').mkdir()
    shutil.copy2(args.desktop_runtime, stage/'runtime/MicrosoftEdgeWebview2Setup.exe')
if args.icon.exists():
    shutil.copytree(root/'desktop/assets',stage/'assets')
release_source=root/'build'/('release-info-'+suffix+'.cs')
release_source.parent.mkdir(parents=True,exist_ok=True)
release_source.write_text('[assembly:System.Reflection.AssemblyTitle("AI 审稿团")]\n[assembly:System.Reflection.AssemblyProduct("AI 审稿团") ]\n[assembly:System.Reflection.AssemblyVersion("0.14.1.0")]\n[assembly:System.Reflection.AssemblyInformationalVersion("'+release_label+'")]\ninternal static class ReleaseInfo { internal const string Version="'+release_label+'"; }',encoding='utf-8')
csc = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
for name, source in [("AI审稿团.exe", "Launcher.cs"), ("卸载AI审稿团.exe", "Uninstall.cs")]:
    if args.desktop_sdk and source == "Launcher.cs":
        source = "DesktopApp.cs"
    command=[str(csc), "/nologo", "/target:winexe", "/platform:x64", "/win32manifest:"+str(root/"desktop/app.manifest"),
             "/reference:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll", "/out:"+str(stage/name), str(root/"desktop"/source),str(release_source)]
    if args.icon.exists():command.append('/win32icon:'+str(args.icon))
    if args.desktop_sdk and source == "DesktopApp.cs":
        sdk = args.desktop_sdk
        for dll in ['Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll']:
            shutil.copy2(sdk/'lib/net462'/dll, stage/dll)
            command.append('/reference:'+str(stage/dll))
        shutil.copy2(sdk/'runtimes/win-x64/native/WebView2Loader.dll', stage/'WebView2Loader.dll')
        command.append('/reference:System.Web.Extensions.dll')
    subprocess.run(command,check=True)
shutil.copy2(root / "desktop/使用说明.txt", stage / "使用说明.txt")
if args.guide_dir:
    if not (args.guide_dir/'使用教程.html').is_file():
        raise SystemExit('Offline tutorial is missing 使用教程.html')
    shutil.copytree(args.guide_dir,stage/'详细教程')
licenses = stage / "licenses"
licenses.mkdir()
if args.desktop_sdk:
    shutil.copy2(args.desktop_sdk/'LICENSE.txt', licenses/'Microsoft-WebView2-LICENSE.txt')
shutil.copy2(root / "LICENSE", licenses / "The-AI-Counsel-MIT.txt")
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists():
    shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
inventory = []
for distribution in importlib.metadata.distributions():
    name = distribution.metadata["Name"]
    inventory.append({"name": name, "version": distribution.version, "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License", "See included license files")})
    for file in distribution.files or []:
        if not any(part.lower() in ("licenses", "license", "copying", "license.txt", "license.md", "notice") for part in file.parts):
            continue
        source = Path(distribution.locate_file(file))
        if source.is_file():
            target = licenses / name / str(file).replace("../", "").replace("..\\", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
(licenses / "dependency-inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
bundle = json.loads((root/"desktop/role_bundle.json").read_text(encoding="utf-8"))
if args.review_version:
    assert bundle['version'] == args.review_version
    assert json.loads((stage/"server/_internal/desktop/role_bundle.json").read_text(encoding="utf-8")) == bundle
    shutil.copytree(root/f"desktop/role-guides-v{args.review_version}", stage/f"角色说明-v{args.review_version}")
    shutil.copy2(root/"desktop/role_bundle.json", stage/f"角色说明-v{args.review_version}/角色配置.json")
(stage / "build-info.json").write_text(json.dumps({"project": "The AI Counsel", "upstreamVersion": "0.14.1", "upstreamCommit": commit, "localBuild": "2026-10-18-review-"+release_label, "releaseLabel":release_label,"reviewVersion":bundle.get('version',1), "roleBundleSHA256":hashlib.sha256((root/"desktop/role_bundle.json").read_bytes()).hexdigest(), "bundledPython": platform.python_version(), "port": 3340, "modelWeightsIncluded": False, "apiKeysIncluded": False, "profileIncluded": False, "userAuthorizedRolePromptsIncluded": True,"interface":"windows-webview2" if args.desktop_sdk else "browser-launcher"}, indent=2), encoding="utf-8")
for item in stage.rglob("*"):
    if item.name in ("credentials.json", "settings.json", "custom_personas.json", ".env"):
        raise RuntimeError("Unexpected profile/secret file in package: " + str(item))
archive = root / ("dist/payload-" + suffix + ".zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
    for file in sorted(stage.rglob("*")):
        if file.is_file():
            zipped.write(file, file.relative_to(stage).as_posix())
digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
(root / "desktop/PayloadInfo.cs").write_text('internal static class PayloadInfo { internal const string Hash="' + digest + '"; internal const string Version="'+release_label+'"; }', encoding="utf-8")
command = [str(csc), "/nologo", "/target:winexe", "/platform:x64", "/win32manifest:" + str(root / "desktop/app.manifest"),
           "/reference:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll,System.IO.Compression.dll,Microsoft.CSharp.dll",
           "/resource:" + str(archive) + ",payload.zip", "/out:" + str(installer), str(root / "desktop/Installer.cs"), str(root / "desktop/PayloadInfo.cs"),str(release_source)]
if args.icon.exists():command.append('/win32icon:'+str(args.icon))
subprocess.run(command, cwd=root, check=True)
hash_value = hashlib.file_digest(installer.open("rb"), "sha256").hexdigest()
Path(str(installer) + ".sha256").write_text(hash_value + "  " + installer.name + "\n", encoding="utf-8")
subprocess.run([str(installer), "--verify"], check=True)
shutil.copy2(root / "desktop/使用说明.txt", root / "dist/使用说明.txt")
print(json.dumps({"installer": str(installer), "bytes": installer.stat().st_size, "sha256": hash_value, "upstreamCommit": commit}, ensure_ascii=False))
