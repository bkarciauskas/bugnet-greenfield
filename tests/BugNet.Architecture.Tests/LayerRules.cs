using System.Reflection;
using System.Xml.Linq;
using BugNet.Core;
using BugNet.Data;
using BugNet.Web;
using NetArchTest.Rules;
using Xunit;

namespace BugNet.Architecture.Tests;

public sealed class LayerRules
{
    private static readonly string[] Sentinels =
    [
        "15.135.1.105",
        "BugNetServices.asmx",
        "BugNET.",
        "CoreWCF",
    ];

    private static readonly string[] DataInternalNamespaces =
    [
        "BugNet.Data.Entities",
        "BugNet.Data.Mapping",
        "BugNet.Data.Persistence",
        "BugNet.Data.Internal",
    ];

    [Fact]
    public void CoreDoesNotReferenceWebDataEfOrAspNet()
    {
        var assembly = typeof(CoreAssembly).Assembly;
        Assert.NotEmpty(assembly.GetTypes());

        foreach (var name in ReferencedNames(assembly))
        {
            Assert.False(IsForbiddenCoreReference(name), name);
        }

        AssertPassing(
            Types.InAssembly(assembly)
                .ShouldNot()
                .HaveDependencyOnAny(
                    "BugNet.Web",
                    "BugNet.Data",
                    "Microsoft.EntityFrameworkCore",
                    "Microsoft.AspNetCore",
                    "CoreWCF")
                .GetResult());

        var project = ProjectPath("src", "BugNet.Core", "BugNet.Core.csproj");
        Assert.Empty(ProjectReferenceNames(project));
        Assert.Empty(PackageReferenceNames(project));
    }

    [Fact]
    public void DataReferencesCoreOnlyAndKeepsEfCorePrivate()
    {
        var project = ProjectPath("src", "BugNet.Data", "BugNet.Data.csproj");
        Assert.Equal(["BugNet.Core"], ProjectReferenceNames(project));
        Assert.Equal(["Microsoft.EntityFrameworkCore.SqlServer"], PackageReferenceNames(project));
        Assert.Contains("compile", PrivateAssets(project, "Microsoft.EntityFrameworkCore.SqlServer"), StringComparison.OrdinalIgnoreCase);

        var names = ReferencedNames(typeof(DataAssembly).Assembly);
        Assert.Contains("BugNet.Core", names);
        Assert.Contains(names, name => name.StartsWith("Microsoft.EntityFrameworkCore", StringComparison.Ordinal));
        Assert.DoesNotContain("BugNet.Web", names);
        Assert.DoesNotContain(names, name => name.StartsWith("Microsoft.AspNetCore", StringComparison.Ordinal));
        Assert.DoesNotContain(names, name => name.StartsWith("CoreWCF", StringComparison.Ordinal));

        AssertPassing(
            Types.InAssembly(typeof(DataAssembly).Assembly)
                .That()
                .HaveName(nameof(DataAssembly))
                .Should()
                .HaveDependencyOn("Microsoft.EntityFrameworkCore")
                .GetResult());
        AssertPassing(
            Types.InAssembly(typeof(DataAssembly).Assembly)
                .ShouldNot()
                .HaveDependencyOnAny("BugNet.Web", "Microsoft.AspNetCore", "CoreWCF")
                .GetResult());
    }

    [Fact]
    public void WebReferencesCoreAndNotDataInternals()
    {
        var project = ProjectPath("src", "BugNet.Web", "BugNet.Web.csproj");
        var references = ProjectReferenceNames(project);
        Assert.Contains("BugNet.Core", references);
        Assert.All(references, name => Assert.True(name is "BugNet.Core" or "BugNet.Data", name));
        Assert.DoesNotContain(
            PackageReferenceNames(project),
            name => name.Contains("EntityFrameworkCore", StringComparison.Ordinal)
                || name.StartsWith("CoreWCF", StringComparison.Ordinal));

        var names = ReferencedNames(typeof(Program).Assembly);
        Assert.Contains("BugNet.Core", names);
        Assert.DoesNotContain(names, name => name.StartsWith("Microsoft.EntityFrameworkCore", StringComparison.Ordinal));
        Assert.DoesNotContain(names, name => name.StartsWith("CoreWCF", StringComparison.Ordinal));

        AssertPassing(
            Types.InAssembly(typeof(Program).Assembly)
                .That()
                .HaveName(nameof(Program))
                .Should()
                .HaveDependencyOn("BugNet.Core")
                .GetResult());
        AssertPassing(
            Types.InAssembly(typeof(Program).Assembly)
                .ShouldNot()
                .HaveDependencyOnAny(
                    DataInternalNamespaces.Concat(["Microsoft.EntityFrameworkCore", "CoreWCF"]).ToArray())
                .GetResult());
    }

    [Fact]
    public void CoreTestsReferenceCoreOnly()
    {
        var project = ProjectPath("tests", "BugNet.Core.Tests", "BugNet.Core.Tests.csproj");
        Assert.Equal(["BugNet.Core"], ProjectReferenceNames(project));
        Assert.DoesNotContain(
            PackageReferenceNames(project),
            name => name.Contains("EntityFrameworkCore", StringComparison.Ordinal)
                || name.Contains("AspNetCore", StringComparison.Ordinal)
                || name.StartsWith("CoreWCF", StringComparison.Ordinal));
    }

