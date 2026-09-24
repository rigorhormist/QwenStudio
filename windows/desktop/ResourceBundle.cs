using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;

// The EXE carries its web UI and Python backend. User data never lives here.
internal static class ResourceBundle
{
    internal static string Unpack()
    {
        using var payload=Assembly.GetExecutingAssembly().GetManifestResourceStream("Studio.Resources")??throw new InvalidOperationException("Application resources are missing.");
        var digest=Convert.ToHexString(SHA256.HashData(payload))[..20];payload.Position=0;
        var parent=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QwenStudio","application");
        var root=Path.Combine(parent,digest);
        using var archive=new ZipArchive(payload,ZipArchiveMode.Read);
        bool Complete()=>File.Exists(Path.Combine(root,".complete"))&&archive.Entries.All(entry=>File.Exists(Path.Combine(root,entry.FullName))&&new FileInfo(Path.Combine(root,entry.FullName)).Length==entry.Length);
        if(Complete())return root;
        Directory.CreateDirectory(parent);
        var staging=Path.Combine(parent,digest+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(staging);
        try{
            foreach(var entry in archive.Entries){
                var path=Path.GetFullPath(Path.Combine(staging,entry.FullName));
                if(!path.StartsWith(staging+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Invalid bundled resource path.");
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);entry.ExtractToFile(path);
            }
            File.WriteAllText(Path.Combine(staging,".complete"),digest);
            // Another user-selected data profile may have unpacked the same EXE.
            using var mutex=new Mutex(false,"Local\\QwenStudioResources"+digest);
            try{mutex.WaitOne();}catch(AbandonedMutexException){}
            try{if(Complete())return root;if(Directory.Exists(root))Directory.Delete(root,true);Directory.Move(staging,root);}
            finally{mutex.ReleaseMutex();}
            return root;
        }finally{if(Directory.Exists(staging))Directory.Delete(staging,true);}
    }
}
