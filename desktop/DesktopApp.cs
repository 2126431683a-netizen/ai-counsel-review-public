using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal static class DesktopService {
    internal static readonly string Root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    internal static readonly string Data=Environment.GetEnvironmentVariable("AI_COUNSEL_DATA_DIR") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AICounselReview");
    internal static readonly string Port=Environment.GetEnvironmentVariable("AI_COUNSEL_PORT") ?? "3340";
    internal static readonly string Server=Path.Combine(Root,"server","AICounselServer.exe");
    internal static readonly string Pid=Path.Combine(Data,"desktop-server.pid");
    internal static readonly string Url="http://127.0.0.1:"+Port;
    internal static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    internal static bool Ready(){try{var req=(HttpWebRequest)WebRequest.Create(Url+"/api/health");req.Proxy=null;req.Timeout=1200;using(var response=req.GetResponse())using(var reader=new StreamReader(response.GetResponseStream()))return reader.ReadToEnd().Contains("The AI Counsel API");}catch{return false;}}
    internal static async Task Ensure(){
        int port;if(!int.TryParse(Port,out port)||port<1024||port>65535)throw new Exception("本机服务端口设置无效。");
        Directory.CreateDirectory(Data);if(Ready())return;
        if(!File.Exists(Server))throw new FileNotFoundException("缺少内置审稿服务，请重新安装桌面版。",Server);
        var info=new ProcessStartInfo(Server,"--port "+Port+" --data-dir \""+Data+"\""){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,WorkingDirectory=Root};
        var process=Process.Start(info);File.WriteAllText(Pid,process.Id+"|"+process.StartTime.ToUniversalTime().Ticks);
        for(int i=0;i<160;i++){await Task.Delay(500);if(Ready())return;if(process.HasExited)throw new Exception("本机审稿服务未能启动，请查看数据目录中的 server.log。");}
        throw new Exception("启动等待超时。请稍后重试，或在数据目录查看 server.log。");
    }
    internal static void Stop(){
        if(!File.Exists(Pid))return;var parts=File.ReadAllText(Pid).Split('|');int id;
        if(parts.Length!=2||!int.TryParse(parts[0],out id))return;
        try{var process=Process.GetProcessById(id);if(process.StartTime.ToUniversalTime().Ticks.ToString()!=parts[1])return;
            if(!String.Equals(process.MainModule.FileName,Server,StringComparison.OrdinalIgnoreCase))return;process.Kill();process.WaitForExit(10000);
        }catch(ArgumentException){}File.Delete(Pid);
    }
    internal static void WriteStatus(string stage,string runtime){
        Directory.CreateDirectory(Data);
        File.WriteAllText(Path.Combine(Data,"desktop-status.json"),Json.Serialize(new {version=ReleaseInfo.Version,mode="windows-desktop",stage=stage,runtime=runtime,pid=Process.GetCurrentProcess().Id,time=DateTime.UtcNow.ToString("o")}),Encoding.UTF8);
    }
    internal static void OpenExternal(string value){Process.Start(new ProcessStartInfo(value){UseShellExecute=true});}
}

internal static class DesktopProgram {
    [STAThread] static int Main(string[] args){
        try{
            if(Array.IndexOf(args,"--stop")>=0){DesktopService.Stop();return 0;}
            if(Array.IndexOf(args,"--smoke-test")>=0){DesktopService.Ensure().GetAwaiter().GetResult();DesktopService.WriteStatus("service-ready","");return 0;}
            string key;using(var sha=SHA256.Create())key=BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(DesktopService.Data.ToLowerInvariant()+"|"+DesktopService.Port))).Replace("-","").Substring(0,24);
            bool first;using(var instance=new Mutex(true,"Local\\AICounselReviewDesktop-"+key,out first)){
                if(!first){
                    foreach(var p in Process.GetProcessesByName(Process.GetCurrentProcess().ProcessName)){
                        try{if(p.Id!=Process.GetCurrentProcess().Id&&String.Equals(p.MainModule.FileName,Application.ExecutablePath,StringComparison.OrdinalIgnoreCase)&&p.MainWindowHandle!=IntPtr.Zero){ShowWindow(p.MainWindowHandle,9);SetForegroundWindow(p.MainWindowHandle);break;}}catch(System.ComponentModel.Win32Exception){}
                    }return 0;
                }
                Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new ReviewDesktop());instance.ReleaseMutex();
            }return 0;
        }catch(Exception error){
            Directory.CreateDirectory(DesktopService.Data);File.AppendAllText(Path.Combine(DesktopService.Data,"desktop-error.log"),DateTime.Now+" "+error+Environment.NewLine);
            if(Array.IndexOf(args,"--smoke-test")<0)MessageBox.Show(error.Message,"AI 审稿团桌面版");return 1;
        }
    }
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool ShowWindow(IntPtr window,int command);
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
}