    [Fact]
    public void SoapHostIsNotPresent()
    {
        var root = RepoRoot();
        Assert.False(Directory.Exists(Path.Combine(root, "src", "BugNet.Soap")));
        var solution = File.ReadAllText(Path.Combine(root, "BugNet.sln"));
        Assert.DoesNotContain("BugNet.Soap", solution, StringComparison.Ordinal);
        Assert.DoesNotContain("CoreWCF", solution, StringComparison.Ordinal);

        foreach (var project in Directory.EnumerateFiles(root, "*.csproj", SearchOption.AllDirectories))
        {
            if (IsIgnored(project))
            {
                continue;
            }

            Assert.DoesNotContain("CoreWCF", File.ReadAllText(project), StringComparison.Ordinal);
        }
    }

    [Fact]
    public void ProjectsDoNotReferenceLegacyHostProceduresOrCode()
    {
        var root = RepoRoot();
        var tokens = LoadTokens(root);
        Assert.True(tokens.Count >= 180, $"Expected the legacy denylist to stay intact, found {tokens.Count} tokens.");
        foreach (var sentinel in Sentinels)
        {
            Assert.Contains(sentinel, tokens);
        }

        foreach (var file in FilesUnder(Path.Combine(root, "src")).Concat(FilesUnder(Path.Combine(root, "tests"))))
        {
            var text = File.ReadAllText(file);
            foreach (var token in tokens)
            {
                if (text.Contains(token, StringComparison.Ordinal))
                {
                    Assert.Fail($"{Path.GetRelativePath(root, file)} contains '{token}'.");
                }
            }
        }
    }

    private static void AssertPassing(TestResult result)
    {
        var names = result.FailingTypeNames ?? [];
        Assert.True(result.IsSuccessful, string.Join(", ", names));
    }

    private static bool IsForbiddenCoreReference(string name)
    {
        return name is "BugNet.Web" or "BugNet.Data"
            || name.StartsWith("Microsoft.EntityFrameworkCore", StringComparison.Ordinal)
            || name.StartsWith("Microsoft.AspNetCore", StringComparison.Ordinal)
            || name.StartsWith("CoreWCF", StringComparison.Ordinal);
    }

    private static List<string> ReferencedNames(Assembly assembly)
    {
        return assembly
            .GetReferencedAssemblies()
            .Select(name => name.Name ?? string.Empty)
            .ToList();
    }

    private static string ProjectPath(params string[] parts)
    {
        var all = new string[parts.Length + 1];
        all[0] = RepoRoot();
        parts.CopyTo(all, 1);
        return Path.Combine(all);
    }

    private static List<string> ProjectReferenceNames(string projectPath)
    {
        return Names(projectPath, "ProjectReference")
            .Select(ProjectNameFromInclude)
            .Order(StringComparer.Ordinal)
            .ToList();
    }

    private static List<string> PackageReferenceNames(string projectPath)
    {
        return Names(projectPath, "PackageReference")
            .Order(StringComparer.Ordinal)
            .ToList();
    }

    private static List<string> Names(string projectPath, string elementName)
    {
        return LoadProject(projectPath)
            .Descendants()
            .Where(element => element.Name.LocalName == elementName)
            .Select(element => element.Attribute("Include")?.Value ?? string.Empty)
            .ToList();
    }

    private static string PrivateAssets(string projectPath, string packageName)
    {
        var package = LoadProject(projectPath)
            .Descendants()
            .Single(element => element.Name.LocalName == "PackageReference"
                && string.Equals(element.Attribute("Include")?.Value, packageName, StringComparison.Ordinal));
        var child = package.Elements().SingleOrDefault(element => element.Name.LocalName == "PrivateAssets");
        return child?.Value ?? package.Attribute("PrivateAssets")?.Value ?? string.Empty;
    }

    private static XDocument LoadProject(string projectPath)
    {
        return XDocument.Load(projectPath);
    }

    private static List<string> LoadTokens(string root)
    {
        var path = Path.Combine(root, "tests", "BugNet.Architecture.Tests", "LegacyReferences.txt");
        var tokens = new List<string>();
        foreach (var raw in File.ReadAllLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#'))
            {
                continue;
            }

            tokens.Add(line);
        }

        return tokens;
    }

    private static string ProjectNameFromInclude(string include)
    {
        var normalized = include.Replace('\\', '/');
        var file = normalized.Split('/')[^1];
        return Path.GetFileNameWithoutExtension(file);
    }

    private static IEnumerable<string> FilesUnder(string directory)
    {
        foreach (var path in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
        {
            if (IsIgnored(path) || IsCheckerSource(path))
            {
                continue;
            }

            yield return path;
        }
    }

    private static bool IsCheckerSource(string path)
    {
        var name = Path.GetFileName(path);
        return name is "LayerRules.cs" or "LegacyReferences.txt";
    }

    private static bool IsIgnored(string path)
    {
        if (path.EndsWith(".pyc", StringComparison.Ordinal))
        {
            return true;
        }

        var parts = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return parts.Contains("bin") || parts.Contains("obj") || parts.Contains("__pycache__");
    }

    private static string RepoRoot()
    {
        foreach (var start in new[] { AppContext.BaseDirectory, Directory.GetCurrentDirectory() })
        {
            var dir = new DirectoryInfo(start);
            while (dir is not null)
            {
                if (File.Exists(Path.Combine(dir.FullName, "BugNet.sln")))
                {
                    return dir.FullName;
                }

                dir = dir.Parent;
            }
        }

        throw new InvalidOperationException("Could not find BugNet.sln.");
    }
}
