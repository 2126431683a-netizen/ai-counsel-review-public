using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class LocalApp {
    internal static readonly string Root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    internal static readonly string Data=Environment.GetEnvironmentVariable("AI_COUNSEL_DATA_DIR") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AICounselReview");
    internal static readonly string Port=Environment.GetEnvironmentVariable("AI_COUNSEL_PORT") ?? "3340";
    internal static readonly string Url="http://127.0.0.1:"+Port;
    internal static readonly string Server=Path.Combine(Root,"server","AICounselServer.exe");
    internal static readonly string Pid=Path.Combine(Data,"desktop-server.pid");
    [STAThread] static int Main(string[] args) {
        try {
            if(Array.IndexOf(args,"--smoke-test")>=0){Ensure().GetAwaiter().GetResult();File.WriteAllText(Path.Combine(Data,"launcher-check.json"),"{\"ready\":true,\"bundledPython\":true,\"url\":\""+Url+"\"}");return 0;}
            if(Array.IndexOf(args,"--stop")>=0){Stop();return 0;}
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new MainWindow());return 0;
        } catch(Exception e){Directory.CreateDirectory(Data);File.AppendAllText(Path.Combine(Data,"launcher-error.log"),DateTime.Now+" "+e+Environment.NewLine);if(Array.IndexOf(args,"--smoke-test")<0)MessageBox.Show(e.Message,"AI 审稿团");return 1;}
    }
    internal static bool Ready(){try{var req=(HttpWebRequest)WebRequest.Create(Url+"/api/health");req.Proxy=null;req.Timeout=1200;using(var response=req.GetResponse())using(var reader=new StreamReader(response.GetResponseStream()))return reader.ReadToEnd().Contains("The AI Counsel API");}catch{return false;}}
    internal static async Task Ensure(){
        Directory.CreateDirectory(Data);if(Ready())return;
        if(!File.Exists(Server))throw new FileNotFoundException("缺少内置服务文件，请重新安装。",Server);
        var info=new ProcessStartInfo(Server,"--port "+Port+" --data-dir \""+Data+"\""){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,WorkingDirectory=Root};
        var process=Process.Start(info);File.WriteAllText(Pid,process.Id+"|"+process.StartTime.ToUniversalTime().Ticks);
        for(int i=0;i<120;i++){await Task.Delay(500);if(Ready())return;if(process.HasExited)throw new Exception("服务未能启动。请查看数据目录中的 server.log。");}
        throw new Exception("启动等待超时。可稍后点击打开工作台，或查看 server.log。");
    }
    internal static void Stop(){
        if(!File.Exists(Pid))return;var parts=File.ReadAllText(Pid).Split('|');int id;
        if(parts.Length!=2||!int.TryParse(parts[0],out id))return;
        try{var process=Process.GetProcessById(id);if(process.StartTime.ToUniversalTime().Ticks.ToString()!=parts[1])return;
            if(!String.Equals(process.MainModule.FileName,Server,StringComparison.OrdinalIgnoreCase))return;process.Kill();process.WaitForExit(10000);
        }catch(ArgumentException){}File.Delete(Pid);
    }
    internal static void Open(string value){Process.Start(new ProcessStartInfo(value){UseShellExecute=true});}
}
internal class MainWindow:Form {
    Label status;Button launch,api,stop;
    internal MainWindow(){
        Text="AI 审稿团 "+ReleaseInfo.Version+" · Git源宝审稿室";ClientSize=new Size(552,330);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft YaHei UI",10F);
        BackColor=Color.FromArgb(255,253,245);Icon=System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        var mascot=Path.Combine(LocalApp.Root,"assets","yuanbao-ip","yuanbao-ip-cat-master.png");
        if(File.Exists(mascot))Controls.Add(new PictureBox{Image=Image.FromFile(mascot),SizeMode=PictureBoxSizeMode.Zoom,Left=24,Top=14,Width=84,Height=84});
        Controls.Add(new Label{Text="AI 审稿团 "+ReleaseInfo.Version,Font=new Font(Font.FontFamily,21F,FontStyle.Bold),AutoSize=true,Left=120,Top=25});
        Controls.Add(new Label{Text="小猫陪你读稿，把意见讲清楚。",AutoSize=true,Left=123,Top=71});
        status=new Label{Text="就绪，点击启动后在浏览器中使用。",Left=30,Top=116,Width=490,Height=32};Controls.Add(status);
        launch=Add("启动并打开",30,161,async()=>await Start(false));api=Add("配置模型 / API",280,161,async()=>await Start(true));
        Add("详细教程",30,212,()=>{var guide=Path.Combine(LocalApp.Root,"详细教程","使用教程.html");LocalApp.Open(File.Exists(guide)?guide:Path.Combine(LocalApp.Root,"使用说明.txt"));});Add("打开数据目录",280,212,()=>{Directory.CreateDirectory(LocalApp.Data);LocalApp.Open(LocalApp.Data);});
        stop=Add("停止本机服务",30,263,()=>{LocalApp.Stop();status.Text="本机服务已停止；设置和审稿记录已保留。";});
        Controls.Add(new Label{Text=LocalApp.Url,Left=280,Top=272,Width=240,Height=28});
    }
    Button Add(string text,int x,int y,Action action){var b=new Button{Text=text,Left=x,Top=y,Width=235,Height=39};b.Click+=(s,e)=>{try{action();}catch(Exception ex){MessageBox.Show(ex.Message,Text);}};Controls.Add(b);return b;}
    async Task Start(bool settings){launch.Enabled=api.Enabled=stop.Enabled=false;status.Text="正在启动内置环境，请稍候…";try{await LocalApp.Ensure();status.Text="已启动。无需登录，在浏览器中配置模型后即可审稿。";LocalApp.Open(LocalApp.Url+(settings?"/?settings=1":"/"));}catch(Exception e){status.Text="启动失败，请查看日志。";MessageBox.Show(e.Message,Text);}finally{launch.Enabled=api.Enabled=stop.Enabled=true;}}
}
