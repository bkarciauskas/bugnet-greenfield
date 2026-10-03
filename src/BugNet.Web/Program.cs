using BugNet.Core;

namespace BugNet.Web;

public static class Program
{
    // A live type token. A discarded typeof is compiled away, and the project reference would vanish from the assembly.
    public static readonly Type CoreMarker = typeof(CoreAssembly);

    public static void Main(string[] args)
    {
        ArgumentNullException.ThrowIfNull(CoreMarker);
        var builder = WebApplication.CreateBuilder(args);
        builder.Services.AddRazorPages();
        var app = builder.Build();
        app.MapRazorPages();
        app.Run();
    }
}
