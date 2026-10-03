using System.Globalization;

namespace BugNet.Core;

public static class CreatedOnText
{
    private static readonly Dictionary<string, string> Patterns = new(StringComparer.Ordinal)
    {
        ["de-DE"] = "dd.MM.yyyy HH:mm",
        ["en-US"] = "M/d/yyyy h:mm tt",
        ["es-ES"] = "dd/MM/yyyy H:mm",
        ["fr-CA"] = "yyyy-MM-dd HH:mm",
        ["it-IT"] = "dd/MM/yyyy HH:mm",
        ["nl-NL"] = "d-M-yyyy HH:mm",
        ["ro-RO"] = "dd.MM.yyyy HH:mm",
        ["ru-RU"] = "dd.MM.yyyy H:mm",
        ["zh-CN"] = "yyyy/M/d H:mm",
    };

    public static string Format(DateTime value, string? preferredLocale)
    {
        var cultureName = string.IsNullOrWhiteSpace(preferredLocale) ? "en-US" : preferredLocale.Trim();
        if (!Patterns.TryGetValue(cultureName, out var pattern))
        {
            cultureName = "en-US";
            pattern = Patterns[cultureName];
        }

        return value.ToString(pattern, CultureInfo.GetCultureInfo(cultureName));
    }
}
