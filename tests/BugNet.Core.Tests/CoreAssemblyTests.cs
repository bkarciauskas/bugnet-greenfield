using BugNet.Core;
using Xunit;

namespace BugNet.Core.Tests;

public sealed class CoreAssemblyTests
{
    [Fact]
    public void CoreAssemblyIsLoadable()
    {
        Assert.Equal("BugNet.Core", typeof(CoreAssembly).Assembly.GetName().Name);
    }
}
