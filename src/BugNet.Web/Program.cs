using BugNet.Core;
using BugNet.Data;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;

namespace BugNet.Web;

public static class Program
{
    public static readonly Type CoreMarker = typeof(CoreAssembly);

    public static void Main(string[] args)
    {
        ArgumentNullException.ThrowIfNull(CoreMarker);
        var builder = WebApplication.CreateBuilder(args);
        var connectionString = builder.Configuration.GetConnectionString("BugNet");
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            throw new InvalidOperationException("ConnectionStrings:BugNet is required.");
        }

        var database = IssueDatabase.Open(connectionString);
        builder.Services.AddSingleton(database);
        builder.Services.AddSingleton<IAddSender>(_ => new PickupAddSender(
            builder.Configuration["Mail:PickupDirectory"] ?? "C:\\EmailGreenfield"));
        builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
            .AddCookie(options =>
            {
                options.LoginPath = "/Account/Login.aspx";
                options.Cookie.Name = "BugNet.Greenfield";
                options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
            });
        builder.Services.AddAuthorization(options =>
        {
            options.FallbackPolicy = new AuthorizationPolicyBuilder()
                .RequireAuthenticatedUser()
                .Build();
        });
        builder.Services.AddRazorPages();
        var app = builder.Build();
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapRazorPages();
        app.Run();
    }
}
