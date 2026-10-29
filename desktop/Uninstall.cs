using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Uninstall {
    [STAThread] static int Main(string[] args){
        try{
            Application.EnableVisualStyles();
            if(args.Length==2&&args[0]=="--remove"){
                var root=Path.GetFullPath(args[1]).TrimEnd('\\');var marker=Path.Combine(root,".ai-counsel-review-install");
                if(root.Length<12||!File.Exists(marker)||File.ReadAllText(marker)!="ai-counsel-review-v1"||!File.Exists(Path.Combine(root,"AI审稿团.exe")))throw new Exception("安装目录校验失败，未删除任何文件。");
                System.Threading.Thread.Sleep(1200);
                foreach(var p in Process.GetProcessesByName("AICounselServer")){try{if(String.Equals(p.MainModule.FileName,Path.Combine(root,"server","AICounselServer.exe"),StringComparison.OrdinalIgnoreCase))throw new IOException("服务仍在运行，请先在启动器中停止服务。");}catch(System.ComponentModel.Win32Exception){}}
                Directory.Delete(root,true);
                var desktop=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"AI 审稿团.lnk");if(File.Exists(desktop))File.Delete(desktop);
                var menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"AI 审稿团");if(Directory.Exists(menu))Directory.Delete(menu,true);
                Registry.CurrentUser.DeleteSubKeyTree("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AICounselReview",false);
                MessageBox.Show("程序已卸载。审稿记录、角色、设置与凭据保留在本机数据目录中。","AI 审稿团");return 0;
            }
            if(MessageBox.Show("卸载 AI 审稿团？请先在启动器中停止服务并关闭启动器。\n对话、角色、设置与凭据会保留。","卸载 AI 审稿团",MessageBoxButtons.YesNo)!=DialogResult.Yes)return 0;
            var source=System.Reflection.Assembly.GetExecutingAssembly().Location;var directory=Path.GetDirectoryName(source);var temp=Path.Combine(Path.GetTempPath(),"AICounsel-uninstall-"+Guid.NewGuid().ToString("N")+".exe");File.Copy(source,temp);Process.Start(new ProcessStartInfo(temp,"--remove \""+directory+"\""){UseShellExecute=false,CreateNoWindow=true});return 0;
        }catch(Exception e){MessageBox.Show(e.Message,"卸载未完成");return 1;}
    }
}
