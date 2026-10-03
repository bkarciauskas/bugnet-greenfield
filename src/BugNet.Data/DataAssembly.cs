using BugNet.Core;
using Microsoft.EntityFrameworkCore;

namespace BugNet.Data;

public static class DataAssembly
{
    public static string CoreAssemblyName { get; } =
        typeof(CoreAssembly).Assembly.GetName().Name ?? string.Empty;

    public static string EntityFrameworkAssemblyName { get; } =
        typeof(DbContext).Assembly.GetName().Name ?? string.Empty;
}