internal class ReviewDesktop:Form {
    WebView2 view;Panel loading;Label message;Button retry;CoreWebView2Environment environment;
    bool initialized=false,checkingClose=false,allowClose=false,stopOnExit=false,installRuntime=false;string runtime="";
    internal ReviewDesktop(){
        Text="AI 审稿团 · 桌面版 "+ReleaseInfo.Version;
        Font=new Font("Microsoft YaHei UI",10F);BackColor=Color.FromArgb(255,253,245);
        Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);StartPosition=FormStartPosition.CenterScreen;
        var area=Screen.PrimaryScreen.WorkingArea;
        Size=new Size(Math.Min(1440,area.Width-40),Math.Min(960,area.Height-40));MinimumSize=new Size(860,620);AutoScaleMode=AutoScaleMode.Dpi;
        var menu=new MenuStrip{BackColor=BackColor,Font=Font};
        var file=new ToolStripMenuItem("文件");
        file.DropDownItems.Add("打开数据目录",null,(s,e)=>DesktopService.OpenExternal(DesktopService.Data));
        file.DropDownItems.Add(new ToolStripSeparator());file.DropDownItems.Add("关闭窗口",null,(s,e)=>Close());
        file.DropDownItems.Add("完全退出",null,(s,e)=>{stopOnExit=true;Close();});
        var display=new ToolStripMenuItem("视图");
        display.DropDownItems.Add("刷新当前页面",null,(s,e)=>{if(initialized)view.Reload();});
        display.DropDownItems.Add("放大文字",null,(s,e)=>{if(initialized)view.ZoomFactor=Math.Min(1.5,view.ZoomFactor+0.1);});
        display.DropDownItems.Add("缩小文字",null,(s,e)=>{if(initialized)view.ZoomFactor=Math.Max(0.8,view.ZoomFactor-0.1);});
        display.DropDownItems.Add("还原文字大小",null,(s,e)=>{if(initialized)view.ZoomFactor=1;});
        var help=new ToolStripMenuItem("帮助");help.DropDownItems.Add("使用教程",null,(s,e)=>OpenGuide());
        help.DropDownItems.Add("关于桌面版",null,(s,e)=>MessageBox.Show("AI 审稿团 "+ReleaseInfo.Version+"\n独立 Windows 窗口，无需打开浏览器。\nAPI 配置、人设和审稿记录存储在本机数据目录。\n微软 WebView2 运行环境："+runtime,Text));
        menu.Items.AddRange(new ToolStripItem[]{file,display,help});MainMenuStrip=menu;
        view=new WebView2{Dock=DockStyle.Fill,DefaultBackgroundColor=BackColor};Controls.Add(view);
        loading=new Panel{Dock=DockStyle.Fill,BackColor=BackColor};
        var box=new TableLayoutPanel{AutoSize=true,AutoSizeMode=AutoSizeMode.GrowAndShrink,ColumnCount=1,Padding=new Padding(25)};
        var image=Path.Combine(DesktopService.Root,"assets","yuanbao-ip","yuanbao-ip-cat-master.png");
        if(File.Exists(image))box.Controls.Add(new PictureBox{Image=Image.FromFile(image),SizeMode=PictureBoxSizeMode.Zoom,Width=120,Height=120});
        box.Controls.Add(new Label{Text="正在打开审稿室…",AutoSize=true,Font=new Font(Font.FontFamily,22,FontStyle.Bold)});
        message=new Label{Text="正在连接本机服务，读取配置与审稿记录。",AutoSize=true,MaximumSize=new Size(650,0),Margin=new Padding(3,20,3,20)};box.Controls.Add(message);
        retry=new Button{Text="重试",AutoSize=true,Visible=false};retry.Click+=async(s,e)=>{
            if(installRuntime){
                retry.Enabled=false;
                try{var process=Process.Start(new ProcessStartInfo(Path.Combine(DesktopService.Root,"runtime","MicrosoftEdgeWebview2Setup.exe"),"/silent /install"){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden});await Task.Run(()=>process.WaitForExit());installRuntime=false;retry.Text="重试";}
                catch(Exception ex){message.Text=ex.Message;}
                finally{retry.Enabled=true;}
            }
            await Initialize();
        };box.Controls.Add(retry);
        loading.Controls.Add(box);loading.Resize+=(s,e)=>{box.Location=new Point(Math.Max(0,(loading.Width-box.Width)/2),Math.Max(0,(loading.Height-box.Height)/2));};
        Controls.Add(loading);Controls.Add(menu);loading.BringToFront();menu.BringToFront();
        Shown+=async(s,e)=>await Initialize();FormClosing+=ClosingReview;
    }
    async Task Initialize(){
        retry.Visible=false;message.Text="正在启动本机审稿服务…";
        try{
            await DesktopService.Ensure();
            runtime=CoreWebView2Environment.GetAvailableBrowserVersionString();
            message.Text="正在载入桌面工作台…";
            environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(DesktopService.Data,"desktop-webview"));
            await view.EnsureCoreWebView2Async(environment);
            view.CoreWebView2.Settings.AreDevToolsEnabled=false;
            view.CoreWebView2.Settings.IsStatusBarEnabled=false;
            view.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled=false;
            view.CoreWebView2.Settings.IsPasswordAutosaveEnabled=false;
            view.CoreWebView2.Settings.IsGeneralAutofillEnabled=false;
            view.CoreWebView2.PermissionRequested+=(s,e)=>e.State=CoreWebView2PermissionState.Deny;
            view.CoreWebView2.NewWindowRequested+=(s,e)=>{e.Handled=true;OpenLink(e.Uri);};
            view.CoreWebView2.NavigationStarting+=(s,e)=>{
                Uri uri;if(!Uri.TryCreate(e.Uri,UriKind.Absolute,out uri)){e.Cancel=true;return;}
                if(uri.Scheme=="about")return;
                if(uri.GetLeftPart(UriPartial.Authority)!=DesktopService.Url){e.Cancel=true;OpenLink(e.Uri);}
            };
            view.CoreWebView2.NavigationCompleted+=(s,e)=>{
                if(e.IsSuccess){initialized=true;loading.Visible=false;DesktopService.WriteStatus("workbench-loaded",runtime);}
                else{message.Text="工作台载入失败，请点击重试。";retry.Visible=true;loading.Visible=true;}
            };
            view.Source=new Uri(DesktopService.Url+"/");
        }catch(WebView2RuntimeNotFoundException){
            message.Text="缺少微软桌面显示组件。安装 Microsoft Edge WebView2 Runtime 后，重新打开审稿团即可。";
            var bootstrap=Path.Combine(DesktopService.Root,"runtime","MicrosoftEdgeWebview2Setup.exe");
            if(File.Exists(bootstrap)){
                retry.Text="安装桌面显示组件";retry.Visible=true;installRuntime=true;
            }
        }catch(Exception error){
            message.Text=error.Message;retry.Text="重试";retry.Visible=true;
            File.AppendAllText(Path.Combine(DesktopService.Data,"desktop-error.log"),DateTime.Now+" "+error+Environment.NewLine);
        }
    }
    void OpenLink(string link){
        Uri uri;if(Uri.TryCreate(link,UriKind.Absolute,out uri)&&(uri.Scheme=="https"||uri.Scheme=="http"))DesktopService.OpenExternal(link);
    }
    void OpenGuide(){
        var path=Path.Combine(DesktopService.Root,"详细教程");
        if(!Directory.Exists(path)){MessageBox.Show("请查看安装目录中的使用说明.txt。",Text);return;}
        var guide=new Form{Text="AI 审稿团 · 使用教程",Width=1120,Height=820,StartPosition=FormStartPosition.CenterParent,Icon=Icon,Font=Font};
        var browser=new WebView2{Dock=DockStyle.Fill,DefaultBackgroundColor=BackColor};guide.Controls.Add(browser);
        guide.Shown+=async(s,e)=>{try{
            await browser.EnsureCoreWebView2Async(environment);
            browser.CoreWebView2.SetVirtualHostNameToFolderMapping("review-guide.local",path,CoreWebView2HostResourceAccessKind.DenyCors);
            browser.CoreWebView2.Settings.IsStatusBarEnabled=false;
            browser.CoreWebView2.NewWindowRequested+=(sender,args)=>{args.Handled=true;OpenLink(args.Uri);};
            browser.CoreWebView2.NavigationStarting+=(sender,args)=>{Uri u;if(Uri.TryCreate(args.Uri,UriKind.Absolute,out u)&&u.Host!="review-guide.local"&&u.Scheme!="about"){args.Cancel=true;OpenLink(args.Uri);}};
            browser.Source=new Uri("https://review-guide.local/使用教程.html");
        }catch(Exception ex){MessageBox.Show(ex.Message,guide.Text);}};
        guide.Show(this);
    }
    async void ClosingReview(object sender,FormClosingEventArgs e){
        if(allowClose||!initialized){if(stopOnExit)DesktopService.Stop();return;}
        e.Cancel=true;if(checkingClose)return;checkingClose=true;
        bool active=false;
        try{
            using(var client=new WebClient()){client.Proxy=null;
                var entries=DesktopService.Json.DeserializeObject(await client.DownloadStringTaskAsync(DesktopService.Url+"/api/conversations")) as object[];
                foreach(var item in entries ?? new object[0]){
                    var row=item as System.Collections.Generic.Dictionary<string,object>;
                    var progress=await client.DownloadStringTaskAsync(DesktopService.Url+"/api/conversations/"+row["id"]+"/progress");
                    if(progress.Contains("\"active\":true")||progress.Contains("\"active\": true")){active=true;break;}
                }
            }
        }catch{ }
        checkingClose=false;
        if(active&&MessageBox.Show("审稿还在进行，关闭窗口可能中断当前审阅。确定关闭吗？已保存的记录不会删除。",Text,MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes){stopOnExit=false;return;}
        allowClose=true;Close();
    }
}
