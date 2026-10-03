namespace BugNet.Core;

public sealed class XsltHelpers
{
    [System.Diagnostics.CodeAnalysis.SuppressMessage(
        "Performance",
        "CA1822:Mark members as static",
        Justification = "An XSLT extension object only calls instance methods.")]
    public string StripHTML2(string? value) => value ?? string.Empty;
}
