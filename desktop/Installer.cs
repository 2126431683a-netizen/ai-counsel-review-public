using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Setup {
    internal const string Marker=".ai-counsel-review-install";
    internal static readonly string Default=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","AICounselReview");
    internal const string RegistryKey="Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AICounselReview";
    [STAThread] static int Main(string[] args){
        try{
            if(Array.IndexOf(args,"--verify")>=0){Verify();return 0;}
            if(Array.IndexOf(args,"--silent")>=0){var index=Array.IndexOf(args,"--dir");Install(index>=0?args[index+1]:Default,Array.IndexOf(args,"--no-shortcuts")<0,null);return 0;}
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new InstallWindow());return 0;
        }catch(Exception e){File.WriteAllText(Path.Combine(Path.GetTempPath(),"AI-Counsel-install-error.log"),e.ToString());if(Array.IndexOf(args,"--silent")<0)MessageBox.Show(e.Message,"AI 审稿团安装");return 1;}
    }
    static void Verify(){using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))using(var sha=SHA256.Create())if(BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant()!=PayloadInfo.Hash)throw new Exception("安装包校验失败，请重新获取。");}
    internal static void Install(string destination,bool shortcuts,Action<int> progress){
        Verify();var root=Path.GetFullPath(destination).TrimEnd('\\');
        if(root.Length<12||Directory.GetParent(root)==null)throw new Exception("请选择独立的程序文件夹。");
        if(Directory.Exists(root)&&Directory.GetFileSystemEntries(root).Length>0&&!File.Exists(Path.Combine(root,Marker)))throw new Exception("所选目录不为空，请选择空目录或原安装目录。");
        foreach(var p in Process.GetProcessesByName("AI审稿团")){try{if(String.Equals(p.MainModule.FileName,Path.Combine(root,"AI审稿团.exe"),StringComparison.OrdinalIgnoreCase))throw new IOException("请先在审稿团窗口选择“文件 → 完全退出”，再更新安装。");}catch(System.ComponentModel.Win32Exception){}}
        if(File.Exists(Path.Combine(root,Marker))){foreach(var p in Process.GetProcessesByName("AICounselServer")){try{if(String.Equals(p.MainModule.FileName,Path.Combine(root,"server","AICounselServer.exe"),StringComparison.OrdinalIgnoreCase))throw new IOException("请先在启动器中停止服务，再更新安装。");}catch(System.ComponentModel.Win32Exception){}}}
        Directory.CreateDirectory(root);
        using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))using(var zip=new ZipArchive(stream,ZipArchiveMode.Read)){
            int n=0;foreach(var item in zip.Entries){var target=Path.GetFullPath(Path.Combine(root,item.FullName.Replace('/','\\')));
                if(!target.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase))throw new Exception("安装包路径校验失败。");
                if(item.FullName.EndsWith("/")){Directory.CreateDirectory(target);continue;}
                Directory.CreateDirectory(Path.GetDirectoryName(target));using(var source=item.Open())using(var file=new FileStream(target,FileMode.Create,FileAccess.Write))source.CopyTo(file);
                n++;if(progress!=null)progress(n*100/zip.Entries.Count);
            }
        }
        File.WriteAllText(Path.Combine(root,Marker),"ai-counsel-review-v1");
        if(shortcuts){
            var desktop=Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);var menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"AI 审稿团");Directory.CreateDirectory(menu);
            CreateShortcut(Path.Combine(desktop,"AI 审稿团.lnk"),root);CreateShortcut(Path.Combine(menu,"AI 审稿团.lnk"),root);
            using(var key=Registry.CurrentUser.CreateSubKey(RegistryKey)){key.SetValue("DisplayName","AI 审稿团 "+PayloadInfo.Version+" · The AI Counsel");key.SetValue("DisplayVersion","0.14.1-review."+PayloadInfo.Version);key.SetValue("Publisher","The AI Counsel community / 本地中文配置");key.SetValue("InstallLocation",root);key.SetValue("DisplayIcon",Path.Combine(root,"AI审稿团.exe"));key.SetValue("UninstallString","\""+Path.Combine(root,"卸载AI审稿团.exe")+"\"");key.SetValue("NoModify",1);key.SetValue("NoRepair",1);}
        }
    }
    static void CreateShortcut(string link,string root){dynamic shell=Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));dynamic shortcut=shell.CreateShortcut(link);shortcut.TargetPath=Path.Combine(root,"AI审稿团.exe");shortcut.IconLocation=Path.Combine(root,"AI审稿团.exe")+",0";shortcut.WorkingDirectory=root;shortcut.Description="小猫审稿员 · 自定义评审团、本地模型与自定义API";shortcut.Save();}
}
internal class InstallWindow:Form {
    TextBox folder;Button install,browse;ProgressBar bar;Label status;CheckBox open;
    internal InstallWindow(){
        Text="安装 AI 审稿团 "+PayloadInfo.Version;ClientSize=new Size(590,340);Font=new Font("Microsoft YaHei UI",10F);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
        BackColor=Color.FromArgb(255,253,245);Icon=System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        Controls.Add(new Label{Text="AI 审稿团 "+PayloadInfo.Version,Left=28,Top=24,AutoSize=true,Font=new Font(Font.FontFamily,24F,FontStyle.Bold)});
        Controls.Add(new Label{Text="内置运行环境 · 简体中文 · 自定义角色与 API",Left=30,Top=79,Width=535,Height=28});
        Controls.Add(new Label{Text="安装位置（当前用户，无需管理员权限）",Left=30,Top=118,Width=510});
        folder=new TextBox{Text=Setup.Default,Left=30,Top=148,Width=435};Controls.Add(folder);
        browse=new Button{Text="浏览",Left=476,Top=145,Width=80,Height=32};browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog()){dialog.Description="选择独立的程序目录";if(dialog.ShowDialog()==DialogResult.OK)folder.Text=dialog.SelectedPath;}};Controls.Add(browse);
        open=new CheckBox{Text="安装完成后打开审稿团",Checked=true,Left=30,Top=190,Width=300};Controls.Add(open);
        status=new Label{Text="模型与密钥可在安装后填写。",Left=30,Top=229,Width=525};Controls.Add(status);
        bar=new ProgressBar{Left=30,Top=261,Width=525,Height=18};Controls.Add(bar);
        install=new Button{Text="安装",Left=416,Top=292,Width=140,Height=34};install.Click+=async(s,e)=>await Run();Controls.Add(install);
    }
    async Task Run(){install.Enabled=browse.Enabled=folder.Enabled=false;status.Text="正在校验并安装，请稍候…";try{string target=folder.Text;await Task.Run(()=>Setup.Install(target,true,value=>BeginInvoke((Action)(()=>bar.Value=value))));bar.Value=100;status.Text="安装完成。";if(open.Checked)Process.Start(new ProcessStartInfo(Path.Combine(target,"AI审稿团.exe")){UseShellExecute=true});MessageBox.Show("安装完成。双击桌面的“AI 审稿团”即可使用。",Text);Close();}catch(Exception e){MessageBox.Show(e.Message,Text);install.Enabled=browse.Enabled=folder.Enabled=true;}}
}
